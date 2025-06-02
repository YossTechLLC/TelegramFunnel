import time
import asyncio
from typing import Tuple
from flask import Flask, request, abort, jsonify
from telegram import Bot

app = Flask(__name__)

@app.route("/success_inv", methods=['GET', 'POST'])
def success_inv() -> Tuple[str, int]:
    from telegram import Bot  # local import in case you modularize

    BOT_TOKEN = "8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU"
    bot = Bot(BOT_TOKEN)

    # extract and validate url parameters
    user_id = request.args.get("user_id", type=int)
    closed_channel_id = request.args.get("closed_channel_id", type=int)

    if user_id is None or closed_channel_id is None:
        abort(400, "missing or invalid user_id and/or closed_channel_id in url parameters")

    try:
        async def run_invite():
            invite = await bot.create_chat_invite_link(
                chat_id=closed_channel_id,
                expire_date=int(time.time()) + 3600,
                member_limit=1
            )
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "✅ you’ve been granted access!\n"
                    "here is your one-time invite link:\n"
                    f"{invite.invite_link}"
                ),
                disable_web_page_preview=True
            )

        asyncio.run(run_invite())

    except Exception as e:
        app.logger.error("telegram error: %s", e, exc_info=True)
        abort(500, "telegram error")

    return jsonify(status="ok"), 200
