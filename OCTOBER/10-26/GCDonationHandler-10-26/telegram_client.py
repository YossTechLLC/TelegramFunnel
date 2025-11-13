#!/usr/bin/env python
"""
Telegram Client Wrapper for GCDonationHandler
Provides synchronous interface to Telegram Bot API

This module wraps the telegram.Bot API to provide a Flask-compatible
synchronous interface. It is a self-contained module with no internal dependencies.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from telegram import Bot, InlineKeyboardMarkup, WebAppInfo, InlineKeyboardButton
from telegram.error import TelegramError, BadRequest, Forbidden

logger = logging.getLogger(__name__)


class TelegramClient:
    """
    Synchronous wrapper for Telegram Bot API operations.

    This class provides Flask-compatible synchronous methods for common
    Telegram operations. All async operations are wrapped with asyncio.run()
    to ensure compatibility with synchronous Flask handlers.

    Attributes:
        bot: Telegram Bot instance
        bot_token: Bot API token
    """

    def __init__(self, bot_token: str):
        """
        Initialize the TelegramClient with bot token.

        Args:
            bot_token: Telegram bot API token

        Raises:
            ValueError: If bot_token is empty or None
        """
        if not bot_token:
            raise ValueError("Bot token is required")

        self.bot_token = bot_token
        self.bot = Bot(token=bot_token)
        logger.info("📱 TelegramClient initialized")

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        parse_mode: str = "HTML"
    ) -> Dict[str, Any]:
        """
        Send a text message to a chat.

        Args:
            chat_id: Target chat ID
            text: Message text (supports HTML formatting by default)
            reply_markup: Optional inline keyboard markup
            parse_mode: Message parse mode (default: "HTML")

        Returns:
            Dictionary with result:
            {'success': True, 'message_id': int} on success
            {'success': False, 'error': str} on failure

        Example:
            >>> client = TelegramClient(token)
            >>> result = client.send_message(
            ...     chat_id=123456789,
            ...     text="<b>Hello!</b>",
            ...     reply_markup=keyboard
            ... )
            >>> if result['success']:
            ...     print(f"Message sent: {result['message_id']}")
        """
        try:
            async def _send():
                message = await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
                return message

            message = asyncio.run(_send())
            logger.info(f"✅ Message sent to chat {chat_id}, message_id: {message.message_id}")
            return {'success': True, 'message_id': message.message_id}

        except TelegramError as e:
            logger.error(f"❌ Failed to send message to chat {chat_id}: {e}")
            return {'success': False, 'error': str(e)}

    def send_message_with_webapp_button(
        self,
        chat_id: int,
        text: str,
        button_text: str,
        webapp_url: str
    ) -> Dict[str, Any]:
        """
        Send a message with a Web App button.

        This is used for sending payment gateway links after donation confirmation.

        Args:
            chat_id: Target chat ID
            text: Message text
            button_text: Button label text
            webapp_url: URL for the Web App (payment gateway link)

        Returns:
            Dictionary with result:
            {'success': True, 'message_id': int} on success
            {'success': False, 'error': str} on failure

        Example:
            >>> result = client.send_message_with_webapp_button(
            ...     chat_id=123456789,
            ...     text="Complete your donation:",
            ...     button_text="💳 Pay Now",
            ...     webapp_url="https://nowpayments.io/payment/?iid=12345"
            ... )
        """
        try:
            # Create Web App button
            button = InlineKeyboardButton(
                text=button_text,
                web_app=WebAppInfo(url=webapp_url)
            )
            keyboard = InlineKeyboardMarkup([[button]])

            return self.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"❌ Failed to create Web App button: {e}")
            return {'success': False, 'error': str(e)}

    def edit_message_reply_markup(
        self,
        chat_id: int,
        message_id: int,
        reply_markup: Optional[InlineKeyboardMarkup] = None
    ) -> Dict[str, Any]:
        """
        Edit only the reply markup of a message.

        This is used to update the keypad display when user presses buttons.

        Args:
            chat_id: Chat ID where message was sent
            message_id: ID of message to edit
            reply_markup: New inline keyboard markup

        Returns:
            Dictionary with result:
            {'success': True} on success
            {'success': False, 'error': str} on failure

        Example:
            >>> result = client.edit_message_reply_markup(
            ...     chat_id=123456789,
            ...     message_id=456,
            ...     reply_markup=updated_keyboard
            ... )
        """
        try:
            async def _edit():
                await self.bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=reply_markup
                )

            asyncio.run(_edit())
            logger.info(f"✅ Message {message_id} reply markup edited in chat {chat_id}")
            return {'success': True}

        except BadRequest as e:
            # "Message is not modified" is not a real error - keyboard is already up-to-date
            if "message is not modified" in str(e).lower():
                logger.debug(f"Message {message_id} keyboard already up-to-date")
                return {'success': True}
            logger.error(f"❌ Failed to edit message {message_id} in chat {chat_id}: {e}")
            return {'success': False, 'error': str(e)}

        except TelegramError as e:
            logger.error(f"❌ Failed to edit message {message_id} in chat {chat_id}: {e}")
            return {'success': False, 'error': str(e)}

    def delete_message(self, chat_id: int, message_id: int) -> Dict[str, Any]:
        """
        Delete a message.

        Used to clean up temporary keypad messages after donation flow completes.

        Args:
            chat_id: Chat ID where message was sent
            message_id: ID of message to delete

        Returns:
            Dictionary with result:
            {'success': True} on success
            {'success': False, 'error': str} on failure

        Example:
            >>> result = client.delete_message(
            ...     chat_id=123456789,
            ...     message_id=456
            ... )
        """
        try:
            async def _delete():
                await self.bot.delete_message(
                    chat_id=chat_id,
                    message_id=message_id
                )

            asyncio.run(_delete())
            logger.info(f"✅ Message {message_id} deleted from chat {chat_id}")
            return {'success': True}

        except BadRequest as e:
            # Message not found is not a critical error - might have been deleted already
            if "message to delete not found" in str(e).lower():
                logger.debug(f"Message {message_id} already deleted")
                return {'success': True}
            logger.error(f"❌ Failed to delete message {message_id} from chat {chat_id}: {e}")
            return {'success': False, 'error': str(e)}

        except TelegramError as e:
            logger.error(f"❌ Failed to delete message {message_id} from chat {chat_id}: {e}")
            return {'success': False, 'error': str(e)}

    def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False
    ) -> Dict[str, Any]:
        """
        Answer a callback query from an inline button.

        This must be called after receiving a callback query, or Telegram will
        show a loading indicator for up to 30 seconds.

        Args:
            callback_query_id: ID of the callback query to answer
            text: Optional text to show to user (as notification or alert)
            show_alert: If True, shows alert popup instead of notification

        Returns:
            Dictionary with result:
            {'success': True} on success
            {'success': False, 'error': str} on failure

        Example:
            >>> result = client.answer_callback_query(
            ...     callback_query_id="123ABC",
            ...     text="✅ Amount updated",
            ...     show_alert=False
            ... )
        """
        try:
            async def _answer():
                await self.bot.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text=text,
                    show_alert=show_alert
                )

            asyncio.run(_answer())
            logger.debug(f"✅ Answered callback query {callback_query_id}")
            return {'success': True}

        except TelegramError as e:
            logger.error(f"❌ Failed to answer callback query {callback_query_id}: {e}")
            return {'success': False, 'error': str(e)}
