import os, time
from telegram import Bot
from functions_framework import http

BOT_TOKEN = "8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU"
bot = Bot(BOT_TOKEN)

@http
def send_invite(request):
    try:
        uid = int(request.args.get("uid"))
        cid = int(request.args.get("cid"))
        if uid is None or cid is None:
            raise ValueError("Missing required query parameters.")
    except Exception as e:
        return (f"error: {str(e)}", 400)

    try:
        invite = bot.create_chat_invite_link(
            chat_id=cid,
            expire_date=int(time.time()) + 3600,
            member_limit=1
        ).invite_link

        bot.send_message(
            uid,
            f"✅ Access granted!\nHere is your one-time link:\n{invite}",
            disable_web_page_preview=True
        )
        return ("ok", 200)

    except Exception as e:
        return (f"telegram error: {str(e)}", 500)
