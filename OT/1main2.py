#!/usr/bin/env python
"""
paygateprime unified stack
──────────────────────────
• broadcasts hash+sub links to each channel
• /start handles both <hash>_<sub> tokens and “payload-cmd” deep-links
• user’s chosen sub value is cached per-chat (ctx.user_data["price_usd"])
• /start_np_gateway_new creates a NowPayments invoice *on-the-fly*
  using that cached price
"""

# ── imports ────────────────────────────────────────────────────────────────
import os, base64, asyncio, logging, secrets, json
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── configuration ───────────────────────────────────────────────────────────
DB_CFG = dict(host="34.58.246.248", port=5432, dbname="client_table",
              user="postgres", password="Chigdabeast123$")

TLFX_PRIVATE_CHANNEL_ID = -1002398681722
INVITE_LIFETIME_SEC     = 3600
CALLBACK_URL            = "https://us-central1-rikky-telebot1.cloudfunctions.net/simplecallback"

TELEGRAM_SECRET  = os.getenv("TELEGRAM_BOT_SECRET_NAME")
NOWPAY_SECRET    = os.getenv("PAYMENT_PROVIDER_SECRET_NAME")
NOW_SIG_SECRET   = os.getenv("NOWPAYMENTS_WEBHOOK_SECRET")        # raw secret string

def gcp_secret(path: str) -> str | None:
    try:
        cli = secretmanager.SecretManagerServiceClient()
        return cli.access_secret_version(request={"name": path}).payload.data.decode()
    except Exception as e:
        logging.error("secret %s error: %s", path, e); return None

BOT_TOKEN      = gcp_secret(TELEGRAM_SECRET)
NOWPAY_API_KEY = gcp_secret(NOWPAY_SECRET)

BOT_USERNAME = "PayGatePrime_bot"

# ── globals (channel data) ──────────────────────────────────────────────────
tele_open_list: list[int] = []
tele_info_map: dict[int, dict[str, int | None]] = {}

encode_id = lambda i: base64.urlsafe_b64encode(str(i).encode()).decode()
decode_hash = lambda s: int(base64.urlsafe_b64decode(s.encode()).decode())

# ── database helpers ────────────────────────────────────────────────────────
def load_channels() -> None:
    tele_open_list.clear(); tele_info_map.clear()
    with psycopg2.connect(**DB_CFG) as c, c.cursor() as cur:
        cur.execute("SELECT tele_open, sub_1, sub_2, sub_3 FROM tele_channel")
        for cid, s1, s2, s3 in cur.fetchall():
            tele_open_list.append(cid)
            tele_info_map[cid] = {"sub_1": s1, "sub_2": s2, "sub_3": s3}

# ── telegram utility ────────────────────────────────────────────────────────
def tg_send(chat: int, html: str, ttl: int = 900):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": chat, "text": html,
                  "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=10,
        ); r.raise_for_status()
        msg_id = r.json()["result"]["message_id"]
        asyncio.get_event_loop().call_later(
            ttl,
            lambda: requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage",
                json={"chat_id": chat, "message_id": msg_id}, timeout=5
            )
        )
    except Exception as e:
        logging.error("tg send error to %s: %s", chat, e)

# ── broadcast hash+sub links to every channel ───────────────────────────────
def broadcast_links():
    if not tele_open_list:
        load_channels()
    for cid in tele_open_list:
        subs = tele_info_map.get(cid, {})
        base = encode_id(cid)
        lines = ["<b>decode links:</b>"]
        for key in ("sub_1", "sub_2", "sub_3"):
            val = subs.get(key)
            if val is None: continue
            token = f"{base}_{val}"
            url   = f"https://t.me/{BOT_USERNAME}?start={token}"
            lines.append(f"• {key} <b>{val}</b> → <a href=\"{escape(url)}\">link</a>")
        tg_send(cid, "\n".join(lines))

# ── NowPayments invoice helper ──────────────────────────────────────────────
async def make_invoice(chat_id: int, usd_amount: float) -> str:
    order = f"{encode_id(chat_id)}::{secrets.token_hex(3)}"
    payload = {
        "price_amount":  usd_amount,
        "price_currency":"USD",
        "order_id":      order,
        "order_description":"TLFX1c subscription",
        "ipn_callback_url": CALLBACK_URL,
        "success_url":     CALLBACK_URL,
        "cancel_url":      CALLBACK_URL,
    }
    headers = {"x-api-key": NOWPAY_API_KEY, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as cli:
        r = await cli.post("https://api.nowpayments.io/v1/invoice",
                           headers=headers, json=payload)
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code}: {r.text}")
    return r.json()["invoice_url"]

# ── /start handler ──────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("send /start <hash_sub> or deep link")
        return

    token = ctx.args[0]

    # style 1: <hash>_<sub>
    if "_" in token and not "-" in token:
        h, sub = token.split("_", 1)
        try:
            cid  = decode_hash(h)
            price = float(sub)
            ctx.user_data["price_usd"] = price
            await update.message.reply_text(
                f"ID <code>{cid}</code>\nsub value <code>{price}</code>",
                parse_mode="HTML")
        except Exception as e:
            await update.message.reply_text(f"decode err: {e}")
        return

    # style 2: <payload>-<cmd>
    if "-" in token:
        try:
            payload, cmd = token.rsplit("-", 1)
            user_id, chat_id = payload.split("-", 1)
            await update.message.reply_text(
                f"🔍 Parsed user_id {user_id}, channel_id {chat_id}")
            if cmd == "start_np_gateway_new":
                await start_np_gateway_new(update, ctx)
            elif cmd == "database":
                await start_db(update, ctx)
            return
        except Exception as e:
            await update.message.reply_text(f"parse error {e}")
            return

    await update.message.reply_text("unrecognised token")

# ── pay button handler ──────────────────────────────────────────────────────
async def start_np_gateway_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    price = ctx.user_data.get("price_usd", 20.0)
    try:
        url = await make_invoice(update.effective_user.id, price)
        kb = ReplyKeyboardMarkup.from_button(
            KeyboardButton(text="Open Payment Gateway",
                           web_app=WebAppInfo(url=url))
        )
        await update.message.reply_text(
            f"Invoice for ${price:.2f} created. Click button to pay.",
            reply_markup=kb)
    except Exception as e:
        await update.message.reply_text(f"invoice error: {e}")

# ── announce deep-links command ─────────────────────────────────────────────
async def announce(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid, cid = str(update.effective_user.id), str(update.effective_chat.id)
    payload  = quote(f"{uid}-{cid}")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Pay $20",
         url=f"https://t.me/{BOT_USERNAME}?start={payload}-start_np_gateway_new")]
    ])
    await update.message.reply_text("invite links:", reply_markup=kb)

# ── optional /database conversation (abbreviated) ───────────────────────────
ID_INPUT, NAME_INPUT, AGE_INPUT = range(3)
async def start_db(u:Update,ctx:ContextTypes.DEFAULT_TYPE):
    ctx.user_data["db"]=True; await u.message.reply_text("id:"); return ID_INPUT
async def recv_id(u:Update,ctx:ContextTypes.DEFAULT_TYPE):
    ctx.user_data["id"]=int(u.message.text); await u.message.reply_text("name:"); return NAME_INPUT
async def recv_name(u:Update,ctx:ContextTypes.DEFAULT_TYPE):
    ctx.user_data["name"]=u.message.text; await u.message.reply_text("age:"); return AGE_INPUT
async def recv_age(u:Update,ctx:ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("saved"); ctx.user_data.clear(); return ConversationHandler.END
async def cancel(u:Update,ctx:ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear(); await u.message.reply_text("cancelled"); return ConversationHandler.END

# ── webhook for NowPayments (only stub shown; add signature check if needed) ─
@app.route("/np_webhook", methods=["POST"])
def np_webhook():
    data = request.json or {}
    if data.get("payment_status") != "finished":
        return "ignored", 200
    # confirm, create invite, DM user... (logic omitted for brevity)
    return "ok", 200

# ── bootstrap ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not BOT_TOKEN or not NOWPAY_API_KEY:
        raise RuntimeError("missing secrets")

    load_channels()
    broadcast_links()

    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
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
    app.run(host="0.0.0.0", port=5000)
