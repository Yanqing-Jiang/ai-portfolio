"""
Analytics Shared Module

This module contains shared functionality between analytics_memory and analytics_supervisor systems.
It aims to eliminate code duplication while maintaining system independence.
"""

__version__ = "1.0.0"

# Core shared modules
from . import intent
from . import sql
from . import charting
from . import database
from . import companies
from . import streaming

__all__ = [
    'intent',
    'sql',
    'charting',
    'database',
    'companies',
    'streaming'
]