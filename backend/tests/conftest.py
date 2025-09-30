import pytest

try:
    import pytest_asyncio  # type: ignore[import]
    HAS_PYTEST_ASYNCIO = True
except ModuleNotFoundError:
    HAS_PYTEST_ASYNCIO = False


def pytest_collection_modifyitems(config, items):
    if HAS_PYTEST_ASYNCIO:
        return
    skip_marker = pytest.mark.skip(reason="pytest-asyncio not installed; skipping async tests")
    for item in items:
        if any(marker.name == "asyncio" for marker in item.iter_markers()):
            item.add_marker(skip_marker)
