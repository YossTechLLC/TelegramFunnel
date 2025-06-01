#!/usr/bin/env python
"""
combined paygateprime stack
───────────────────────────
features
    • broadcast per-channel hash+sub links (old 1dbtest1.py logic)
    • /start handler that decodes <hash> or <hash>_<sub> tokens
    • announce command that drops deep links into a public channel
    • dynamic “pay $20” invoice (start_np_gateway_new)
    • NowPayments IPN webhook → verify signature → create one-time
      invite link to TLFX1c → DM paying user
    • optional /database conversation demo

flask + python-telegram-bot share the same asyncio loop via nest_asyncio.
"""

# ─────────────────────── imports ────────────────────────────────────────────
import os, json, hmac, hashlib, base64, asyncio, logging, secrets
from html import escape
from urllib.parse import quote
from datetime import datetime, timedelta

import psycopg2, requests, httpx, nest_asyncio
from flask import Flask, request, abort, jsonify
from google.cloud import secretmanager
from telegram import (
    Update, Bot, ForceReply, KeyboardButton, ReplyKeyboardMarkup,
    WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters
)

nest_asyncio.apply()              # allow single loop
app = Flask(__name__)

# ─────────────────────── configuration ──────────────────────────────────────
DB_CFG   = dict(
    host="34.58.246.248", port=5432, dbname="client_table",
    user="postgres", password="Chigdabeast123$"
)

TLFX_PRIVATE_CHANNEL_ID = -1002398681722          # TLFX1c channel id
LINK_LIFETIME_SEC       = 3600                    # invite link ttl

# env-based secret refs
TELEGRAM_SECRET = os.getenv("TELEGRAM_BOT_SECRET_NAME")
NOWPAY_SECRET   = os.getenv("PAYMENT_PROVIDER_SECRET_NAME")
NOW_SIG_SECRET  = os.getenv("NOWPAYMENTS_WEBHOOK_SECRET")  # raw secret string

# ─────────────────────── helper: fetch secret ───────────────────────────────
def fetch_secret(secret_resource_name: str) -> str | None:
    try:
        client   = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(request={"name": secret_resource_name})
        return response.payload.data.decode()
    except Exception as e:
        logging.error("secret fetch error for %s: %s", secret_resource_name, e)
        return None

BOT_TOKEN = fetch_secret(TELEGRAM_SECRET)
NOWPAY_API_KEY = fetch_secret(NOWPAY_SECRET)

# ─────────────────────── global maps ────────────────────────────────────────
tele_open_list: list[int]                         = []
tele_info_map: dict[int, dict[str, int | None]]  = {}

# ─────────────────────── db helpers ─────────────────────────────────────────
def load_channel_info() -> None:
    tele_open_list.clear(); tele_info_map.clear()
    try:
        with psycopg2.connect(**DB_CFG) as conn, conn.cursor() as cur:
            cur.execute("SELECT tele_open, sub_1, sub_2, sub_3 FROM tele_channel")
            for cid, s1, s2, s3 in cur.fetchall():
                tele_open_list.append(cid)
                tele_info_map[cid] = {"sub_1": s1, "sub_2": s2, "sub_3": s3}
    except Exception as e:
        logging.error("db load: %s", e)

def insert_payment_row(payment_id, chat_id, usd, status, invite=None):
    try:
        with psycopg2.connect(**DB_CFG) as conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO payments(payment_id,chat_id,amount_usd,status,invite_link)
                   VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (payment_id) DO UPDATE
                   SET status=excluded.status, invite_link=excluded.invite_link""",
                (payment_id, chat_id, usd, status, invite)
            )
    except Exception as e:
        logging.error("db insert payment: %s", e)

# ─────────────────────── telegram send helper ───────────────────────────────
def tg_send(chat_id:int, html:str):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id":chat_id,"text":html,"parse_mode":"HTML","disable_web_page_preview":True},
            timeout=10,
        ); r.raise_for_status()
        msg_id = r.json()["result"]["message_id"]
        del_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
        asyncio.get_event_loop().call_later(
            900, lambda: requests.post(del_url,json={"chat_id":chat_id,"message_id":msg_id},timeout=5)
        )
    except Exception as e:
        logging.error("send to %s: %s", chat_id, e)

# ─────────────────────── broadcast hash+sub links ───────────────────────────
def broadcast_links():
    if not tele_open_list: load_channel_info()
    for cid in tele_open_list:
        subs = tele_info_map.get(cid,{})
        base_hash = base64.urlsafe_b64encode(str(cid).encode()).decode()
        lines = ["<b>decode links:</b>"]
        for key in ("sub_1","sub_2","sub_3"):
            val = subs.get(key);  # could be None
            if val is None: continue
            token = f"{base_hash}_{val}"
            url   = f"https://t.me/PayGatePrime_bot?start={token}"
            lines.append(f"• {key} <b>{val}</b> → <a href=\"{escape(url)}\">link</a>")
        tg_send(cid, "\n".join(lines))

# ─────────────────────── invoice helper ─────────────────────────────────────
async def create_invoice(chat_id:int)->str:
    order_id = f"{base64.urlsafe_b64encode(str(chat_id).encode()).decode()}::{secrets.token_hex(3)}"
    payload = {
        "price_amount":20.0,"price_currency":"USD",
        "order_id":order_id,"order_description":"TLFX1c sub",
        "ipn_callback_url":"https://<your-domain>/np_webhook",
        "success_url":"https://t.me/PayGatePrime_bot",
        "cancel_url":"https://t.me/PayGatePrime_bot"
    }
    headers = {"x-api-key":NOWPAY_API_KEY,"Content-Type":"application/json"}
    async with httpx.AsyncClient(timeout=30) as cli:
        r = await cli.post("https://api.nowpayments.io/v1/invoice",headers=headers,json=payload)
    if r.status_code!=200:
        raise RuntimeError(f"np error {r.status_code}: {r.text}")
    return r.json()["invoice_url"]

# ─────────────────────── bot command handlers ───────────────────────────────
async def start_cmd(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("use /start <hash_sub>")
        return
    try:
        token = context.args[0]
        h,_,sub = token.partition("_")
        cid = int(base64.urlsafe_b64decode(h.encode()).decode())
        sub_disp = sub if sub else "n/a"
        await update.message.reply_text(
            f"ID <code>{cid}</code>\nsub <code>{escape(sub_disp)}</code>",
            parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"err {e}")

async def start_np_gateway_new(update:Update, context:ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_user.id
    try:
        link = await create_invoice(chat_id)
        kb = ReplyKeyboardMarkup.from_button(
            KeyboardButton(text="Open Payment Gateway",web_app=WebAppInfo(url=link))
        )
        await update.message.reply_text(
            "click button to pay (20-min window).", reply_markup=kb
        )
    except Exception as e:
        await update.message.reply_text(f"np error: {e}")

async def announce(update:Update, context:ContextTypes.DEFAULT_TYPE):
    # drop deep-links in current chat
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    payload = f"{user_id}-{chat_id}"
    enc = quote(payload)
    text = f"demo deep links"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Pay", url=f"https://t.me/PayGatePrime_bot?start={enc}-start_np_gateway_new")]
    ])
    await update.message.reply_text(text,reply_markup=kb)

# /database conversation (same as before, trimmed for brevity)
ID_INPUT,NAME_INPUT,AGE_INPUT=range(3)
async def start_db(update:Update, context:ContextTypes.DEFAULT_TYPE):
    context.user_data["db"]=True; await update.message.reply_text("id:"); return ID_INPUT
async def recv_id(update:Update, context:ContextTypes.DEFAULT_TYPE):
    context.user_data["id"]=int(update.message.text); await update.message.reply_text("name:"); return NAME_INPUT
async def recv_name(update:Update, context:ContextTypes.DEFAULT_TYPE):
    context.user_data["name"]=update.message.text; await update.message.reply_text("age:"); return AGE_INPUT
async def recv_age(update:Update, context:ContextTypes.DEFAULT_TYPE):
    context.user_data["age"]=int(update.message.text)
    await update.message.reply_text("saved"); context.user_data.clear(); return ConversationHandler.END
async def cancel(update:Update, context:ContextTypes.DEFAULT_TYPE):
    context.user_data.clear(); await update.message.reply_text("cancelled"); return ConversationHandler.END

# ─────────────────────── flask webhook ──────────────────────────────────────
@app.route("/np_webhook", methods=["POST"])
def np_webhook():
    raw = request.data
    sig  = request.headers.get("x-nowpayments-sig","")
    calc = hmac.new(NOW_SIG_SECRET.encode(), raw, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(sig, calc): abort(403)
    data = request.json or {}
    if data.get("payment_status")!="finished":
        return "ignored", 200

    order_id = data["order_id"]              # <hash>::nonce
    hash_part = order_id.split("::",1)[0]
    chat_id = int(base64.urlsafe_b64decode(hash_part.encode()).decode())
    usd = data.get("price_amount")

    # create one-time invite link
    try:
        bot = Bot(BOT_TOKEN)
        res = bot.create_chat_invite_link(
            chat_id=TLFX_PRIVATE_CHANNEL_ID,
            expire_date=int((datetime.utcnow()+timedelta(seconds=LINK_LIFETIME_SEC)).timestamp()),
            member_limit=1
        )
        link = res.invite_link
        bot.send_message(chat_id, f"payment received ✅\nhere is your link:\n{link}",
                         disable_web_page_preview=True)
        insert_payment_row(data["payment_id"], chat_id, usd, "finished", link)
    except Exception as e:
        logging.error("invite send error: %s", e)
        insert_payment_row(data["payment_id"], chat_id, usd, "error", None)

    return "ok", 200

# ─────────────────────── main bootstrap ─────────────────────────────────────
if __name__=="__main__":
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    load_channel_info()
    broadcast_links()

    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start_cmd))
    bot_app.add_handler(CommandHandler("start_np_gateway_new", start_np_gateway_new))
    bot_app.add_handler(CommandHandler("announce", announce))
    bot_app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("database", start_db)],
        states={
            ID_INPUT:[MessageHandler(filters.TEXT & ~filters.COMMAND, recv_id)],
            NAME_INPUT:[MessageHandler(filters.TEXT & ~filters.COMMAND, recv_name)],
            AGE_INPUT:[MessageHandler(filters.TEXT & ~filters.COMMAND, recv_age)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    loop = asyncio.get_event_loop()
    loop.create_task(bot_app.run_polling())
    app.run(host="0.0.0.0",port=5000)
