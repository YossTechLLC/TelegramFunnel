#!/usr/bin/env python
"""
Bot handlers package.
Contains command handlers and callback query handlers.
"""
from .command_handler import register_command_handlers

__all__ = ['register_command_handlers']
