import importlib.util
import pytest

LEGACY_MODULES = [
    "analytics_memory",
    "analytics_shared",
    "analytics_supervisor",
]


@pytest.mark.parametrize("module_name", LEGACY_MODULES)
def test_legacy_modules_removed(module_name):
    spec = importlib.util.find_spec(module_name)
    assert spec is None, f"Legacy module {module_name} should be removed from the codebase"
