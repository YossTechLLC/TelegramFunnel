import time
from typing import Tuple, Dict, Any
from flask import Flask, request, abort, jsonify
from telegram import Bot

# ── hard-coded credentials (replace with env/secretmanager in prod) ───────────
BOT_TOKEN = "8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU"

bot = Bot(BOT_TOKEN)
app = Flask(__name__)


def _validate(payload: Dict[str, Any]) -> Tuple[int, int]:
    """
    Ensure payload has two integers: user_id, closed_channel_id.
    Raises ValueError on problems.
    """
    try:
        uid  = int(payload["user_id"])
        cid  = int(payload["closed_channel_id"])
    except (KeyError, ValueError, TypeError):
        raise ValueError("payload must contain integer user_id and closed_channel_id")
    return uid, cid


@app.route("/", methods=["POST"])
def send_invite() -> Tuple[str, int]:
    try:
        uid, cid = _validate(request.get_json(force=True, silent=False))
    except ValueError as e:
        abort(400, str(e))

    try:
        invite_link = bot.create_chat_invite_link(
            chat_id     = cid,
            expire_date = int(time.time()) + 3600,   # 1 hour
            member_limit= 1
        ).invite_link

        bot.send_message(
            chat_id = uid,
            text    = (
                "✅ You’ve been granted access!\n"
                "Here is your one-time invite link:\n"
                f"{invite_link}"
            ),
            disable_web_page_preview=True
        )
    except Exception as e:
        # makes debugging easier in Cloud Logging
        app.logger.error("telegram error: %s", e, exc_info=True)
        abort(500, "telegram error")

    return jsonify(status="ok"), 200
