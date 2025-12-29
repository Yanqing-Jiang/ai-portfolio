"""
Configuration for Generative UI service.
"""

import os
from pydantic_settings import BaseSettings
from typing import Optional
from dataclasses import field



class GenerativeUISettings(BaseSettings):
    """Settings for the Generative UI A2UI service."""
    
    # Claude API (for dashboard planning)
    claude_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", os.getenv("CLAUDE_API_KEY")))
    claude_model: str = "claude-3-5-sonnet-20241022"
    
    # Gemini API (for data synthesis)
    gemini_api_key: Optional[str] = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY")))
    gemini_model: str = "gemini-1.5-pro"
    
    # Database (reuse from main app)
    database_url: Optional[str] = field(default_factory=lambda: os.getenv("DATABASE_URL"))
    
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
    
    class Config:
        env_prefix = "GENUI_"
        env_file = ".env"


# Singleton settings instance
_settings: Optional[GenerativeUISettings] = None


def get_settings() -> GenerativeUISettings:
    """Get the settings singleton."""
    global _settings
    if _settings is None:
        _settings = GenerativeUISettings()
    return _settings
