#!/usr/bin/env python
from telegram import Update, Message, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from broadcast_manager import BroadcastManager
from input_handlers import OPEN_CHANNEL_INPUT

class MenuHandlers:
    def __init__(self, input_handlers, payment_gateway_handler):
        self.input_handlers = input_handlers
        self.payment_gateway_handler = payment_gateway_handler
        self.global_sub_value = 5.0
        self.global_open_channel_id = ""
        self.global_sub_time = 30  # Default subscription time in days
    
    def create_hamburger_menu(self):
        """Create hamburger menu with ReplyKeyboardMarkup"""
        keyboard = [
            [KeyboardButton("🚀 Start"), KeyboardButton("💾 Database")],
            [KeyboardButton("💳 Payment Gateway"), KeyboardButton("💝 Donate")]
        ]
        return ReplyKeyboardMarkup(
            keyboard, 
            resize_keyboard=True, 
            one_time_keyboard=False,
            input_field_placeholder="Choose an option..."
        )
    
    async def handle_menu_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle hamburger menu selections"""
        message_text = update.message.text
        chat_id = update.effective_chat.id
        
        if message_text == "🚀 Start":
            await context.bot.send_message(chat_id, "✅ You clicked Start!")
        elif message_text == "💾 Database":
            # Start database conversation
            await self.input_handlers.start_database(update, context)
        elif message_text == "💳 Payment Gateway":
            await self.payment_gateway_handler(update, context)
        elif message_text == "💝 Donate":
            # Start donation conversation
            await self.input_handlers.start_donation_conversation(update, context)
        else:
            # Unknown menu option
            await context.bot.send_message(chat_id, "❌ Unknown menu option. Please use the menu buttons.")
    
    async def main_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle main menu button callbacks"""
        query = update.callback_query
        await query.answer()
        data = query.data
        chat_id = query.message.chat.id
        
        if data == "CMD_START":
            await context.bot.send_message(chat_id, "You clicked Start!")
        elif data == "CMD_DATABASE":
            # DO NOT edit the message! Just send prompt for input.
            await context.bot.send_message(
                chat_id,
                "Enter *open_channel_id* (≤14 chars integer):",
                parse_mode="Markdown"
            )
            return OPEN_CHANNEL_INPUT
        elif data == "CMD_GATEWAY":
            await self.payment_gateway_handler(update, context)
        elif data == "CMD_DONATE":
            # This should not be reached as CMD_DONATE is handled by ConversationHandler
            print(f"⚠️ [DEBUG] CMD_DONATE reached menu callback handler - this shouldn't happen!")
            await context.bot.send_message(chat_id, "Please try the donation button again.")
        else:
            await context.bot.send_message(chat_id, "Unknown command.")
    
    async def start_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command and token parsing"""
        chat_id = update.effective_chat.id
        user = update.effective_user
        args = context.args[0] if context.args else None

        if args and '-' in args:
            try:
                chat_part, channel_part, cmd = args.split('-', 2)
                await context.bot.send_message(
                    chat_id,
                    f"🔍 Parsed open_channel_id: {chat_part}, channel_id: {channel_part}",
                )
                if cmd == "start_np_gateway_new":
                    await self.payment_gateway_handler(update, context)
                    return
                elif cmd == "database":
                    await self.input_handlers.start_database(update, context)
                    return
            except Exception as e:
                await context.bot.send_message(chat_id, f"❌ could not parse command: {e}")
        
        # Send greeting message with hamburger menu (only if no subscription token)
        if not context.args:
            # No subscription token - show hamburger menu
            reply_markup = self.create_hamburger_menu()
            await context.bot.send_message(
                chat_id,
                rf"Hi {user.mention_html()}! 👋",
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        else:
            # Has subscription token - no menu (clean payment flow)
            await context.bot.send_message(
                chat_id,
                rf"Hi {user.mention_html()}! 👋",
                parse_mode="HTML",
            )
        
        # Handle token parsing for payment
        if not context.args:
            return
        
        try:
            token = context.args[0]
            hash_part, _, remaining_part = token.partition("_")
            open_channel_id = BroadcastManager.decode_hash(hash_part)
            self.global_open_channel_id = open_channel_id  # always a string!
            
            # Check if this is a donation token
            if remaining_part == "DONATE":
                print(f"🎯 [DEBUG] Donation token detected: channel_id={open_channel_id}")
                # Store channel ID for donation and start donation conversation
                context.user_data["donation_channel_id"] = open_channel_id
                # Also set global channel ID for consistency
                self.global_open_channel_id = open_channel_id
                print(f"⚙️ [DEBUG] Set donation context: channel_id={open_channel_id}")
                
                # For token-based donations, we need to simulate the CMD_DONATE callback
                # to properly enter the ConversationHandler state machine
                print(f"🚀 [DEBUG] Triggering donation conversation handler for token-based donation")
                
                # Create a fake callback query to trigger the ConversationHandler properly
                # This simulates clicking the CMD_DONATE button
                fake_callback = CallbackQuery(
                    id="donation_token_callback",
                    from_user=update.effective_user,
                    message=update.message,
                    data="CMD_DONATE",
                    chat_instance=str(update.effective_chat.id)
                )
                
                # Create new update with callback query
                fake_update = Update(
                    update_id=update.update_id + 1000000,
                    callback_query=fake_callback
                )
                
                # Process this fake update to trigger the ConversationHandler
                await context.application.process_update(fake_update)
                return
            
            # Handle regular subscription tokens with format: {hash}_{price}_{time}
            # Split remaining part into price and time
            if "_" in remaining_part:
                sub_part, time_part = remaining_part.rsplit("_", 1)  # Split from right to handle prices with underscores
                try:
                    local_sub_time = int(time_part)
                    self.global_sub_time = local_sub_time
                    print(f"📅 [DEBUG] Parsed subscription time: {local_sub_time} days")
                except ValueError:
                    print(f"⚠️ [DEBUG] Invalid subscription time '{time_part}', using default: {self.global_sub_time}")
            else:
                # Fallback for old token format without time
                sub_part = remaining_part
                print(f"ℹ️ [DEBUG] Old token format detected, using default subscription time: {self.global_sub_time}")
            
            # Parse subscription value
            sub_raw = sub_part.replace("d", ".") if sub_part else "n/a"
            try:
                local_sub_value = float(sub_raw)
            except ValueError:
                local_sub_value = 15.0
            self.global_sub_value = local_sub_value
            print(f"💰 [DEBUG] Parsed subscription: ${local_sub_value:.2f} for {self.global_sub_time} days")
            
            # For subscription tokens, immediately trigger payment gateway (skip amount input)
            print(f"🚀 [DEBUG] Triggering direct payment for subscription tier")
            await self.send_payment_gateway_ready(update, context)
            return
            
        except Exception as e:
            await context.bot.send_message(chat_id, f"❌ decode error: {e}")
    
    async def send_payment_gateway_ready(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send 'Payment Gateway Ready' message with payment button for subscription tiers"""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        chat_id = update.effective_chat.id
        
        # Create payment gateway button
        keyboard = [[
            InlineKeyboardButton("💰 Payment Gateway", callback_data="TRIGGER_PAYMENT")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send the "Payment Gateway Ready" message
        await context.bot.send_message(
            chat_id=chat_id,
            text="💳 Payment Gateway Ready",
            reply_markup=reply_markup
        )
        print(f"✅ [DEBUG] Sent Payment Gateway Ready message to user {update.effective_user.id if update.effective_user else 'Unknown'}")
    
    def get_global_values(self):
        """Return current global values for use by other modules"""
        return {
            'sub_value': self.global_sub_value,
            'open_channel_id': self.global_open_channel_id,
            'sub_time': self.global_sub_time
        }