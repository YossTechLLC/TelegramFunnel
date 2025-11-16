#!/usr/bin/env python
from telegram import Update, Message, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from broadcast_manager import BroadcastManager
from input_handlers import OPEN_CHANNEL_INPUT, DATABASE_CHANNEL_ID_INPUT, DATABASE_EDITING, DATABASE_FIELD_INPUT

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
        
        # Send greeting message with inline keyboard menu (only if no subscription token)
        if not context.args:
            # No subscription token - show inline keyboard menu
            keyboard = [
                [
                    InlineKeyboardButton("💾 DATABASE", callback_data="CMD_DATABASE"),
                    InlineKeyboardButton("💳 PAYMENT GATEWAY", callback_data="CMD_GATEWAY"),
                ],
                [
                    InlineKeyboardButton("🌐 REGISTER", url="https://www.paygateprime.com"),
                ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id,
                f"Hi {user.mention_html()}! 👋\n\n"
                f"Choose an option:",
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        else:
            # Has subscription token - no menu (clean payment flow)
            await context.bot.send_message(
                chat_id,
                f"Hi {user.mention_html()}! 👋",
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
        """Send personalized payment gateway message with closed channel info"""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        # Get closed channel info from database using the global open channel ID
        closed_channel_title = "Premium Channel"  # Default fallback
        closed_channel_description = "exclusive content"  # Default fallback
        
        if self.global_open_channel_id:
            try:
                # We need to get database manager from context to fetch channel info
                from app_initializer import AppInitializer
                # Since we don't have direct access to db_manager here, we'll use a different approach
                # We can get the info from the broadcast manager's cached data
                from broadcast_manager import BroadcastManager
                
                # Get database manager from bot_data if available
                db_manager = context.bot_data.get('db_manager')
                if db_manager:
                    # Fetch channel info directly
                    _, channel_info_map = db_manager.fetch_open_channel_list()
                    channel_data = channel_info_map.get(self.global_open_channel_id, {})
                    if channel_data:
                        closed_channel_title = channel_data.get("closed_channel_title", "Premium Channel")
                        closed_channel_description = channel_data.get("closed_channel_description", "exclusive content")
            except Exception as e:
                print(f"⚠️ [DEBUG] Could not fetch channel info for personalized message: {e}")
        
        # Create payment gateway button with updated text
        keyboard = [[
            InlineKeyboardButton("💰 Launch Payment Gateway", callback_data="TRIGGER_PAYMENT")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send beautifully formatted message
        welcome_text = (
            f"💳 <b>Click the button below to Launch the Payment Gateway</b> 🚀\n\n"
            f"🎯 <b>Get access to:</b> {closed_channel_title}\n"
            f"📝 <b>Description:</b> {closed_channel_description}"
        )
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=welcome_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        print(f"✅ [DEBUG] Sent personalized payment gateway message to user {user.id if user else 'Unknown'}")
    
    def get_global_values(self):
        """Return current global values for use by other modules"""
        return {
            'sub_value': self.global_sub_value,
            'open_channel_id': self.global_open_channel_id,
            'sub_time': self.global_sub_time
        }

    # ═══════════════════════════════════════════════════════════════════
    #  NEW DATABASE FLOW - Inline Form Functions
    # ═══════════════════════════════════════════════════════════════════

    async def show_main_edit_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = True):
        """Display the main editing menu with current channel data summary."""
        channel_data = context.user_data.get("channel_data", {})
        open_channel_id = context.user_data.get("editing_channel_id", "Unknown")

        # Build summary text
        summary_text = (
            f"📝 *Editing Channel: {open_channel_id}*\n\n"
            f"📢 Open: {channel_data.get('open_channel_title', 'Not set')}\n"
            f"🔒 Private: {channel_data.get('closed_channel_title', 'Not set')}\n"
            f"💰 Tiers: "
        )

        # Add tier status
        tier_status = []
        for i in range(1, 4):
            price = channel_data.get(f"sub_{i}_price")
            time = channel_data.get(f"sub_{i}_time")
            status = "✅" if (price is not None and time is not None) else "❌"
            tier_status.append(status)
        summary_text += " ".join(tier_status)

        summary_text += f"\n💳 Wallet: {channel_data.get('client_payout_currency', 'Not set')}"

        # Build inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("📢 Open Channel", callback_data="EDIT_OPEN_CHANNEL"),
                InlineKeyboardButton("🔒 Private Channel", callback_data="EDIT_PRIVATE_CHANNEL"),
            ],
            [
                InlineKeyboardButton("💰 Payment Tiers", callback_data="EDIT_PAYMENT_TIERS"),
                InlineKeyboardButton("💳 Wallet Address", callback_data="EDIT_WALLET"),
            ],
            [
                InlineKeyboardButton("✅ Save All Changes", callback_data="SAVE_ALL_CHANGES"),
                InlineKeyboardButton("❌ Cancel", callback_data="CANCEL_EDIT"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Edit existing message or send new one
        if edit_message and update.callback_query:
            await update.callback_query.edit_message_text(
                text=summary_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=summary_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

    async def show_open_channel_form(self, update: Update, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = True):
        """Display open channel editing form."""
        channel_data = context.user_data.get("channel_data", {})

        form_text = (
            f"📢 *OPEN CHANNEL CONFIGURATION*\n\n"
            f"Channel ID: `{channel_data.get('open_channel_id', 'Not set')}`\n"
            f"Title: {channel_data.get('open_channel_title', 'Not set')}\n"
            f"Description: {channel_data.get('open_channel_description', 'Not set')}"
        )

        keyboard = [
            [InlineKeyboardButton("✏️ Edit Channel ID", callback_data="EDIT_OPEN_CHANNEL_ID")],
            [InlineKeyboardButton("✏️ Edit Title", callback_data="EDIT_OPEN_CHANNEL_TITLE")],
            [InlineKeyboardButton("✏️ Edit Description", callback_data="EDIT_OPEN_CHANNEL_DESC")],
            [
                InlineKeyboardButton("💾 Submit", callback_data="SUBMIT_OPEN_CHANNEL"),
                InlineKeyboardButton("⬅️ Back", callback_data="BACK_TO_MAIN"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        context.user_data["current_form"] = "open_channel"

        if edit_message and update.callback_query:
            await update.callback_query.edit_message_text(
                text=form_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=form_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

    async def show_private_channel_form(self, update: Update, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = True):
        """Display private channel editing form."""
        channel_data = context.user_data.get("channel_data", {})

        form_text = (
            f"🔒 *PRIVATE CHANNEL CONFIGURATION*\n\n"
            f"Channel ID: `{channel_data.get('closed_channel_id', 'Not set')}`\n"
            f"Title: {channel_data.get('closed_channel_title', 'Not set')}\n"
            f"Description: {channel_data.get('closed_channel_description', 'Not set')}"
        )

        keyboard = [
            [InlineKeyboardButton("✏️ Edit Channel ID", callback_data="EDIT_PRIVATE_CHANNEL_ID")],
            [InlineKeyboardButton("✏️ Edit Title", callback_data="EDIT_PRIVATE_CHANNEL_TITLE")],
            [InlineKeyboardButton("✏️ Edit Description", callback_data="EDIT_PRIVATE_CHANNEL_DESC")],
            [
                InlineKeyboardButton("💾 Submit", callback_data="SUBMIT_PRIVATE_CHANNEL"),
                InlineKeyboardButton("⬅️ Back", callback_data="BACK_TO_MAIN"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        context.user_data["current_form"] = "private_channel"

        if edit_message and update.callback_query:
            await update.callback_query.edit_message_text(
                text=form_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=form_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

    async def show_payment_tiers_form(self, update: Update, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = True):
        """Display payment tiers editing form."""
        channel_data = context.user_data.get("channel_data", {})

        form_text = "💰 *PAYMENT TIERS CONFIGURATION*\n\n"

        medals = ["🥇", "🥈", "🥉"]
        names = ["Gold", "Silver", "Bronze"]

        for i in range(1, 4):
            price = channel_data.get(f"sub_{i}_price")
            time = channel_data.get(f"sub_{i}_time")
            status = "✅" if (price is not None and time is not None) else "❌"
            price_display = f"${price:.2f}" if price is not None else "Not set"
            time_display = f"{time} days" if time is not None else "Not set"

            form_text += (
                f"{medals[i-1]} *Tier {i} ({names[i-1]})* {status}\n"
                f"Price: {price_display} | Time: {time_display}\n\n"
            )

        keyboard = []
        for i in range(1, 4):
            price = channel_data.get(f"sub_{i}_price")
            time = channel_data.get(f"sub_{i}_time")
            is_enabled = (price is not None and time is not None)
            toggle_text = "☑️ Disable" if is_enabled else "☑️ Enable"

            keyboard.append([
                InlineKeyboardButton(toggle_text, callback_data=f"TOGGLE_TIER_{i}"),
                InlineKeyboardButton(f"✏️ Edit Tier {i}", callback_data=f"EDIT_TIER_{i}"),
            ])

        keyboard.append([
            InlineKeyboardButton("💾 Submit", callback_data="SUBMIT_PAYMENT_TIERS"),
            InlineKeyboardButton("⬅️ Back", callback_data="BACK_TO_MAIN"),
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        context.user_data["current_form"] = "payment_tiers"

        if edit_message and update.callback_query:
            await update.callback_query.edit_message_text(
                text=form_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=form_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

    async def show_wallet_form(self, update: Update, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = True):
        """Display wallet address editing form."""
        channel_data = context.user_data.get("channel_data", {})

        form_text = (
            f"💳 *WALLET ADDRESS CONFIGURATION*\n\n"
            f"Wallet Address: `{channel_data.get('client_wallet_address', 'Not set')}`\n"
            f"Currency Type: {channel_data.get('client_payout_currency', 'Not set')}"
        )

        keyboard = [
            [InlineKeyboardButton("✏️ Edit Wallet Address", callback_data="EDIT_WALLET_ADDRESS")],
            [InlineKeyboardButton("✏️ Edit Currency Type", callback_data="EDIT_WALLET_CURRENCY")],
            [
                InlineKeyboardButton("💾 Submit", callback_data="SUBMIT_WALLET"),
                InlineKeyboardButton("⬅️ Back", callback_data="BACK_TO_MAIN"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        context.user_data["current_form"] = "wallet"

        if edit_message and update.callback_query:
            await update.callback_query.edit_message_text(
                text=form_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=form_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

    async def handle_database_callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Master callback handler for all database editing callbacks."""
        query = update.callback_query
        await query.answer()
        data = query.data

        print(f"🔘 [CALLBACK] Received: {data}")

        # Main menu callbacks
        if data == "EDIT_OPEN_CHANNEL":
            await self.show_open_channel_form(update, context, edit_message=True)
        elif data == "EDIT_PRIVATE_CHANNEL":
            await self.show_private_channel_form(update, context, edit_message=True)
        elif data == "EDIT_PAYMENT_TIERS":
            await self.show_payment_tiers_form(update, context, edit_message=True)
        elif data == "EDIT_WALLET":
            await self.show_wallet_form(update, context, edit_message=True)
        elif data == "SAVE_ALL_CHANGES":
            await self.save_all_changes(update, context)
        elif data == "CANCEL_EDIT":
            await self.cancel_edit(update, context)

        # Open channel form callbacks
        elif data == "EDIT_OPEN_CHANNEL_ID":
            context.user_data["awaiting_input_for"] = "open_channel_id"
            await query.message.reply_text("Enter new *open_channel_id* (≤14 chars integer):", parse_mode="Markdown")
            return DATABASE_FIELD_INPUT
        elif data == "EDIT_OPEN_CHANNEL_TITLE":
            context.user_data["awaiting_input_for"] = "open_channel_title"
            await query.message.reply_text("Enter new *open channel title* (1-100 chars):", parse_mode="Markdown")
            return DATABASE_FIELD_INPUT
        elif data == "EDIT_OPEN_CHANNEL_DESC":
            context.user_data["awaiting_input_for"] = "open_channel_description"
            await query.message.reply_text("Enter new *open channel description* (1-500 chars):", parse_mode="Markdown")
            return DATABASE_FIELD_INPUT
        elif data == "SUBMIT_OPEN_CHANNEL":
            await self.show_main_edit_menu(update, context, edit_message=True)

        # Private channel form callbacks
        elif data == "EDIT_PRIVATE_CHANNEL_ID":
            context.user_data["awaiting_input_for"] = "closed_channel_id"
            await query.message.reply_text("Enter new *closed_channel_id* (≤14 chars integer):", parse_mode="Markdown")
            return DATABASE_FIELD_INPUT
        elif data == "EDIT_PRIVATE_CHANNEL_TITLE":
            context.user_data["awaiting_input_for"] = "closed_channel_title"
            await query.message.reply_text("Enter new *private channel title* (1-100 chars):", parse_mode="Markdown")
            return DATABASE_FIELD_INPUT
        elif data == "EDIT_PRIVATE_CHANNEL_DESC":
            context.user_data["awaiting_input_for"] = "closed_channel_description"
            await query.message.reply_text("Enter new *private channel description* (1-500 chars):", parse_mode="Markdown")
            return DATABASE_FIELD_INPUT
        elif data == "SUBMIT_PRIVATE_CHANNEL":
            await self.show_main_edit_menu(update, context, edit_message=True)

        # Payment tiers callbacks
        elif data.startswith("TOGGLE_TIER_"):
            tier_num = int(data.split("_")[-1])
            channel_data = context.user_data.get("channel_data", {})
            price = channel_data.get(f"sub_{tier_num}_price")
            time = channel_data.get(f"sub_{tier_num}_time")
            is_enabled = (price is not None and time is not None)

            if is_enabled:
                # Disable tier
                context.user_data["channel_data"][f"sub_{tier_num}_price"] = None
                context.user_data["channel_data"][f"sub_{tier_num}_time"] = None
                print(f"❌ [TIER] Disabled tier {tier_num}")
                await self.show_payment_tiers_form(update, context, edit_message=True)
            else:
                # Enable tier - ask for price
                context.user_data["awaiting_input_for"] = f"sub_{tier_num}_price"
                await query.message.reply_text(
                    f"🥇 *Tier {tier_num} - Enter price* (0-9999.99):",
                    parse_mode="Markdown"
                )
                return DATABASE_FIELD_INPUT

        elif data.startswith("EDIT_TIER_"):
            tier_num = int(data.split("_")[-1])
            context.user_data["awaiting_input_for"] = f"sub_{tier_num}_price"
            await query.message.reply_text(
                f"🥇 *Tier {tier_num} - Enter price* (0-9999.99):",
                parse_mode="Markdown"
            )
            return DATABASE_FIELD_INPUT

        elif data == "SUBMIT_PAYMENT_TIERS":
            await self.show_main_edit_menu(update, context, edit_message=True)

        # Wallet form callbacks
        elif data == "EDIT_WALLET_ADDRESS":
            context.user_data["awaiting_input_for"] = "client_wallet_address"
            await query.message.reply_text("Enter new *wallet address*:", parse_mode="Markdown")
            return DATABASE_FIELD_INPUT
        elif data == "EDIT_WALLET_CURRENCY":
            context.user_data["awaiting_input_for"] = "client_payout_currency"
            await query.message.reply_text("Enter new *payout currency* (e.g., BTC, ETH, USDT):", parse_mode="Markdown")
            return DATABASE_FIELD_INPUT
        elif data == "SUBMIT_WALLET":
            await self.show_main_edit_menu(update, context, edit_message=True)

        # Back button
        elif data == "BACK_TO_MAIN":
            await self.show_main_edit_menu(update, context, edit_message=True)

        # Create new channel
        elif data == "CREATE_NEW_CHANNEL":
            await self.create_new_channel(update, context)

        # Cancel database
        elif data == "CANCEL_DATABASE":
            await self.cancel_edit(update, context)

        return DATABASE_EDITING

    async def save_all_changes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Save all changes to database."""
        editing_channel_id = context.user_data.get("editing_channel_id")
        channel_data = context.user_data.get("channel_data", {})

        print(f"💾 [SAVE] Saving changes for channel {editing_channel_id}")

        # Get database manager from bot_data
        db_manager = context.bot_data.get('db_manager')

        if not db_manager:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Error: Database manager not available"
            )
            context.user_data.clear()
            from telegram.ext import ConversationHandler
            return ConversationHandler.END

        # Update database
        success = db_manager.update_channel_config(editing_channel_id, channel_data)

        if success:
            await update.callback_query.edit_message_text(
                text=(
                    f"✅ *All changes saved successfully!*\n\n"
                    f"Channel: `{editing_channel_id}`\n"
                    f"📢 Open: {channel_data.get('open_channel_title', 'N/A')}\n"
                    f"🔒 Private: {channel_data.get('closed_channel_title', 'N/A')}\n"
                    f"💳 Wallet: {channel_data.get('client_payout_currency', 'N/A')}"
                ),
                parse_mode="Markdown"
            )
        else:
            await update.callback_query.edit_message_text(
                text="❌ Failed to save changes to database."
            )

        context.user_data.clear()
        from telegram.ext import ConversationHandler
        return ConversationHandler.END

    async def cancel_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel editing and clear session."""
        print(f"❌ [CANCEL] User cancelled editing")

        if update.callback_query:
            await update.callback_query.edit_message_text(
                text="❌ Editing cancelled. No changes were saved."
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Editing cancelled. No changes were saved."
            )

        context.user_data.clear()
        from telegram.ext import ConversationHandler
        return ConversationHandler.END

    async def create_new_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create a new channel configuration."""
        pending_channel_id = context.user_data.get("pending_channel_id")

        print(f"✨ [CREATE] Creating new channel: {pending_channel_id}")

        # Initialize empty channel data
        channel_data = {
            "open_channel_id": pending_channel_id,
            "open_channel_title": "New Channel",
            "open_channel_description": "Description",
            "closed_channel_id": "",
            "closed_channel_title": "Private Channel",
            "closed_channel_description": "Description",
            "sub_1_price": None,
            "sub_1_time": None,
            "sub_2_price": None,
            "sub_2_time": None,
            "sub_3_price": None,
            "sub_3_time": None,
            "client_wallet_address": "",
            "client_payout_currency": "USD",
            "client_payout_network": "ETH",
        }

        context.user_data["editing_channel_id"] = pending_channel_id
        context.user_data["channel_data"] = channel_data
        context.user_data["current_form"] = "main"

        await update.callback_query.edit_message_text(
            text=f"✨ Creating new channel configuration for `{pending_channel_id}`\n\n"
            f"All fields are set to defaults. Please configure them now.",
            parse_mode="Markdown"
        )

        await self.show_main_edit_menu(update, context, edit_message=False)

        return DATABASE_EDITING