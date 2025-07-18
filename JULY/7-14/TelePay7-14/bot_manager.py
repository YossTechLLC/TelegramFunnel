#!/usr/bin/env python
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler,
)
from input_handlers import InputHandlers, OPEN_CHANNEL_INPUT, CLOSED_CHANNEL_INPUT, SUB1_INPUT, SUB2_INPUT, SUB3_INPUT, SUB1_TIME_INPUT, SUB2_TIME_INPUT, SUB3_TIME_INPUT, DONATION_AMOUNT_INPUT

class BotManager:
    def __init__(self, input_handlers: InputHandlers, menu_callback_handler, start_bot_handler, payment_gateway_handler, menu_handlers=None, db_manager=None):
        self.input_handlers = input_handlers
        self.menu_callback_handler = menu_callback_handler
        self.start_bot_handler = start_bot_handler
        self.payment_gateway_handler = payment_gateway_handler
        self.menu_handlers = menu_handlers
        self.db_manager = db_manager
    
    def setup_handlers(self, application: Application):
        """Set up all bot handlers"""
        # Get handler functions from input_handlers
        handlers = self.input_handlers.get_handlers()
        
        # Accept both /database and CMD_DATABASE button to start conversation
        database_handler = ConversationHandler(
            entry_points=[
                CommandHandler("database", self.input_handlers.start_database),
                CallbackQueryHandler(self.menu_callback_handler, pattern="^CMD_DATABASE$"),
            ],
            states={
                OPEN_CHANNEL_INPUT   : [MessageHandler(filters.TEXT & ~filters.COMMAND, self.input_handlers.receive_open_channel)],
                CLOSED_CHANNEL_INPUT : [MessageHandler(filters.TEXT & ~filters.COMMAND, self.input_handlers.receive_closed_channel)],
                SUB1_INPUT        : [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers['receive_sub1'])],
                SUB1_TIME_INPUT   : [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers['receive_sub1_time'])],
                SUB2_INPUT        : [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers['receive_sub2'])],
                SUB2_TIME_INPUT   : [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers['receive_sub2_time'])],
                SUB3_INPUT        : [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers['receive_sub3'])],
                SUB3_TIME_INPUT   : [MessageHandler(filters.TEXT & ~filters.COMMAND, self.input_handlers.receive_sub3_time)],
            },
            fallbacks=[CommandHandler("cancel", self.input_handlers.cancel)],
            per_message=False,  # This is default, warning can be ignored or silenced
        )
        
        # Donation conversation handler
        donation_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.input_handlers.start_donation_conversation, pattern="^CMD_DONATE$"),
            ],
            states={
                DONATION_AMOUNT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.input_handlers.receive_donation_amount)],
            },
            fallbacks=[CommandHandler("cancel", self.input_handlers.cancel)],
            per_message=False,
        )
        
        # Add all handlers
        application.add_handler(database_handler)
        application.add_handler(donation_handler)
        application.add_handler(CommandHandler("start", self.start_bot_handler))
        application.add_handler(CommandHandler("start_np_gateway_new", self.payment_gateway_handler))
        application.add_handler(CallbackQueryHandler(self.trigger_payment_handler, pattern="^TRIGGER_PAYMENT$"))
        application.add_handler(CallbackQueryHandler(self.menu_callback_handler, pattern="^(?!CMD_DATABASE|CMD_DONATE|TRIGGER_PAYMENT).*$"))
        
        # Add hamburger menu handler
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex("^(🚀 Start|💾 Database|💳 Payment Gateway|💝 Donate)$"),
            self.menu_handlers.handle_menu_selection
        ))
    
    async def run_telegram_bot(self, telegram_token: str, payment_token: str):
        """Main bot runner function"""
        if not telegram_token:
            raise RuntimeError("Bot cannot start: TELEGRAM_BOT_SECRET_NAME is missing or invalid.")
        if not payment_token:
            raise RuntimeError("Bot cannot start: PAYMENT_PROVIDER_SECRET_NAME is missing or invalid.")

        application = Application.builder().token(telegram_token).build()
        
        # Store references in bot_data for donation flow  
        application.bot_data['menu_handlers'] = self.menu_handlers
        application.bot_data['payment_gateway_handler'] = self.payment_gateway_handler
        application.bot_data['db_manager'] = self.db_manager
        print(f"⚙️ [DEBUG] Bot data setup: menu_handlers={self.menu_handlers is not None}, payment_handler={self.payment_gateway_handler is not None}, db_manager={self.db_manager is not None}")
        
        # Setup all handlers
        self.setup_handlers(application)
        
        # Start polling
        await application.run_polling(allowed_updates=Update.ALL_TYPES)
    
    async def trigger_payment_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle TRIGGER_PAYMENT callback - directly invoke payment gateway"""
        print(f"💳 [DEBUG] TRIGGER_PAYMENT callback received from user {update.effective_user.id if update.effective_user else 'Unknown'}")
        
        try:
            # Answer the callback query first
            await context.bot.answer_callback_query(update.callback_query.id)
            
            # Trigger the payment gateway handler directly
            await self.payment_gateway_handler(update, context)
            print(f"✅ [DEBUG] Payment gateway triggered successfully")
            
        except Exception as e:
            print(f"❌ [DEBUG] Error triggering payment gateway: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Error processing payment. Please try again."
            )