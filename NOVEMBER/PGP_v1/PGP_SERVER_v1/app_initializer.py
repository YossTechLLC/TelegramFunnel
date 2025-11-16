#!/usr/bin/env python
import logging
import nest_asyncio
import os

# Core managers (keep these - no new versions yet)
from config_manager import ConfigManager
from secure_webhook import SecureWebhookManager
from broadcast_manager import BroadcastManager
from message_utils import MessageUtils
from subscription_manager import SubscriptionManager
from closed_channel_manager import ClosedChannelManager

# 🆕 NEW_ARCHITECTURE: Modular architecture imports
from database import DatabaseManager  # Refactored to use ConnectionPool internally
from services import init_payment_service, init_notification_service
from bot.handlers import register_command_handlers
from bot.conversations import create_donation_conversation_handler
from bot.utils import keyboards as bot_keyboards

# Keep old imports temporarily for gradual migration
from input_handlers import InputHandlers
from menu_handlers import MenuHandlers
from bot_manager import BotManager

# Legacy imports (will be removed after full migration)
from donation_input_handler import DonationKeypadHandler  # TODO: Migrate to bot.conversations (kept for backward compatibility)
# from start_np_gateway import PaymentGatewayManager  # REPLACED by services.PaymentService
# ✅ REMOVED: notification_service.py (Phase 1 consolidation complete - using services.NotificationService)

from telegram import Bot  # For bot initialization

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
        self.payment_manager = None  # Legacy (will use payment_service)
        self.broadcast_manager = None
        self.input_handlers = None
        self.menu_handlers = None
        self.bot_manager = None
        self.message_utils = None
        self.subscription_manager = None
        self.closed_channel_manager = None
        self.donation_handler = None
        self.notification_service = None  # Will use new modular version

        # 🆕 NEW_ARCHITECTURE: New components
        self.security_config = None
        self.payment_service = None  # New modular payment service
        self.flask_app = None  # Flask app with security
    
    def initialize(self):
        """Initialize all application components."""
        # Get configuration
        self.config = self.config_manager.initialize_config()

        if not self.config['bot_token']:
            raise RuntimeError("Bot token is required to start the application")

        # 🆕 NEW_ARCHITECTURE: Initialize security configuration
        self.security_config = self._initialize_security_config()
        self.logger.info("✅ Security configuration loaded")

        # Initialize core managers
        self.db_manager = DatabaseManager()  # Now uses ConnectionPool internally
        self.webhook_manager = SecureWebhookManager()

        # 🆕 NEW_ARCHITECTURE: Initialize new services
        self.logger.info("🆕 Initializing NEW_ARCHITECTURE services...")

        # Initialize payment service with database manager (Phase 2 migration complete)
        self.payment_service = init_payment_service(database_manager=self.db_manager)
        self.logger.info("✅ Payment Service initialized with database integration")
        self.logger.info("✅ Phase 2: Payment Service now has ALL features from OLD implementation")

        # ✅ REMOVED: PaymentGatewayManager (Phase 2 consolidation complete - using services.PaymentService)
        # OLD start_np_gateway.py functionality now fully migrated to services/payment_service.py
        self.input_handlers = InputHandlers(self.db_manager)
        self.message_utils = MessageUtils(self.config['bot_token'])
        
        # Initialize broadcast manager
        self.broadcast_manager = BroadcastManager(
            self.config['bot_token'],
            self.config['bot_username'],
            self.db_manager
        )

        # Initialize closed channel manager for donations
        self.closed_channel_manager = ClosedChannelManager(
            self.config['bot_token'],
            self.db_manager
        )
        self.logger.info("✅ Closed Channel Manager initialized")

        # Initialize donation input handler
        self.donation_handler = DonationKeypadHandler(
            self.db_manager
        )
        self.logger.info("✅ Donation Input Handler initialized")

        # Create payment gateway wrapper function
        async def payment_gateway_wrapper(update, context):
            print(f"🔄 [DEBUG] Payment gateway wrapper called for user: {update.effective_user.id if update.effective_user else 'Unknown'}")
            global_values = self.menu_handlers.get_global_values() if self.menu_handlers else {
                'sub_value': 5.0,
                'open_channel_id': '',
                'sub_time': 30
            }
            print(f"🎯 [DEBUG] Payment gateway using global values: {global_values}")
            # ✅ Phase 2: Now using NEW payment_service with FULL OLD functionality
            await self.payment_service.start_np_gateway_new(
                update, context,
                global_values['sub_value'],
                global_values['open_channel_id'],
                global_values['sub_time'],
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
            self.db_manager,
            self.donation_handler
        )
        
        # Initialize subscription manager with configurable check interval
        import os
        check_interval = int(os.getenv("SUBSCRIPTION_CHECK_INTERVAL", "60"))
        self.subscription_manager = SubscriptionManager(
            bot_token=self.config['bot_token'],
            db_manager=self.db_manager,
            check_interval=check_interval
        )
        self.logger.info(f"✅ Subscription Manager initialized (check_interval: {check_interval}s)")

        # 🆕 NEW_ARCHITECTURE: Initialize notification service (modular version)
        bot_instance = Bot(token=self.config['bot_token'])
        self.notification_service = init_notification_service(
            bot=bot_instance,
            db_manager=self.db_manager
        )
        self.logger.info("✅ Notification Service initialized (NEW_ARCHITECTURE)")

        # Initialize broadcast data
        if self.broadcast_manager:
            self.broadcast_manager.fetch_open_channel_list()
            self.broadcast_manager.broadcast_hash_links()

        # Send donation messages to closed channels
        if self.closed_channel_manager:
            import asyncio
            self.logger.info("📨 Sending donation messages to closed channels...")
            result = asyncio.run(self.closed_channel_manager.send_donation_message_to_closed_channels())
            self.logger.info(f"✅ Donation broadcast complete: {result['successful']}/{result['total_channels']} successful")

        # 🆕 NEW_ARCHITECTURE: Initialize Flask server with security
        self._initialize_flask_app()

    def _initialize_security_config(self) -> dict:
        """
        Initialize security configuration for Flask server.

        🆕 NEW_ARCHITECTURE: Loads security settings for HMAC, IP whitelist, rate limiting.

        Returns:
            Security configuration dictionary
        """
        from google.cloud import secretmanager
        import secrets as python_secrets

        # Fetch webhook signing secret from Secret Manager
        try:
            client = secretmanager.SecretManagerServiceClient()

            # Try to fetch webhook signing secret
            try:
                secret_path = os.getenv("WEBHOOK_SIGNING_SECRET_NAME")
                if secret_path:
                    response = client.access_secret_version(request={"name": secret_path})
                    webhook_signing_secret = response.payload.data.decode("UTF-8").strip()
                    self.logger.info("✅ Webhook signing secret loaded from Secret Manager")
                else:
                    # Generate a temporary secret for development
                    webhook_signing_secret = python_secrets.token_hex(32)
                    self.logger.warning("⚠️ WEBHOOK_SIGNING_SECRET_NAME not set - using temporary secret (DEV ONLY)")
            except Exception as e:
                # Fallback: generate temporary secret
                webhook_signing_secret = python_secrets.token_hex(32)
                self.logger.warning(f"⚠️ Could not fetch webhook signing secret: {e}")
                self.logger.warning("⚠️ Using temporary secret (DEV ONLY)")

        except Exception as e:
            self.logger.error(f"❌ Error initializing security config: {e}")
            # Use a temporary secret for development
            webhook_signing_secret = python_secrets.token_hex(32)
            self.logger.warning("⚠️ Using temporary webhook signing secret (DEV ONLY)")

        # Get allowed IPs from environment or use defaults
        allowed_ips_str = os.getenv('ALLOWED_IPS', '127.0.0.1,10.0.0.0/8')
        allowed_ips = [ip.strip() for ip in allowed_ips_str.split(',')]

        # Get rate limit config from environment
        rate_limit_per_minute = int(os.getenv('RATE_LIMIT_PER_MINUTE', '10'))
        rate_limit_burst = int(os.getenv('RATE_LIMIT_BURST', '20'))

        config = {
            'webhook_signing_secret': webhook_signing_secret,
            'allowed_ips': allowed_ips,
            'rate_limit_per_minute': rate_limit_per_minute,
            'rate_limit_burst': rate_limit_burst
        }

        self.logger.info(f"🔒 [SECURITY] Configured:")
        self.logger.info(f"   Allowed IPs: {len(allowed_ips)} ranges")
        self.logger.info(f"   Rate limit: {rate_limit_per_minute} req/min, burst {rate_limit_burst}")

        return config

    def _initialize_flask_app(self):
        """
        Initialize Flask app with security config and services.

        🆕 NEW_ARCHITECTURE: Creates Flask app with security layers active.
        """
        from server_manager import create_app

        # Create Flask app with security config
        self.flask_app = create_app(self.security_config)

        # Store services in Flask app context for blueprint access
        self.flask_app.config['notification_service'] = self.notification_service
        self.flask_app.config['payment_service'] = self.payment_service
        self.flask_app.config['database_manager'] = self.db_manager

        self.logger.info("✅ Flask server initialized with security")
        self.logger.info("   HMAC: enabled")
        self.logger.info("   IP Whitelist: enabled")
        self.logger.info("   Rate Limiting: enabled")

    async def run_bot(self):
        """Run the Telegram bot."""
        if not self.bot_manager:
            raise RuntimeError("Bot manager not initialized. Call initialize() first.")

        await self.bot_manager.run_telegram_bot(
            telegram_token=self.config['bot_token'],
            payment_token=self.payment_service.api_key  # Phase 2: Using NEW payment_service
        )
    
    def get_managers(self):
        """
        Get all initialized managers for external use.

        🆕 NEW_ARCHITECTURE: Now includes new modular services and Flask app.
        ✅ Phase 2: payment_manager removed, payment_service is now the single source
        """
        return {
            # Core managers
            'db_manager': self.db_manager,
            'webhook_manager': self.webhook_manager,
            'broadcast_manager': self.broadcast_manager,
            'input_handlers': self.input_handlers,
            'menu_handlers': self.menu_handlers,
            'bot_manager': self.bot_manager,
            'message_utils': self.message_utils,

            # 🆕 NEW_ARCHITECTURE: Modular services (Phase 1 & 2 complete)
            'payment_service': self.payment_service,  # Phase 2: COMPLETE - replaced payment_manager
            'notification_service': self.notification_service,  # Phase 1: COMPLETE - replaced notification_service
            'flask_app': self.flask_app,
            'security_config': self.security_config
        }