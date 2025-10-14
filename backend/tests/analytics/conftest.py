import sys
from pathlib import Path
from typing import Generator

sys.path.append(str(Path(__file__).resolve().parents[2]))

import pytest

from analytics.core import session_state


@pytest.fixture(autouse=True)
def use_in_memory_session_repository(monkeypatch) -> Generator[session_state.SessionStateRepository, None, None]:
    monkeypatch.setattr(session_state, "redis", None)
    repository = session_state.SessionStateRepository()
    monkeypatch.setattr(session_state, "_repository", repository)
    yield repository
