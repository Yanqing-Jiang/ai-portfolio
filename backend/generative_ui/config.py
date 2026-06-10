"""
Configuration for Generative UI service.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load env from backend/.env and backend/generative_ui/.env (if present) so the
# agent can reuse CLAUDE_API_KEY/GENUI_* when launched via uvicorn.
_MODULE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=_MODULE_DIR.parent / ".env", override=False)
load_dotenv(dotenv_path=_MODULE_DIR / ".env", override=False)


class GenerativeUISettings(BaseSettings):
    """Settings for the Generative UI A2UI service."""
    model_config = SettingsConfigDict(
        env_prefix="GENUI_",
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
    )
    
    # Claude API (for dashboard planning)
    # Checks multiple env var names for compatibility with different deployment platforms
    claude_api_key: Optional[str] = (
        os.getenv("GENUI_CLAUDE_API_KEY") or 
        os.getenv("CLAUDE_API_KEY") or   # Main application convention
        os.getenv("ANTHROPIC_API_KEY")   # Fallback for other platforms
    )
    claude_model: str = os.getenv("GENUI_CLAUDE_MODEL", "claude-haiku-4-5-20251001")
    
    # Database (reuse from main app)
    database_url: Optional[str] = None
    
    # A2UI Configuration
    a2ui_version: str = "0.8"
    default_surface_id: str = "dashboard_main"
    
    # Catalog
    catalog_id: str = "https://yoursite.com/a2ui/financial-catalog/v1.0"
    standard_catalog_id: str = "https://github.com/google/A2UI/blob/main/specification/0.8/json/standard_catalog_definition.json"
    
    # Limits
    max_widgets_per_dashboard: int = 12
    max_data_rows: int = 1000
    max_chart_points: int = 500
    
    # Debug
    debug_mode: bool = True
    


# Singleton settings instance
_settings: Optional[GenerativeUISettings] = None


def get_settings() -> GenerativeUISettings:
    """
    Function: get_settings — called from generative_ui.agent and routes.dashboard;
    returns singleton settings configured from environment; exists to centralize
    Claude/database config for the A2UI service.
    """
    global _settings
    if _settings is None:
        _settings = GenerativeUISettings()
    return _settings
