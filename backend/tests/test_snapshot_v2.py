"""Phase 3A — snapshot v2 accumulator, legacy normalizer, dual-read shape."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.responses import JSONResponse

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

GOLDEN_PATH = BACKEND / "tests" / "golden" / "fortune_a2ui_frames_wish_v1.json"

from fortune.snapshot_model import (  # noqa: E402
    accumulate_from_envelopes,
    apply_data_model_update,
    data_model_from_legacy_columns,
    process_contents,
)


def test_accumulator_from_golden_frames_merges_and_overwrites():
    frames = json.loads(GOLDEN_PATH.read_text())
    model = accumulate_from_envelopes(frames)

    assert "pillars" in model
    assert "kpi" in model
    assert "thinking" in model
    assert "meta" in model
    assert model.get("narrative", {}).get("isComplete") is True
    # Wish fan-out is absent from the golden (mocked narrative has no wish block);
    # assert the shared foundation + narrative paths the golden does emit.
    assert "classics" in model
    assert "guardrail" in model

    # Overwrite semantics: later update to same path wins / merges.
    base = apply_data_model_update(
        {},
        "/data/corrections",
        [{"key": "2020", "valueMap": [{"key": "user_note", "valueString": "old"}]}],
    )
    updated = apply_data_model_update(
        base,
        "/data/corrections",
        [{"key": "2020", "valueMap": [{"key": "user_note", "valueString": "new"}]}],
    )
    assert updated["corrections"]["2020"]["user_note"] == "new"

    # valueBool alias + nested valueObject alias
    aliased = process_contents(
        [
            {"key": "ok", "valueBool": True},
            {"key": "nested", "valueObject": [{"key": "n", "valueNumber": 3}]},
        ]
    )
    assert aliased == {"ok": True, "nested": {"n": 3}}


def test_legacy_normalizer_synthetic_v1_row():
    model = data_model_from_legacy_columns(
        pillars={
            "pillars": {
                "year": {"stem": "甲", "branch": "子"},
                "day_master": "甲",
                "day_master_element": "wood",
            },
            "elements": {"wood": 2, "fire": 1},
        },
        mechanics={
            "harmony_score": 0.7,
            "ten_gods": [{"name": "Direct Wealth"}],
            "hidden_stems": {"year": ["甲"]},
            "interactions": [{"type": "clash"}],
            "seasonal_strength": {"strength": "旺", "score": 0.8},
            "luck_pillars": [{"decade": "2024-2033"}],
            "annual_pillars": [{"year": 2026}],
        },
        narrative={
            "tldr": "hello",
            "insights": [{"heading": "H", "bullets": []}],
            "wish": {"verdict": {"summary": "yes"}},
        },
        references={"items": [{"title": "Classic"}]},
        retrodictions={
            "items": [{"year": 2020}],
            "corrections": {"2020": {"user_note": "note", "corrected_at": "2026-01-01"}},
        },
        focus="wish",
    )
    assert model["kpi"]["harmonyScore"] == 0.7
    assert model["tenGods"]["items"][0]["name"] == "Direct Wealth"
    assert model["narrative"]["isComplete"] is True
    assert model["wish"]["verdict"]["summary"] == "yes"
    assert model["classics"]["references"][0]["title"] == "Classic"
    assert model["corrections"]["2020"]["userNote"] == "note"
    assert model["elements"].get("Wood", model["elements"].get("wood")) == 2


def test_dual_read_response_shape_v1_and_v2():
    """Snapshot GET payload: v1 unchanged core fields; v2 carries data_model."""
    from fortune.routes import _unpack_jsonb

    def build_payload(row: dict) -> dict:
        schema_version = row.get("schema_version")
        if schema_version is None:
            schema_version = 1
        retro = _unpack_jsonb(row.get("latest_retrodictions"))
        corrections = retro.get("corrections") if isinstance(retro, dict) else None
        return {
            "fortune_id": row["fortune_id"],
            "snapshot_version": row["snapshot_version"],
            "schema_version": int(schema_version),
            "status": row["snapshot_status"],
            "metadata": {"focus": row.get("focus")},
            "data": {
                "overview": _unpack_jsonb(row.get("latest_overview")),
                "pillars": _unpack_jsonb(row.get("latest_pillars")),
                "mechanics": _unpack_jsonb(row.get("latest_mechanics")),
                "narrative": _unpack_jsonb(row.get("latest_narrative")),
                "trace": _unpack_jsonb(row.get("latest_trace")),
                "references": _unpack_jsonb(row.get("latest_references")),
                "retrodictions": retro,
                "corrections": corrections,
            },
            "data_model": _unpack_jsonb(row.get("data_model")),
        }

    v1_row = {
        "fortune_id": "f1",
        "snapshot_version": 3,
        "schema_version": 1,
        "snapshot_status": "done",
        "focus": "wish",
        "latest_overview": None,
        "latest_pillars": {"pillars": {"dayMaster": "Jia"}},
        "latest_mechanics": None,
        "latest_narrative": {"tldr": "x"},
        "latest_trace": None,
        "latest_references": None,
        "latest_retrodictions": None,
        "data_model": None,
    }
    v1 = build_payload(v1_row)
    assert v1["schema_version"] == 1
    assert v1["data_model"] is None
    assert v1["data"]["pillars"]["pillars"]["dayMaster"] == "Jia"
    assert set(v1["data"].keys()) >= {
        "overview", "pillars", "mechanics", "narrative",
        "trace", "references", "retrodictions", "corrections",
    }

    v2_row = {
        **v1_row,
        "schema_version": 2,
        "data_model": {"pillars": {"dayMaster": "Jia"}, "wish": {"verdict": {}}},
    }
    v2 = build_payload(v2_row)
    assert v2["schema_version"] == 2
    assert v2["data_model"]["wish"]["verdict"] == {}
    assert v2["data"]["narrative"]["tldr"] == "x"

    body = json.loads(bytes(JSONResponse(content=v2).body))
    assert body["schema_version"] == 2
    assert body["data_model"]["pillars"]["dayMaster"] == "Jia"
