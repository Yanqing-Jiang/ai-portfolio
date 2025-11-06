from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import yaml

# Point to shared YAMLs under backend/config/schemas
SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "config" / "schemas"


class Configs:
    def __init__(self) -> None:
        self.queries: Dict[str, Any] = {}
        self.query_requirements: Dict[str, Any] = {}
        self.metrics: Dict[str, Any] = {}
        self.charts: Dict[str, Any] = {}
        self.companies: Dict[str, Any] = {}
        self.database: Dict[str, Any] = {}
        self.semantic: Dict[str, Any] = {}
        self.agents: Dict[str, Any] = {}
        self.agent_feature_flags: Dict[str, Any] = {}

    def load(self) -> "Configs":
        def _load(name: str) -> Dict[str, Any]:
            path = SCHEMAS_DIR / f"{name}.yaml"
            if path.exists():
                with path.open("r", encoding="utf-8") as handle:
                    return yaml.safe_load(handle) or {}
            return {}

        self.queries = _load("queries")
        self.query_requirements = _load("query_requirements")
        self.metrics = _load("metrics")
        self.charts = _load("charts")
        self.companies = _load("companies")

        semantic_section = self.metrics.get("semantic", {}) if isinstance(self.metrics, dict) else {}
        database_fallback = _load("database")

        if isinstance(semantic_section, dict) and semantic_section:
            self.database = semantic_section
            self.semantic = semantic_section
        else:
            self.database = database_fallback
            self.semantic = database_fallback if isinstance(database_fallback, dict) else {}

        agents_blob = _load("agents")
        self.agents = agents_blob.get("agents", {}) if isinstance(agents_blob, dict) else {}
        self.agent_feature_flags = agents_blob.get("feature_flags", {}) if isinstance(agents_blob, dict) else {}

        return self


CONFIGS = Configs().load()
