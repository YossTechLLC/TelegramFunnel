#!/usr/bin/env python
"""
1main2.py  –  merged application

• Telegram bot (commands, database demo, NowPayments invoice creation)
• Flask server with two endpoints:
      /decode_start  – original hash decoder
      /np_webhook    – NowPayments IPN webhook → one-time invite link
"""

# ───────────────────────────────── imports ──────────────────────────────────
import os, time, hmac, hashlib, secrets, json, asyncio, base64, logging
from html import escape
from urllib.parse import quote

import psycopg2, requests, httpx, nest_asyncio
from flask import Flask, request
from telegram import (
    Bot, Update, ForceReply, KeyboardButton, ReplyKeyboardMarkup,
    WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters
)
from google.cloud import secretmanager  # still used for other tokens

# ───────────────────────────── global setup ────────────────────────────────
nest_asyncio.apply()
app = Flask(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# ───────────────────────────── constants ────────────────────────────────────
DB_CFG  = dict(host="34.58.246.248", port=5432,
               dbname="client_table", user="postgres",
               password="Chigdabeast123$")

BOT_TOKEN       = "8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU"
BOT_USERNAME    = "PayGatePrime_bot"
NOW_WEBHOOK_KEY = "erwUOFI+HmEbEbT5YTqfU83nOU4IBuqL"   # HMAC secret
CHANNEL_ID      = -1002409379260                       # TLFX1c

CALLBACK_URL = "https://us-central1-rikky-telebot1.cloudfunctions.net/simplecallback"

# ───────────────────────────── globals ──────────────────────────────────────
tele_open_list: list[int] = []
tele_info_map: dict[int, dict[str, int | None]] = {}

global_sub_value: float = 5.0      # updated after /start <hash_sub>
global_cid_value: int   = 0        # last decoded channel id

bot_obj = Bot(BOT_TOKEN)

encode_id = lambda i: base64.urlsafe_b64encode(str(i).encode()).decode()
decode_hash = lambda s: int(base64.urlsafe_b64decode(s.encode()).decode())

# ─────────────────── database helpers ───────────────────────────────────────
def fetch_tele_open_list() -> None:
    tele_open_list.clear(); tele_info_map.clear()
    with psycopg2.connect(**DB_CFG) as conn, conn.cursor() as cur:
        cur.execute("SELECT tele_open,sub_1,sub_2,sub_3 FROM tele_channel")
        for cid, s1, s2, s3 in cur.fetchall():
            tele_open_list.append(cid)
            tele_info_map[cid] = {"sub_1": s1, "sub_2": s2, "sub_3": s3}

def get_db_connection():
    return psycopg2.connect(**DB_CFG)

# ─────────────────── telegram utility ───────────────────────────────────────
def send_message(chat_id: int, html: str, ttl: int = 60):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": html,
                  "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=10
        ); r.raise_for_status()
        msg_id = r.json()["result"]["message_id"]
        asyncio.get_event_loop().call_later(
            ttl,
            lambda: requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage",
                json={"chat_id": chat_id, "message_id": msg_id},
                timeout=5
            )
        )
    except Exception as e:
        logging.error("send error to %s: %s", chat_id, e)

# ─────────────────── broadcast links ────────────────────────────────────────
def broadcast_hash_links():
    if not tele_open_list: fetch_tele_open_list()
    for cid in tele_open_list:
        subs = tele_info_map.get(cid, {})
        base = encode_id(cid)
        lines = ["<b>decode links:</b>"]
        for key in ("sub_1", "sub_2", "sub_3"):
            val = subs.get(key);  # may be None
            if val is None: continue
            token = f"{base}_{val}"
            url   = f"https://t.me/{BOT_USERNAME}?start={token}"
            lines.append(
                f"• {escape(key)} <b>{val}</b> → <a href=\"{escape(url)}\">link</a>"
            )
        send_message(cid, "\n".join(lines))

# ─────────────────── Flask endpoints ────────────────────────────────────────
@app.route("/decode_start")
def decode_start():
    token = request.args.get("start")
    user  = request.args.get("user_id", "unknown")
    if not token: return "missing start", 400
    try:
        h, _, sub = token.partition("_")
        cid = decode_hash(h)
        send_message(
            cid,
            f"🔓 decoded ID: <code>{cid}</code>\n"
            f"👤 user: <code>{escape(user)}</code>\n"
            f"📦 sub value: <code>{escape(sub or 'n/a')}</code>"
        )
        return "ok", 200
    except Exception as e:
        return f"err {e}", 500

def verify_sig(raw: bytes, header: str) -> bool:
    calc = hmac.new(NOW_WEBHOOK_KEY.encode(), raw, hashlib.sha512).hexdigest()
    return hmac.compare_digest(calc, header)

@app.route("/np_webhook", methods=["POST"])
def np_webhook():
    if not verify_sig(request.data, request.headers.get("x-nowpayments-sig", "")):
        return "bad signature", 403
    data = request.get_json(silent=True) or {}
    if data.get("payment_status") != "finished":
        return "ignored", 200
    try:
        uid = int(data["order_id"].split("::",1)[0])
    except Exception:
        return "bad order_id", 400
    try:
        invite = bot_obj.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            expire_date=int(time.time()) + 3600,
            member_limit=1
        ).invite_link
        bot_obj.send_message(
            uid,
            f"✅ Payment confirmed!\nHere is your private-channel link:\n{invite}",
            disable_web_page_preview=True
        )
    except Exception as e:
        logging.error("telegram error %s", e)
        return "telegram error", 500
    return "ok", 200

# ─────────────────── Bot command handlers ───────────────────────────────────
ID_INPUT, NAME_INPUT, AGE_INPUT = range(3)

async def start_bot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global global_sub_value, global_cid_value
    user = update.effective_user
    if not ctx.args:
        await update.message.reply_html(
            rf"Hi {user.mention_html()}! – use /start &lt;hash_sub&gt;",
            reply_markup=ForceReply(selective=True)
        )
        return

    token = ctx.args[0]
    try:
        h, _, sub_part = token.partition("_")
        cid = decode_hash(h)
        price = float(sub_part)
        global_sub_value = price
        global_cid_value = cid
        await update.message.reply_text(
            f"ID <code>{cid}</code>; sub set to <code>{price}</code>",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"decode err: {e}")

async def start_np_gateway_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    payload = {
        "price_amount": global_sub_value,
        "price_currency": "USD",
        "order_id": f"{update.effective_user.id}::{secrets.token_hex(3)}",
        "order_description": "TLFX1c subscription",
        "ipn_callback_url": CALLBACK_URL,
        "success_url": CALLBACK_URL,
        "cancel_url": CALLBACK_URL
    }
    headers = {
        "x-api-key": fetch_payment_provider_token(),
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient(timeout=30) as cli:
        r = await cli.post(
            "https://api.nowpayments.io/v1/invoice",
            headers=headers, json=payload
        )
    if r.status_code == 200:
        invoice_url = r.json().get("invoice_url","<no url>")
        kb = ReplyKeyboardMarkup.from_button(
            KeyboardButton("Open Payment Gateway",
                           web_app=WebAppInfo(url=invoice_url))
        )
        await update.message.reply_text(
            "Click button to pay (20-min window).", reply_markup=kb
        )
    else:
        await update.message.reply_text(f"NP error {r.status_code}: {r.text}")

# (other handlers: announce, database conversation, etc. – unchanged)

# ─────────────────── secrets fetch helpers ──────────────────────────────────
def fetch_telegram_token():    # still used by channel-broadcast helper
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("TELEGRAM_BOT_SECRET_NAME")
        return client.access_secret_version(
            request={"name": secret_path}).payload.data.decode()
    except Exception as e:
        logging.error("secret fetch err %s", e); return None

def fetch_payment_provider_token():
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("PAYMENT_PROVIDER_SECRET_NAME")
        return client.access_secret_version(
            request={"name": secret_path}).payload.data.decode()
    except Exception as e:
        logging.error("NP key fetch err %s", e); return None

# ─────────────────── main bootstrap ─────────────────────────────────────────
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_bot))
    application.add_handler(CommandHandler("start_np_gateway_new", start_np_gateway_new))
    # (add other handlers as needed)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    fetch_tele_open_list()
    broadcast_hash_links()
    main()           # starts telegram polling (non-blocking with nest_asyncio)
    app.run(host="0.0.0.0", port=5000)
