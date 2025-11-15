#!/usr/bin/env python
"""
Message Formatter for GCBotCommand
Format messages for Telegram (for code reuse)
"""
from typing import Dict

class MessageFormatter:
    """Format messages for Telegram"""

    @staticmethod
    def format_subscription_message(channel_title: str, channel_description: str, price: float, time: int) -> str:
        """Format subscription payment message"""
        return (
            f"💳 <b>Click the button below to Launch the Payment Gateway</b> 🚀\n\n"
            f"🎯 <b>Get access to:</b> {channel_title}\n"
            f"📝 <b>Description:</b> {channel_description}\n"
            f"💰 <b>Price:</b> ${price:.2f}\n"
            f"📅 <b>Duration:</b> {time} days"
        )

    @staticmethod
    def format_donation_message(amount: float) -> str:
        """Format donation confirmation message"""
        return (
            f"✅ *Donation Amount: ${amount:.2f}*\n\n"
            f"Click the button below to complete your donation:"
        )

    @staticmethod
    def format_database_menu_message() -> str:
        """Format database configuration menu text"""
        return (
            "💾 *DATABASE CONFIGURATION*\n\n"
            "Enter *open_channel_id* (≤14 chars integer):"
        )

    @staticmethod
    def format_error_message(error_text: str) -> str:
        """Format error message with ❌ emoji"""
        return f"❌ {error_text}"

    @staticmethod
    def format_payment_invoice_message(price: float, time: int) -> str:
        """Format payment invoice message"""
        return (
            f"💰 *Payment Invoice Created*\n\n"
            f"Amount: ${price:.2f}\n"
            f"Duration: {time} days\n\n"
            f"Click the button below to complete payment:"
        )
