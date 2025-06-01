#!/usr/bin/env python3
"""
send_one_time_invite.py
────────────────────────
• creates a one-time, 1-hour invite link for channel  -1002470187705
• sends it to user 7163367091 from @PayGatePrime_bot
"""

import time
from telegram import Bot

BOT_TOKEN   = "8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU"
CHANNEL_ID  = -1002470187705      # TLFX private channel
TARGET_USER = 7163367091          # receiver's Telegram user_id

def main() -> None:
    bot = Bot(BOT_TOKEN)

    # create a link that expires in 1 hour and can be used only once
    invite_link = bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        expire_date=int(time.time()) + 3600,   # 3600 s = 1 h from now
        member_limit=1
    ).invite_link

    # send it to the target user
    bot.send_message(
        chat_id=TARGET_USER,
        text=(
            "✅ You’ve been granted access!\n"
            "Here is your one-time invite link:\n"
            f"{invite_link}"
        ),
        disable_web_page_preview=True
    )

    print("Invite link sent successfully.")

if __name__ == "__main__":
    main()
