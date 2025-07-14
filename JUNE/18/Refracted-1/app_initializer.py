#!/usr/bin/env python
import logging
import nest_asyncio
from config_manager import ConfigManager
from database import DatabaseManager
from secure_webhook import SecureWebhookManager
from start_np_gateway import PaymentGatewayManager
from broadcast_manager import BroadcastManager
from input_handlers import InputHandlers
from menu_handlers import MenuHandlers
from bot_manager import BotManager
from message_utils import MessageUtils

class AppInitializer:
    def __init__(self):
        # Setup logging
        logging.getLogger("httpx").setLevel(logging.WARNING)
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
            level=logging.INFO
        )
        
        # Apply nest_asyncio for Flask compatibility
        nest_asyncio.apply()
        
        # Initialize configuration
        self.config_manager = ConfigManager()
        self.config = None
        
        # Initialize managers
        self.db_manager = None
        self.webhook_manager = None
        self.payment_manager = None
        self.broadcast_manager = None
        self.input_handlers = None
        self.menu_handlers = None
        self.bot_manager = None
        self.message_utils = None
    
    def initialize(self):
        """Initialize all application components."""
        # Get configuration
        self.config = self.config_manager.initialize_config()
        
        if not self.config['bot_token']:
            raise RuntimeError("Bot token is required to start the application")
        
        # Initialize core managers
        self.db_manager = DatabaseManager()
        self.webhook_manager = SecureWebhookManager()
        self.payment_manager = PaymentGatewayManager()
        self.input_handlers = InputHandlers(self.db_manager)
        self.message_utils = MessageUtils(self.config['bot_token'])
        
        # Initialize broadcast manager
        self.broadcast_manager = BroadcastManager(
            self.config['bot_token'], 
            self.config['bot_username'], 
            self.db_manager
        )
        
        # Create payment gateway wrapper function
        async def payment_gateway_wrapper(update, context):
            print(f"[DEBUG] Payment gateway wrapper called for user: {update.effective_user.id if update.effective_user else 'Unknown'}")
            global_values = self.menu_handlers.get_global_values() if self.menu_handlers else {
                'sub_value': 5.0, 
                'open_channel_id': ''
            }
            print(f"[DEBUG] Payment gateway using global values: {global_values}")
            await self.payment_manager.start_np_gateway_new(
                update, context, 
                global_values['sub_value'], 
                global_values['open_channel_id'],
                self.webhook_manager, 
                self.db_manager
            )
        
        # Initialize menu handlers and bot manager
        self.menu_handlers = MenuHandlers(self.input_handlers, payment_gateway_wrapper)
        self.bot_manager = BotManager(
            self.input_handlers, 
            self.menu_handlers.main_menu_callback, 
            self.menu_handlers.start_bot, 
            payment_gateway_wrapper,
            self.menu_handlers,
            self.db_manager
        )
        
        # Initialize broadcast data
        if self.broadcast_manager:
            self.broadcast_manager.fetch_tele_open_list()
            self.broadcast_manager.broadcast_hash_links()
    
    async def run_bot(self):
        """Run the Telegram bot."""
        if not self.bot_manager:
            raise RuntimeError("Bot manager not initialized. Call initialize() first.")
        
        await self.bot_manager.run_telegram_bot(
            telegram_token=self.config['bot_token'],
            payment_token=self.payment_manager.payment_token
        )
    
    def get_managers(self):
        """Get all initialized managers for external use."""
        return {
            'db_manager': self.db_manager,
            'webhook_manager': self.webhook_manager,
            'payment_manager': self.payment_manager,
            'broadcast_manager': self.broadcast_manager,
            'input_handlers': self.input_handlers,
            'menu_handlers': self.menu_handlers,
            'bot_manager': self.bot_manager,
            'message_utils': self.message_utils
        }