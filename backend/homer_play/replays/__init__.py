from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ..models import PLAY_SUCCESS_ADAPTER


ROOT = Path(__file__).resolve().parent


class ReplayManifestEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    replay_id: str
    tab: Literal["memory", "scheduler", "executors", "mcp", "voice", "web"]
    action: str
    schema_version: Literal["1"]
    captured_at: datetime
    generator_build: str
    source_fixture: str
    content_sha256: str
    public_reviewed_by: str
    public_reviewed_at: datetime


class ReplayManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"]
    fixtures: list[ReplayManifestEntry]


def _load() -> tuple[ReplayManifest, dict[str, dict]]:
    manifest = ReplayManifest.model_validate_json((ROOT / "manifest.json").read_text(encoding="utf-8"))
    loaded: dict[str, dict] = {}
    for entry in manifest.fixtures:
        fixture_path = (ROOT / entry.source_fixture).resolve()
        if ROOT not in fixture_path.parents:
            raise ValueError(f"Replay fixture escapes replay root: {entry.source_fixture}")
        raw_bytes = fixture_path.read_bytes()
        digest = hashlib.sha256(raw_bytes).hexdigest()
        if digest != entry.content_sha256:
            raise ValueError(f"Replay fixture hash mismatch: {entry.replay_id}")
        raw = json.loads(raw_bytes)
        validated = PLAY_SUCCESS_ADAPTER.validate_python(raw)
        key = f"{validated.tab}.{validated.action}"
        if key in loaded:
            raise ValueError(f"Duplicate replay fixture for {key}")
        if validated.degraded is None or validated.degraded.replay_id != entry.replay_id:
            raise ValueError(f"Replay manifest mismatch: {entry.replay_id}")
        loaded[key] = validated.model_dump(mode="json", by_alias=True)
    return manifest, loaded


MANIFEST, REPLAYS = _load()


def get_replay(tab: str, action: str) -> dict:
    return copy.deepcopy(REPLAYS[f"{tab}.{action}"])


__all__ = ["MANIFEST", "REPLAYS", "get_replay"]
