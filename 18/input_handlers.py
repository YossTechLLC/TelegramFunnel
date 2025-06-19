#!/usr/bin/env python
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database import DatabaseManager, receive_sub3_time_db

# Conversation states for /database
(
    TELE_OPEN_INPUT,
    TELE_CLOSED_INPUT,
    SUB1_INPUT,
    SUB2_INPUT,
    SUB3_INPUT,
    SUB1_TIME_INPUT,
    SUB2_TIME_INPUT,
    SUB3_TIME_INPUT,
) = range(8)

class InputHandlers:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    @staticmethod
    def _valid_channel_id(text: str) -> bool:
        if text.lstrip("-").isdigit():
            return len(text) <= 14
        return False
    
    @staticmethod
    def _valid_sub(text: str) -> bool:
        try:
            val = float(text)
        except ValueError:
            return False
        if not (0 <= val <= 9999.99):
            return False
        parts = text.split(".")
        return len(parts) == 1 or len(parts[1]) <= 2
    
    @staticmethod
    def _valid_time(text: str) -> bool:
        return text.isdigit() and 1 <= int(text) <= 999
    
    async def start_database(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        ctx.user_data.clear()
        await update.message.reply_text("Enter *tele_open* (≤14 chars integer):", parse_mode="Markdown")
        return TELE_OPEN_INPUT
    
    async def receive_tele_open(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if self._valid_channel_id(update.message.text):
            ctx.user_data["tele_open"] = update.message.text.strip()
            await update.message.reply_text("Enter *tele_closed* (≤14 chars integer):", parse_mode="Markdown")
            return TELE_CLOSED_INPUT
        await update.message.reply_text("❌ Invalid tele_open. Try again:")
        return TELE_OPEN_INPUT
    
    async def receive_tele_closed(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if self._valid_channel_id(update.message.text):
            ctx.user_data["tele_closed"] = update.message.text.strip()
            await update.message.reply_text("Enter *sub_1* (0-9999.99):", parse_mode="Markdown")
            return SUB1_INPUT
        await update.message.reply_text("❌ Invalid tele_closed. Try again:")
        return TELE_CLOSED_INPUT
    
    def _sub_handler(self, idx_key: str, next_state: int, prompt: str):
        async def inner(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            if self._valid_sub(update.message.text):
                ctx.user_data[idx_key] = float(update.message.text)
                await update.message.reply_text(prompt, parse_mode="Markdown")
                return next_state
            await update.message.reply_text("❌ Invalid sub value. Try again:")
            return SUB1_INPUT if idx_key == "sub_1" else SUB2_INPUT if idx_key == "sub_2" else SUB3_INPUT
        return inner
    
    def _time_handler(self, idx_key: str, next_state: int, prompt: str):
        async def inner(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            if self._valid_time(update.message.text):
                ctx.user_data[idx_key] = int(update.message.text)
                await update.message.reply_text(prompt, parse_mode="Markdown")
                return next_state
            await update.message.reply_text("❌ Invalid time (1-999). Try again:")
            return SUB1_TIME_INPUT if idx_key == "sub_1_time" else SUB2_TIME_INPUT if idx_key == "sub_2_time" else SUB3_TIME_INPUT
        return inner
    
    def get_handlers(self):
        """Returns all the handler functions as a dictionary"""
        return {
            'receive_sub1': self._sub_handler("sub_1", SUB1_TIME_INPUT, "Enter *sub_1_time* (1-999):"),
            'receive_sub1_time': self._time_handler("sub_1_time", SUB2_INPUT, "Enter *sub_2* (0-9999.99):"),
            'receive_sub2': self._sub_handler("sub_2", SUB2_TIME_INPUT, "Enter *sub_2_time* (1-999):"),
            'receive_sub2_time': self._time_handler("sub_2_time", SUB3_INPUT, "Enter *sub_3* (0-9999.99):"),
            'receive_sub3': self._sub_handler("sub_3", SUB3_TIME_INPUT, "Enter *sub_3_time* (1-999):"),
        }
    
    async def receive_sub3_time(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        return await receive_sub3_time_db(update, ctx, self.db_manager)
    
    async def cancel(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        ctx.user_data.clear()
        await update.message.reply_text("❌ Operation cancelled.")
        return ConversationHandler.END