from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import yaml

# Point to shared YAMLs under backend/config/schemas
SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "config" / "schemas"

class Configs:
    def __init__(self) -> None:
        self.queries: Dict[str, Any] = {}
        self.metrics: Dict[str, Any] = {}
        self.charts: Dict[str, Any] = {}
        self.companies: Dict[str, Any] = {}
        self.database: Dict[str, Any] = {}

    def load(self) -> "Configs":
        def _load(name: str) -> Dict[str, Any]:
            p = SCHEMAS_DIR / f"{name}.yaml"
            if p.exists():
                with p.open("r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            return {}
        self.queries = _load("queries")
        self.metrics = _load("metrics")
        self.charts = _load("charts")
        self.companies = _load("companies")
        self.database = _load("database")
        return self

CONFIGS = Configs().load()
