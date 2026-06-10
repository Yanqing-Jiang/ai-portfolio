"""Route contract for active APIs and retired legacy surfaces."""

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app  # noqa: E402


def test_active_route_families_are_mounted():
    paths = {route.path for route in app.routes}

    assert "/health" in paths
    assert "/api/analytics/canonical" in paths
    assert "/api/gemini/chat/create" in paths
    assert "/api/conv-analytics/chat" in paths
    assert "/api/dash/create" in paths
    assert "/api/fortune/create" in paths


def test_retired_routes_are_absent():
    paths = {route.path for route in app.routes}

    assert "/api/research" not in paths
    assert "/api/research/stream" not in paths
    assert "/api/resume-search/stream" not in paths
    assert "/api/test-stream" not in paths
    assert "/api/debug/session/{session_id}" not in paths
    assert "/api/analytics/stream" not in paths
    assert "/api/analytics/memory/stream" not in paths
    assert "/api/analytics/memory/clarify" not in paths
