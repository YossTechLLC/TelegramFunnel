#!/usr/bin/env python
"""
Minimal orchestrator for the Telegram Payment Bot.
This file coordinates all the modular components.
"""
import asyncio
from threading import Thread
from app_initializer import AppInitializer
from server_manager import ServerManager

async def run_application(app):
    """Run both the Telegram bot and subscription monitoring concurrently."""
    try:
        # Create both tasks
        bot_task = asyncio.create_task(app.run_bot())
        subscription_task = asyncio.create_task(app.subscription_manager.start_monitoring())
        
        # Run both tasks concurrently
        await asyncio.gather(bot_task, subscription_task)
        
    except Exception as e:
        print(f"❌ Error in application tasks: {e}")
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
        
        # Start Flask server in background thread
        server = ServerManager()
        flask_thread = Thread(target=server.start, daemon=True)
        flask_thread.start()
        
        # Run the Telegram bot and subscription monitoring
        asyncio.run(run_application(app))
        
    except KeyboardInterrupt:
        print("👋\nShutting down gracefully. Goodbye!")
        # Stop subscription monitoring gracefully
        try:
            if 'app' in locals() and hasattr(app, 'subscription_manager'):
                app.subscription_manager.stop_monitoring()
        except:
            pass
    except Exception as e:
        print(f"❌ Application error: {e}")
        raise

if __name__ == "__main__":
    main()