#!/usr/bin/env python
"""
API blueprints package.
Organizes Flask endpoints into modular blueprints.
"""
from flask import Blueprint

# Import blueprints
from .webhooks import webhooks_bp
from .health import health_bp

# Export blueprints
__all__ = ['webhooks_bp', 'health_bp']
