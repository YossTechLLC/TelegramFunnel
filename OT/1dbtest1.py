#!/usr/bin/env python
import psycopg2
import requests
import base64
import threading
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import nest_asyncio

# ───────────────────────────  event-loop patch  ──────────────────────────────
nest_asyncio.apply()

# ─────────────────────────────  flask app  ───────────────────────────────────
app = Flask(__name__)

# ─────────────────────  postgres connection details  ─────────────────────────
DB_HOST = '34.58.246.248'
DB_PORT = 5432
DB_NAME = 'client_table'
DB_USER = 'postgres'
DB_PASSWORD = 'Chigdabeast123$'

# ─────────────────────────  telegram credentials  ────────────────────────────
BOT_TOKEN    = '8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU'
BOT_USERNAME = 'PayGatePrime_bot'

# ───────────────────────────  globals  ───────────────────────────────────────
tele_open_list: list[int] = []

# ───────────────────────────  logging  ───────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
log = logging.getLogger('paygateprime')

# ─────────────────────────  db fetches  ──────────────────────────────────────
def fetch_tele_open_list() -> None:
    global tele_open_list
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASSWORD
        )
        with conn, conn.cursor() as cur:
            cur.execute('SELECT tele_open FROM tele_channel')
            tele_open_list = [row[0] for row in cur.fetchall()]
        log.info('loaded %d channel ids', len(tele_open_list))
    except Exception as exc:
        log.error('failed to load tele_open list: %s', exc)
        tele_open_list = []

# ────────────────────────  message helpers  ─────────────────────────────────
def send_telegram_message(chat_id: int, text: str) -> None:
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        msg_id = r.json()['result']['message_id']
        # schedule deletion in 1 h
        delete_url = f'https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage'
        asyncio.get_event_loop().call_later(
            3600,
            lambda: requests.post(delete_url,
                                  json={'chat_id': chat_id, 'message_id': msg_id},
                                  timeout=10)
        )
    except Exception as exc:
        log.warning('send to %s failed: %s', chat_id, exc)

# ────────────────────────  hash helpers  ────────────────────────────────────
encode_id   = lambda i: base64.urlsafe_b64encode(str(i).encode()).decode()
decode_hash = lambda s: int(base64.urlsafe_b64decode(s.encode()).decode())

def broadcast_hash_links() -> None:
    if not tele_open_list:
        fetch_tele_open_list()
    for cid in tele_open_list:
        h = encode_id(cid)
        link = f'https://t.me/{BOT_USERNAME}?start={h}'
        send_telegram_message(cid, f'Hash: `{h}`\n🔗 [Decode Link]({link})')

# ──────────────────────────  bot handlers  ──────────────────────────────────
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    uid  = update.effective_user.id
    if args:
        try:
            decoded = decode_hash(args[0])
            await update.message.reply_text(
                f'🔓 Decoded ID from hash: `{decoded}`\n👤 User ID: `{uid}`',
                parse_mode='Markdown'
            )
        except Exception as exc:
            await update.message.reply_text(f'❌ decode error: {exc}')
    else:
        await update.message.reply_text(
            'welcome to paygateprime bot – use `/start <hash>` to decode.',
            parse_mode='Markdown'
        )

def make_bot_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start_cmd))
    return app

# ──────────────────────────  flask endpoint  ────────────────────────────────
@app.route('/decode_start')
def decode_start():
    h   = request.args.get('start')
    uid = request.args.get('user_id', 'unknown')
    if not h:
        return 'missing start param', 400
    try:
        cid = decode_hash(h)
        send_telegram_message(
            cid, f'🔓 decoded ID from /start param: {cid}\n👤 user ID: {uid}'
        )
        return f'decoded {cid} for user {uid}', 200
    except Exception as exc:
        return f'error: {exc}', 500

# ──────────────────────────  main routine  ──────────────────────────────────
def start_telegram_bot() -> None:
    bot_app = make_bot_app()
    bot_app.run_polling(allowed_updates=Update.ALL_TYPES)   # blocking inside thread

if __name__ == '__main__':
    fetch_tele_open_list()
    broadcast_hash_links()

    # launch bot in a daemon thread so flask can own main thread
    threading.Thread(target=start_telegram_bot, daemon=True).start()

    # IMPORTANT: disable flask reloader to avoid double-spawn
    app.run(host='0.0.0.0', port=5000, use_reloader=False)
