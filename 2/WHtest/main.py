import os, time
from typing import Tuple, Dict, Any
from flask import Flask, request, abort, jsonify
from telegram import Bot

# Read the bot token from an env-var injected at deploy time
BOT_TOKEN = os.environ["TELEGRAM_BOT_SECRET_NAME"]

bot = Bot(BOT_TOKEN)
app = Flask(__name__)


def _validate(payload: Dict[str, Any]) -> Tuple[int, int]:
    try:
        uid = int(payload["user_id"])
        cid = int(payload["closed_channel_id"])
    except (KeyError, ValueError, TypeError):
        raise ValueError("payload must contain integer user_id and closed_channel_id")
    return uid, cid


@app.route("/", methods=["POST"])
def send_invite():
    try:
        uid, cid = _validate(request.get_json(force=True, silent=False))
    except ValueError as e:
        abort(400, str(e))

    try:
        invite_link = bot.create_chat_invite_link(
            chat_id=cid,
            expire_date=int(time.time()) + 3600,   # 1 hour TTL
            member_limit=1
        ).invite_link

        bot.send_message(
            uid,
            f"✅ Payment confirmed!\nHere is your one-time invite link:\n{invite_link}",
            disable_web_page_preview=True
        )
    except Exception as e:
        app.logger.error("telegram error: %s", e, exc_info=True)
        abort(500, "telegram error")

    return jsonify(status="ok"), 200


# Run with gunicorn when started locally:  gunicorn -b :8080 main:app
