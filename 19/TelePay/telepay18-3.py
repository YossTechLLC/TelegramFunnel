#!/usr/bin/env python
"""
Minimal orchestrator for the Telegram Payment Bot.
This file coordinates all the modular components.
"""
import asyncio
from threading import Thread
from app_initializer import AppInitializer
from server_manager import ServerManager

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
        
        # Run the Telegram bot
        asyncio.run(app.run_bot())
        
    except KeyboardInterrupt:
        print("\nShutting down gracefully. Goodbye!")
    except Exception as e:
        print(f"Application error: {e}")
        raise

if __name__ == "__main__":
    main()