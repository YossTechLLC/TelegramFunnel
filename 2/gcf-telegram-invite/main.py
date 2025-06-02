import os, time, json
from telegram import Bot
from functions_framework import http

BOT_TOKEN = "8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU"
bot = Bot(BOT_TOKEN)

@http
def send_invite(request):
    payload = request.get_json(silent=True) or {}
    try:
        uid  = int(payload["user_id"])
        cid  = int(payload["closed_channel_id"])
    except Exception:
        return ("payload must contain integer user_id and closed_channel_id", 400)

    invite = bot.create_chat_invite_link(
        chat_id=cid,
        expire_date=int(time.time()) + 3600,
        member_limit=1
    ).invite_link

    bot.send_message(uid,
        f"✅ Access granted!\nHere is your one-time link:\n{invite}",
        disable_web_page_preview=True
    )
    return ("ok", 200)
