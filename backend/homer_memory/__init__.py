"""Public-safe Homer memory search demo.

This package contains a static, sanitized corpus about Homer's architecture.
It never reads the real Homer database or private memory files.
"""

from .routes import router

__all__ = ["router"]
