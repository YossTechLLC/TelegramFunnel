#!/usr/bin/env python
import psycopg2, requests, base64, asyncio
from html import escape
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import nest_asyncio

nest_asyncio.apply()
app = Flask(__name__)

# ── config ──────────────────────────────────────────────────────────────────
DB_HOST, DB_PORT, DB_NAME = "34.58.246.248", 5432, "client_table"
DB_USER, DB_PASSWORD     = "postgres", "Chigdabeast123$"
BOT_TOKEN                = "8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU"
BOT_USERNAME             = "PayGatePrime_bot"

# ── globals ─────────────────────────────────────────────────────────────────
tele_open_list: list[int]                         = []
tele_info_map: dict[int, dict[str, int | None]]  = {}

# ── helper lambdas ──────────────────────────────────────────────────────────
encode_id = lambda i: base64.urlsafe_b64encode(str(i).encode()).decode()
decode_hash = lambda s: int(base64.urlsafe_b64decode(s.encode()).decode())

# ── db fetch ────────────────────────────────────────────────────────────────
def fetch_tele_open_list() -> None:
    tele_open_list.clear()
    tele_info_map.clear()
    try:
        with psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASSWORD
        ) as conn, conn.cursor() as cur:
            cur.execute("SELECT tele_open, sub_1, sub_2, sub_3 FROM tele_channel")
            for tele_open, s1, s2, s3 in cur.fetchall():
                tele_open_list.append(tele_open)
                tele_info_map[tele_open] = {"sub_1": s1, "sub_2": s2, "sub_3": s3}
    except Exception as e:
        print("db error:", e)

# ── telegram send ───────────────────────────────────────────────────────────
def send_message(chat_id: int, html_text: str) -> None:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": html_text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        r.raise_for_status()
        msg_id = r.json()["result"]["message_id"]
        # auto-delete after 15 s
        del_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
        asyncio.get_event_loop().call_later(
            15,
            lambda: requests.post(
                del_url,
                json={"chat_id": chat_id, "message_id": msg_id},
                timeout=5,
            ),
        )
    except Exception as e:
        print(f"❌ send error to {chat_id}: {e}")

# ── broadcast ───────────────────────────────────────────────────────────────
def broadcast_hash_links() -> None:
    if not tele_open_list:
        fetch_tele_open_list()

    for chat_id in tele_open_list:
        subs      = tele_info_map.get(chat_id, {})
        base_hash = encode_id(chat_id)

        lines = ["<b>decode links:</b>"]
        for key in ("sub_1", "sub_2", "sub_3"):
            val = subs.get(key)
            if val is None:
                continue
            token = f"{base_hash}_{val}"
            url   = f"https://t.me/{BOT_USERNAME}?start={token}"
            lines.append(
                f"• {escape(key)} <b>{val}</b> → <a href=\"{escape(url)}\">link</a>"
            )

        send_message(chat_id, "\n".join(lines))   # newline, no <br>

# ── /start handler ──────────────────────────────────────────────────────────
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "welcome – use /start &lt;hash_sub&gt; to decode.", parse_mode="HTML"
        )
        return
    try:
        token = context.args[0]
        hash_part, _, sub_part = token.partition("_")
        cid  = decode_hash(hash_part)
        sub  = sub_part if sub_part else "n/a"
        await update.message.reply_text(
            f"🔓 Decoded ID: <code>{cid}</code>\n"
            f"👤 User ID: <code>{update.effective_user.id}</code>\n"
            f"📦 sub value: <code>{escape(sub)}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ decode error: {e}")

def make_bot() -> Application:
    bot = Application.builder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start_cmd))
    return bot

# ── flask endpoint (optional) ───────────────────────────────────────────────
@app.route("/decode_start")
def decode_start():
    token = request.args.get("start")
    user  = request.args.get("user_id", "unknown")
    if not token:
        return "missing start", 400
    try:
        h, _, sub = token.partition("_")
        cid = decode_hash(h)
        send_message(
            cid,
            f"🔓 decoded ID: <code>{cid}</code>\n"
            f"👤 user: <code>{escape(user)}</code>\n"
            f"📦 sub value: <code>{escape(sub or 'n/a')}</code>",
        )
        return "ok", 200
    except Exception as e:
        return f"err {e}", 500

# ── main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    fetch_tele_open_list()
    broadcast_hash_links()

    bot_app = make_bot()
    loop = asyncio.get_event_loop()
    loop.create_task(bot_app.run_polling())

    app.run(host="0.0.0.0", port=5000)
