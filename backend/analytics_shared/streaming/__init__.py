"""
Lightweight Event Streaming Shared Module

Contains shared event streaming utilities for lightweight, efficient event emission
used by both analytics_memory and analytics_supervisor systems.
"""

from .events import (
    StreamEvent,
    EventEmitter,
    TimedEventEmitter,
    emit_progress,
    emit_result,
    emit_error
)

__all__ = [
    'StreamEvent',
    'EventEmitter',
    'TimedEventEmitter',
    'emit_progress',
    'emit_result',
    'emit_error'
]