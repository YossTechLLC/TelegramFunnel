#!/usr/bin/env python
"""
paygateprime merged stack
──────────────────────────
• hash+sub broadcast links (/start <hash_sub>)
• announce deep links with user+chat payload (/start <payload>-<cmd>)
• NowPayments invoice creation & IPN webhook → one-time invite link
• optional /database conversation
"""

# ───────── imports ──────────────────────────────────────────────────────────
import os, json, hmac, hashlib, base64, asyncio, logging, secrets
from html import escape
from urllib.parse import quote
from datetime import datetime, timedelta

import psycopg2, requests, httpx, nest_asyncio
from flask import Flask, request, abort
from google.cloud import secretmanager
from telegram import (
    Update, Bot, ForceReply, KeyboardButton, ReplyKeyboardMarkup,
    WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters
)

nest_asyncio.apply()
app = Flask(__name__)

# ───────── configuration / secrets ──────────────────────────────────────────
DB_CFG = dict(
    host="34.58.246.248", port=5432, dbname="client_table",
    user="postgres", password="Chigdabeast123$"
)

TLFX_PRIVATE_CHANNEL_ID = -1002398681722      # TLFX1c
INVITE_LIFETIME_SEC     = 3600

TELEGRAM_SECRET  = os.getenv("TELEGRAM_BOT_SECRET_NAME")
NOWPAY_SECRET    = os.getenv("PAYMENT_PROVIDER_SECRET_NAME")
NOW_SIG_SECRET   = os.getenv("NOWPAYMENTS_WEBHOOK_SECRET")   # raw value

def gcp_secret(path:str)->str|None:
    try:
        cli = secretmanager.SecretManagerServiceClient()
        return cli.access_secret_version(request={"name":path}).payload.data.decode()
    except Exception as e:
        logging.error("secret %s err %s", path, e); return None

BOT_TOKEN       = gcp_secret(TELEGRAM_SECRET)
NOWPAY_API_KEY  = gcp_secret(NOWPAY_SECRET)

# ───────── globals ──────────────────────────────────────────────────────────
tele_open_list: list[int] = []
tele_info_map: dict[int,dict[str,int|None]] = {}

# ───────── DB helpers ───────────────────────────────────────────────────────
def load_channels():
    tele_open_list.clear(); tele_info_map.clear()
    with psycopg2.connect(**DB_CFG) as c, c.cursor() as cur:
        cur.execute("SELECT tele_open,sub_1,sub_2,sub_3 FROM tele_channel")
        for cid,s1,s2,s3 in cur.fetchall():
            tele_open_list.append(cid)
            tele_info_map[cid] = {"sub_1":s1,"sub_2":s2,"sub_3":s3}

def insert_payment(pid,chat,usd,status,invite=None):
    with psycopg2.connect(**DB_CFG) as c, c.cursor() as cur:
        cur.execute("""INSERT INTO payments(payment_id,chat_id,amount_usd,status,invite_link)
                       VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT(payment_id) DO UPDATE
                       SET status=excluded.status, invite_link=excluded.invite_link""",
                    (pid,chat,usd,status,invite))

# ───────── telegram helpers ─────────────────────────────────────────────────
def tg_send(chat:int, html:str):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id":chat,"text":html,"parse_mode":"HTML","disable_web_page_preview":True},
            timeout=10,
        ); r.raise_for_status()
        msg_id = r.json()["result"]["message_id"]
        delurl = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
        asyncio.get_event_loop().call_later(
            900, lambda: requests.post(delurl,json={"chat_id":chat,"message_id":msg_id},timeout=5)
        )
    except Exception as e:
        logging.error("tg send %s err %s", chat, e)

# ───────── broadcast hash+sub links ─────────────────────────────────────────
def broadcast_links():
    if not tele_open_list: load_channels()
    for cid in tele_open_list:
        subs = tele_info_map.get(cid,{})
        base = base64.urlsafe_b64encode(str(cid).encode()).decode()
        lines=["<b>decode links:</b>"]
        for k in ("sub_1","sub_2","sub_3"):
            v = subs.get(k);  # may be None
            if v is None: continue
            token = f"{base}_{v}"
            url   = f"https://t.me/PayGatePrime_bot?start={token}"
            lines.append(f"• {k} <b>{v}</b> → <a href=\"{escape(url)}\">link</a>")
        tg_send(cid,"\n".join(lines))

# ───────── NowPayments invoice helper ───────────────────────────────────────
async def make_invoice(chat_id:int)->str:
    order = f"{base64.urlsafe_b64encode(str(chat_id).encode()).decode()}::{secrets.token_hex(3)}"
    body = {
        "price_amount":20.0,"price_currency":"USD",
        "order_id":order,"order_description":"TLFX1c sub",
        "ipn_callback_url":"https://<your-domain>/np_webhook",
        "success_url":"https://t.me/PayGatePrime_bot",
        "cancel_url":"https://t.me/PayGatePrime_bot"
    }
    headers={"x-api-key":NOWPAY_API_KEY,"Content-Type":"application/json"}
    async with httpx.AsyncClient(timeout=30) as cli:
        r = await cli.post("https://api.nowpayments.io/v1/invoice",headers=headers,json=body)
    if r.status_code!=200:
        raise RuntimeError(r.text)
    return r.json()["invoice_url"]

# ───────── /start handler ───────────────────────────────────────────────────
async def start(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("use /start <token>"); return
    token = ctx.args[0]

    # style-1: hash_sub
    if "_" in token and not "-" in token:
        h, sub = token.split("_",1)
        try:
            cid = int(base64.urlsafe_b64decode(h.encode()).decode())
            await update.message.reply_text(
                f"ID <code>{cid}</code>\nsub <code>{escape(sub)}</code>",
                parse_mode="HTML")
        except Exception as e:
            await update.message.reply_text(f"err {e}")
        return

    # style-2: payload-cmd
    if "-" in token:
        try:
            payload, cmd = token.rsplit("-",1)
            user_id, chat_id = payload.split("-",1)
            await update.message.reply_text(f"🔍 Parsed user_id {user_id}, channel_id {chat_id}")
            # dispatch cmd
            if cmd=="start_np_gateway_new":
                await start_np_gateway_new(update, ctx)
            elif cmd=="database":
                await start_db(update, ctx)
            return
        except Exception as e:
            await update.message.reply_text(f"parse error {e}")
            return

    await update.message.reply_text("unrecognised token")

# ───────── pay button handler ───────────────────────────────────────────────
async def start_np_gateway_new(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_user.id
    try:
        url = await make_invoice(chat_id)
        kb = ReplyKeyboardMarkup.from_button(
            KeyboardButton(text="Open Payment Gateway", web_app=WebAppInfo(url=url))
        )
        await update.message.reply_text(
            "click button to pay (20-min window).", reply_markup=kb)
    except Exception as e:
        await update.message.reply_text(f"np error {e}")

# ───────── announce deep links ──────────────────────────────────────────────
async def announce(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    uid, cid = str(update.effective_user.id), str(update.effective_chat.id)
    payload  = quote(f"{uid}-{cid}")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Pay $20", url=f"https://t.me/PayGatePrime_bot?start={payload}-start_np_gateway_new")]
    ])
    await update.message.reply_text("invite links:", reply_markup=kb)

# ───────── /database conversation (compact) ─────────────────────────────────
ID_INPUT,NAME_INPUT,AGE_INPUT=range(3)
async def start_db(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    ctx.user_data["db"]=True; await update.message.reply_text("id:"); return ID_INPUT
async def recv_id(u:Update,ctx:ContextTypes.DEFAULT_TYPE):
    ctx.user_data["id"]=int(u.message.text); await u.message.reply_text("name:"); return NAME_INPUT
async def recv_name(u:Update,ctx:ContextTypes.DEFAULT_TYPE):
    ctx.user_data["name"]=u.message.text; await u.message.reply_text("age:"); return AGE_INPUT
async def recv_age(u:Update,ctx:ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("saved"); ctx.user_data.clear(); return ConversationHandler.END
async def cancel(u:Update,ctx:ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear(); await u.message.reply_text("cancelled"); return ConversationHandler.END

# ───────── NowPayments webhook ──────────────────────────────────────────────
@app.route("/np_webhook",methods=["POST"])
def np_webhook():
    if NOW_SIG_SECRET:
        sig = request.headers.get("x-nowpayments-sig","")
        calc= hmac.new(NOW_SIG_SECRET.encode(), request.data, hashlib.sha512).hexdigest()
        if not hmac.compare_digest(sig,calc): abort(403)

    data = request.json or {}
    if data.get("payment_status")!="finished": return "ok",200

    order_id = data["order_id"]               # <hash>::nonce
    hash_part = order_id.split("::",1)[0]
    chat_id   = int(base64.urlsafe_b64decode(hash_part.encode()).decode())
    usd       = data.get("price_amount")
    pid       = data["payment_id"]

    try:
        bot = Bot(BOT_TOKEN)
        res = bot.create_chat_invite_link(
            chat_id=TLFX_PRIVATE_CHANNEL_ID,
            expire_date=int((datetime.utcnow()+timedelta(seconds=INVITE_LIFETIME_SEC)).timestamp()),
            member_limit=1
        )
        link=res.invite_link
        bot.send_message(chat_id, f"payment confirmed ✅\nhere is your link:\n{link}",
                         disable_web_page_preview=True)
        insert_payment(pid,chat_id,usd,"finished",link)
    except Exception as e:
        logging.error("invite error %s", e)
        insert_payment(pid,chat_id,usd,"error",None)

    return "ok",200

# ───────── main bootstrap ───────────────────────────────────────────────────
if __name__=="__main__":
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    load_channels()
    broadcast_links()

    app_bot = Application.builder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("start_np_gateway_new", start_np_gateway_new))
    app_bot.add_handler(CommandHandler("announce", announce))
    app_bot.add_handler(ConversationHandler(
        entry_points=[CommandHandler("database", start_db)],
        states={
            ID_INPUT:[MessageHandler(filters.TEXT & ~filters.COMMAND, recv_id)],
            NAME_INPUT:[MessageHandler(filters.TEXT & ~filters.COMMAND, recv_name)],
            AGE_INPUT:[MessageHandler(filters.TEXT & ~filters.COMMAND, recv_age)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    loop=asyncio.get_event_loop()
    loop.create_task(app_bot.run_polling())
    app.run(host="0.0.0.0",port=5000)
