#!/usr/bin/env python
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database import DatabaseManager, receive_sub3_time_db

# Conversation states for /database and donations
(
    TELE_OPEN_INPUT,
    TELE_CLOSED_INPUT,
    SUB1_INPUT,
    SUB2_INPUT,
    SUB3_INPUT,
    SUB1_TIME_INPUT,
    SUB2_TIME_INPUT,
    SUB3_TIME_INPUT,
    DONATION_AMOUNT_INPUT,
) = range(9)

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
    
    @staticmethod
    def _valid_donation_amount(text: str) -> bool:
        """Validate donation amount (1-9999 USD with max 2 decimal places)"""
        try:
            val = float(text)
        except ValueError:
            return False
        if not (1.0 <= val <= 9999.99):
            return False
        parts = text.split(".")
        return len(parts) == 1 or len(parts[1]) <= 2
    
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
            await update.message.reply_text("Enter *sub_1_price* (0-9999.99):", parse_mode="Markdown")
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
            return SUB1_INPUT if idx_key == "sub_1_price" else SUB2_INPUT if idx_key == "sub_2_price" else SUB3_INPUT
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
            'receive_sub1': self._sub_handler("sub_1_price", SUB1_TIME_INPUT, "Enter *sub_1_time* (1-999):"),
            'receive_sub1_time': self._time_handler("sub_1_time", SUB2_INPUT, "Enter *sub_2_price* (0-9999.99):"),
            'receive_sub2': self._sub_handler("sub_2_price", SUB2_TIME_INPUT, "Enter *sub_2_time* (1-999):"),
            'receive_sub2_time': self._time_handler("sub_2_time", SUB3_INPUT, "Enter *sub_3_price* (0-9999.99):"),
            'receive_sub3': self._sub_handler("sub_3_price", SUB3_TIME_INPUT, "Enter *sub_3_time* (1-999):"),
        }
    
    async def receive_sub3_time(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        return await receive_sub3_time_db(update, ctx, self.db_manager)
    
    async def start_donation_conversation(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Entry point specifically for donation conversation handler from button clicks"""
        print(f"💸 [DEBUG] CMD_DONATE conversation entry point triggered by user {update.effective_user.id if update.effective_user else 'Unknown'}")
        
        # Check if we already have a donation_channel_id set (from token parsing)
        existing_channel_id = ctx.user_data.get("donation_channel_id")
        if not existing_channel_id:
            # Set donation context for menu-based donations (no specific channel)
            ctx.user_data["donation_channel_id"] = "donation_default"
            print(f"🎯 [DEBUG] Set donation_channel_id to 'donation_default' for menu-based donation")
        else:
            print(f"🔗 [DEBUG] Using existing donation_channel_id: {existing_channel_id} (likely from token)")
        
        # Start the donation conversation
        return await self.start_donation(update, ctx)
    
    async def start_donation(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Start the donation conversation by asking for amount"""
        print(f"🚀 [DEBUG] Starting donation conversation for user: {update.effective_user.id if update.effective_user else 'Unknown'}")
        
        # Handle both regular messages and callback queries
        if update.callback_query:
            message = update.callback_query.message
            # Only answer if callback query is valid and not already answered
            try:
                await ctx.bot.answer_callback_query(update.callback_query.id)
                print("🔄 [DEBUG] Processing donation start from callback query")
            except Exception as e:
                print(f"⚠️ [DEBUG] Callback query already answered or invalid: {e}")
                print("ℹ️ [DEBUG] Processing donation start from callback query (callback answer skipped)")
            
            # Set up donation context from menu handlers when starting from button
            menu_handlers = ctx.bot_data.get('menu_handlers')
            if menu_handlers:
                if menu_handlers.global_open_channel_id:
                    ctx.user_data["donation_channel_id"] = menu_handlers.global_open_channel_id
                    print(f"🎯 [DEBUG] Set donation_channel_id from global: {menu_handlers.global_open_channel_id}")
                else:
                    # No specific channel context, use default for menu-based donations
                    ctx.user_data["donation_channel_id"] = "donation_default"
                    print(f"ℹ️ [DEBUG] No global channel ID, using donation_default")
        else:
            message = update.message
            print("💬 [DEBUG] Processing donation start from message")
        
        # Check if we have a donation channel ID from token-based access or menu context
        donation_channel_id = ctx.user_data.get("donation_channel_id")
        
        # If no channel ID from token, try to get a default one from menu handlers
        if not donation_channel_id:
            menu_handlers = ctx.bot_data.get('menu_handlers')
            if menu_handlers and menu_handlers.global_open_channel_id:
                donation_channel_id = menu_handlers.global_open_channel_id
                ctx.user_data["donation_channel_id"] = donation_channel_id
                print(f"🎯 [DEBUG] Using global channel ID for donation: {donation_channel_id}")
            else:
                print("⚠️ [DEBUG] No channel ID available, donation will require manual setup")
        else:
            print(f"🔗 [DEBUG] Using context channel ID for donation: {donation_channel_id}")
        
        await message.reply_text(
            "💝 *How much would you like to donate?*\n\n"
            "Please enter an amount in USD (e.g., 25.50)\n"
            "Range: $1.00 - $9999.99",
            parse_mode="Markdown"
        )
        return DONATION_AMOUNT_INPUT
    
    async def receive_donation_amount(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Process and validate the donation amount"""
        amount_text = update.message.text.strip()
        print(f"💰 [DEBUG] Received donation amount input: '{amount_text}' from user {update.effective_user.id if update.effective_user else 'Unknown'}")
        
        # Remove $ symbol if user included it
        if amount_text.startswith('$'):
            amount_text = amount_text[1:]
            print(f"💲 [DEBUG] Removed $ symbol, amount now: '{amount_text}'")
        
        if self._valid_donation_amount(amount_text):
            donation_amount = float(amount_text)
            print(f"✅ [DEBUG] Valid donation amount: ${donation_amount:.2f}")
            
            # Store donation amount and trigger payment gateway
            ctx.user_data["donation_amount"] = donation_amount
            print(f"💾 [DEBUG] Stored donation amount in user_data: {ctx.user_data.get('donation_amount')}")
            
            await update.message.reply_text(
                f"✅ *Donation Amount: ${donation_amount:.2f}*\n\n"
                "Preparing your payment gateway...",
                parse_mode="Markdown"
            )
            
            # Complete the donation by triggering payment gateway
            print(f"🚀 [DEBUG] Proceeding to complete donation")
            return await self.complete_donation(update, ctx)
        else:
            print(f"❌ [DEBUG] Invalid donation amount: '{amount_text}'")
            await update.message.reply_text(
                "❌ Invalid amount. Please enter a valid donation amount between $1.00 and $9999.99\n"
                "Examples: 25, 10.50, 100.99"
            )
            return DONATION_AMOUNT_INPUT
    
    async def complete_donation(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Complete the donation by setting global values and triggering payment"""
        # Get the donation amount
        donation_amount = ctx.user_data.get("donation_amount")
        channel_id = ctx.user_data.get("donation_channel_id")
        
        print(f"🏁 [DEBUG] Completing donation: amount={donation_amount}, channel_id={channel_id}")
        
        if not donation_amount:
            await update.message.reply_text("❌ Donation amount missing. Please try again.")
            ctx.user_data.clear()
            return ConversationHandler.END
        
        # Handle missing channel ID gracefully
        if not channel_id:
            print("🔍 [DEBUG] No channel ID found, attempting to get default from database")
            
            # Try to get a default channel ID from database (first available open channel)
            try:
                db_manager = ctx.bot_data.get('db_manager')
                if db_manager:
                    default_channel = db_manager.get_default_donation_channel()
                    if default_channel:
                        channel_id = default_channel
                        ctx.user_data["donation_channel_id"] = channel_id
                        print(f"🎯 [DEBUG] Using default donation channel: {channel_id}")
                    else:
                        print("⚠️ [DEBUG] No default channel available in database")
                else:
                    print("❌ [DEBUG] db_manager not available in bot_data")
            except Exception as e:
                print(f"❌ [DEBUG] Error getting default channel: {e}")
            
            # If still no channel ID, inform user but continue with a placeholder
            if not channel_id:
                await update.message.reply_text(
                    "⚠️ *No Channel Configuration Found*\n\n"
                    "This donation will use default settings. "
                    "For channel-specific donations, please use a proper donation link.",
                    parse_mode="Markdown"
                )
                # Use a placeholder channel ID that can be handled by the payment system
                channel_id = "donation_default"  # This will be handled as a special case
                ctx.user_data["donation_channel_id"] = channel_id
                print(f"📍 [DEBUG] Using placeholder channel ID: {channel_id}")
        
        # Get menu handlers instance from bot data to set global values
        menu_handlers = ctx.bot_data.get('menu_handlers')
        if menu_handlers:
            # Set global values in menu handlers (same as subscription flow)
            # For donations, use a special time value (365 days = 1 year access)
            donation_time = 365
            print(f"⚙️ [DEBUG] Setting global values: sub_value={donation_amount}, channel_id={channel_id}, sub_time={donation_time}")
            menu_handlers.global_sub_value = donation_amount
            menu_handlers.global_open_channel_id = channel_id
            menu_handlers.global_sub_time = donation_time
            print(f"✅ [DEBUG] Global values set: sub_value={menu_handlers.global_sub_value}, channel_id={menu_handlers.global_open_channel_id}, sub_time={menu_handlers.global_sub_time}")
        else:
            print("⚠️ [DEBUG] Warning: menu_handlers not found in bot_data")
        
        # Trigger payment gateway (reuse existing payment flow)
        payment_gateway_handler = ctx.bot_data.get('payment_gateway_handler')
        if payment_gateway_handler:
            print("🚀 [DEBUG] Triggering payment gateway for donation")
            await payment_gateway_handler(update, ctx)
        else:
            print("❌ [DEBUG] Error: payment_gateway_handler not found in bot_data")
            await update.message.reply_text("❌ Unable to process donation. Please try again later.")
        
        ctx.user_data.clear()
        return ConversationHandler.END
    
    async def cancel(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        print(f"❌ [DEBUG] Conversation cancelled by user {update.effective_user.id if update.effective_user else 'Unknown'}")
        ctx.user_data.clear()
        await update.message.reply_text("❌ Operation cancelled.")
        return ConversationHandler.END