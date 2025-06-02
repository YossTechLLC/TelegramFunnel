#!/usr/bin/env python3
"""
send_one_time_invite.py
────────────────────────
• asynchronously creates a one-time 1-hour invite link for channel  -1002470187705
• DMs the link to user 7163367091 from @PayGatePrime_bot
"""

import time, asyncio
from telegram import Bot

BOT_TOKEN   = "8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU"
CHANNEL_ID  = -1002470187705      # private channel
TARGET_USER = 7163367091          # recipient user_id

async def main() -> None:
    bot = Bot(BOT_TOKEN)

    # create one-time invite (coroutine → await)
    invite = await bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        expire_date=int(time.time()) + 3600,   # expires in 1 h
        member_limit=1
    )

    # DM it to the user
    await bot.send_message(
        chat_id=TARGET_USER,
        text=(
            "✅ You’ve been granted access!\n"
            "Here is your one-time invite link:\n"
            f"{invite.invite_link}"
        ),
        disable_web_page_preview=True
    )

    print("Invite link sent successfully.")

if __name__ == "__main__":
    asyncio.run(main())
