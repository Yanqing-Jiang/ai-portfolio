import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, BACKEND_ROOT):
    entry_str = str(entry)
    if entry_str not in sys.path:
        sys.path.insert(0, entry_str)

from backend.analytics.core.config_store import ConfigResult, ConfigSource
from backend.analytics.tools.registry import SupervisorTools


class StubConfigStore:
    async def get_templates(self, **_kwargs):
        return ConfigResult(data=[{"id": "template-1"}], source=ConfigSource.YAML_CONFIG, query_time_ms=0.1)

    async def get_metrics(self, **_kwargs):
        return ConfigResult(data=[{"name": "Revenue"}], source=ConfigSource.YAML_CONFIG, query_time_ms=0.1)

    async def get_companies(self, **_kwargs):
        return ConfigResult(data=[{"ticker": "AMD"}], source=ConfigSource.YAML_CONFIG, query_time_ms=0.1)

    async def get_analytics_context(self, **_kwargs):
        return ConfigResult(data=[{"type": "context"}], source=ConfigSource.YAML_CONFIG, query_time_ms=0.1)


def test_supervisor_tools_dependency_injection():
    stub_store = StubConfigStore()
    tools = SupervisorTools(configs={"queries": {}}, config_store=stub_store)
    assert tools.config_store is stub_store


def test_supervisor_tools_schema_registration():
    schemas = SupervisorTools.get_tool_schemas()
    names = {schema.get("name") for schema in schemas if schema.get("type") == "function"}
    assert "provisional_plan" in names
    assert "validate_sql" in names

@pytest.mark.asyncio
async def test_supervisor_tools_metrics_stub_usage():
    stub_store = StubConfigStore()
    tools = SupervisorTools(configs={"queries": {}}, config_store=stub_store)
    metrics = await tools.lookup_metrics(query="revenue")
    assert metrics[0]["name"] == "Revenue"
    assert metrics[0]["_config_metadata"]["source"] == ConfigSource.YAML_CONFIG.value
