#!/usr/bin/env python
"""
Minimal orchestrator for the Telegram Payment Bot.
This file coordinates all the modular components.
"""
import asyncio
import logging
import os
from pathlib import Path
from threading import Thread
from dotenv import load_dotenv
from app_initializer import AppInitializer
from server_manager import ServerManager
from PGP_COMMON.logging import setup_logger

# Initialize logger with LOG_LEVEL environment variable support
logger = setup_logger(__name__)

# Load environment variables from .env file (if it exists)
# This must happen BEFORE any modules try to access environment variables
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    logger.info(f"✅ [CONFIG] Loaded environment variables from {env_path}")
else:
    logger.info(f"⚠️ [CONFIG] No .env file found at {env_path} - using system environment variables")

async def run_application(app):
    """Run both the Telegram bot and subscription monitoring concurrently."""
    try:
        # Create both tasks
        bot_task = asyncio.create_task(app.run_bot())
        subscription_task = asyncio.create_task(app.subscription_manager.start_monitoring())

        # Run both tasks concurrently
        await asyncio.gather(bot_task, subscription_task)

    except Exception as e:
        logger.error(f"❌ [APP] Error in application tasks: {e}", exc_info=True)
        # Stop subscription monitoring if it's running
        if hasattr(app, 'subscription_manager'):
            app.subscription_manager.stop_monitoring()
        raise

def main():
    """Main entry point for the application."""
    try:
        # Initialize the application
        app = AppInitializer()
        app.initialize()

        # 🆕 NEW_ARCHITECTURE: Start Flask server with security and services
        managers = app.get_managers()
        flask_app = managers.get('flask_app')

        if flask_app:
            logger.info("✅ Starting Flask server with NEW_ARCHITECTURE (security enabled)")
            # Run Flask in separate thread
            def run_flask():
                flask_app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')))

            flask_thread = Thread(target=run_flask, daemon=True)
            flask_thread.start()
        else:
            # Fallback to old ServerManager if flask_app not available
            logger.warning("⚠️ Flask app not found - using legacy ServerManager")
            server = ServerManager()
            if hasattr(app, 'notification_service') and app.notification_service:
                server.set_notification_service(app.notification_service)
                logger.info("✅ Notification service configured in Flask server")
            flask_thread = Thread(target=server.start, daemon=True)
            flask_thread.start()

        # Run the Telegram bot and subscription monitoring
        asyncio.run(run_application(app))
        
    except KeyboardInterrupt:
        logger.info("👋 Shutting down gracefully. Goodbye!")
        # Stop subscription monitoring gracefully
        try:
            if 'app' in locals() and hasattr(app, 'subscription_manager'):
                app.subscription_manager.stop_monitoring()
        except:
            pass
    except Exception as e:
        logger.error(f"❌ Application error: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()