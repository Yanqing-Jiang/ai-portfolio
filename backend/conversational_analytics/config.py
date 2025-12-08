"""Configuration for Conversational Analytics agent."""
from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv


def _load_env() -> None:
    """Load environment variables from .env file."""
    backend_dir = Path(__file__).resolve().parents[1]
    env_path = backend_dir / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)


_load_env()


@dataclass
class Settings:
    """Application settings loaded from environment."""
    
    # Claude API
    claude_api_key: str = field(default_factory=lambda: os.getenv("CLAUDE_API_KEY", ""))
    claude_model: str = "claude-sonnet-4-20250514"
    
    # Database
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    
    # Session settings
    session_ttl_seconds: int = 3600  # 1 hour
    max_history_messages: int = 50
    
    # Tool settings
    sql_timeout_seconds: float = 15.0
    
    def validate(self) -> None:
        """Validate required settings are present."""
        if not self.claude_api_key:
            raise ValueError("CLAUDE_API_KEY environment variable is required")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")


settings = Settings()
