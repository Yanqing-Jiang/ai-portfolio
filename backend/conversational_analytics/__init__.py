# Conversational Analytics - Claude-powered analytics agent
"""
A Claude Code-like single agent for conversational analytics using Claude Sonnet 4.5.
"""

from .agent import ConversationalAnalyticsAgent
from .config import settings

__all__ = ["ConversationalAnalyticsAgent", "settings"]
