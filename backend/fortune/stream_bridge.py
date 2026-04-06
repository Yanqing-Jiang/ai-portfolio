"""SSE/A2UI stream bridge for Ming Engine fortune readings.

Translates internal fortune pipeline results and streamed narrative deltas
into A2UI-compatible SSE messages using custom widget components.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

try:
    from generative_ui.a2ui.emitter import A2UIMessageEmitter
    from generative_ui.a2ui.messages import A2UIComponent
except ImportError:
    from ..generative_ui.a2ui.emitter import A2UIMessageEmitter  # type: ignore[no-redef]
    from ..generative_ui.a2ui.messages import A2UIComponent  # type: ignore[no-redef]

try:
    from .config import get_settings
except ImportError:
    from config import get_settings  # type: ignore[no-redef]


def _stable_id(prefix: str, payload: str) -> str:
    digest = hashlib.md5(payload.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{digest}"


class FortuneStreamBridge:
    """Translates fortune pipeline outputs into A2UI SSE messages."""

    def __init__(self, surface_id: str) -> None:
        settings = get_settings()
        self.surface_id = surface_id
        self.emitter = A2UIMessageEmitter(
            surface_id=surface_id,
            catalog_id=settings.catalog_id,
        )
        self._live_narrative = ""

    @staticmethod
    def _root_components() -> list[A2UIComponent]:
        """Build the full component tree with custom fortune widgets."""
        return [
            # Custom fortune widgets
            A2UIComponent(
                id="fortune_pillars",
                component={
                    "FourPillarsCard": {
                        "title": {"literalString": "Four Pillars"},
                        "pillarsPath": {"path": "/data/pillars"},
                    }
                },
            ),
            A2UIComponent(
                id="fortune_elements",
                component={
                    "ElementBalanceRadar": {
                        "title": {"literalString": "Element Balance"},
                        "elementsPath": {"path": "/data/elements"},
                    }
                },
            ),
            A2UIComponent(
                id="fortune_classics",
                component={
                    "ClassicalReferenceCard": {
                        "referencesPath": {"path": "/data/classics"},
                    }
                },
            ),
            A2UIComponent(
                id="fortune_reading",
                component={
                    "FortuneReadingPanel": {
                        "sectionsPath": {"path": "/data/narrative"},
                    }
                },
            ),
            A2UIComponent(
                id="fortune_disclaimer",
                component={
                    "DisclaimerBanner": {
                        "guardrailPath": {"path": "/data/guardrail"},
                    }
                },
            ),
            # Layout wrappers
            A2UIComponent.card("fortune_pillars_card", "fortune_pillars"),
            A2UIComponent.card("fortune_elements_card", "fortune_elements"),
            A2UIComponent.card("fortune_classics_card", "fortune_classics"),
            A2UIComponent.card("fortune_reading_card", "fortune_reading"),
            A2UIComponent.card("fortune_disclaimer_card", "fortune_disclaimer"),
            A2UIComponent.column(
                "fortune_root",
                [
                    "fortune_pillars_card",
                    "fortune_elements_card",
                    "fortune_classics_card",
                    "fortune_reading_card",
                    "fortune_disclaimer_card",
                ],
            ),
            A2UIComponent.column("layout_root", ["fortune_root"]),
        ]

    # ------------------------------------------------------------------
    # Emission helpers
    # ------------------------------------------------------------------

    def begin_messages(self) -> list[str]:
        """Initial SSE messages: begin rendering + surface layout + meta status."""
        return [
            self.emitter.begin_rendering(root_id="layout_root"),
            self.emitter.surface_update(self._root_components()),
            self.emitter.data_update({"status": "streaming"}, path="/data/meta"),
        ]

    @staticmethod
    def _normalize_pillar(p: dict[str, Any]) -> dict[str, Any]:
        """Convert snake_case Pillar fields to camelCase for frontend."""
        return {
            "raw": p.get("raw", ""),
            "stem": p.get("stem", ""),
            "branch": p.get("branch", ""),
            "stemElement": p.get("stem_element", ""),
            "branchElement": p.get("branch_element", ""),
        }

    def emit_pillars(self, payload: dict[str, Any]) -> str:
        normalized: dict[str, Any] = {}
        for key in ("year", "month", "day"):
            if key in payload and payload[key]:
                normalized[key] = self._normalize_pillar(payload[key])
        if "hour" in payload and payload["hour"]:
            normalized["hour"] = self._normalize_pillar(payload["hour"])
        else:
            normalized["hour"] = None
        normalized["dayMaster"] = payload.get("day_master", "")
        normalized["dayMasterElement"] = payload.get("day_master_element", "")
        normalized["birthTimeUnknown"] = payload.get("birth_time_unknown", False)
        return self.emitter.data_update(normalized, path="/data/pillars")

    def emit_elements(self, payload: dict[str, Any]) -> str:
        return self.emitter.data_update(payload, path="/data/elements")

    def emit_references(self, references: list[dict[str, Any]]) -> str:
        normalized = [
            {
                "id": item.get("id") or _stable_id("ref", item["source"] + item["passage"]),
                "passage": item["passage"],
                "translation": item["translation"],
                "source": item["source"],
                "relevance": item["relevance"],
            }
            for item in references
        ]
        return self.emitter.data_update(
            {"references": normalized}, path="/data/classics",
        )

    def emit_narrative_delta(self, delta: str) -> str:
        """Accumulate streaming text into a single live section."""
        self._live_narrative += delta
        sections = [
            {
                "id": "section_live",
                "heading": "Reading In Progress",
                "content": self._live_narrative,
                "type": "overview",
                "citations": [],
            }
        ]
        return self.emitter.data_update(
            {"sections": sections, "isComplete": False}, path="/data/narrative",
        )

    def emit_narrative_complete(self, sections: list[dict[str, Any]]) -> str:
        """Replace streaming section with final multi-section output."""
        normalized = [
            {
                "id": item.get("id") or _stable_id("section", json.dumps(item, sort_keys=True)),
                "heading": item["heading"],
                "content": item["content"],
                "type": item["type"],
                "citations": item.get("citations", []),
            }
            for item in sections
        ]
        return self.emitter.data_update(
            {"sections": normalized, "isComplete": True}, path="/data/narrative",
        )

    def emit_guardrail(self, payload: dict[str, Any]) -> str:
        normalized = {
            "level": payload.get("level", "info"),
            "message": payload.get("message", ""),
            "disclaimer": payload.get("disclaimer", ""),
            "followUpButtons": payload.get("follow_up_buttons", []),
        }
        return self.emitter.data_update(normalized, path="/data/guardrail")

    def emit_complete(self) -> list[str]:
        """Terminal success: set status + audit event."""
        return [
            self.emitter.data_update({"status": "complete"}, path="/data/meta"),
            self.emitter.audit("stream_complete"),
        ]

    def emit_error(self, message: str) -> list[str]:
        """Terminal error: set status + audit event."""
        return [
            self.emitter.data_update(
                {"status": "error", "error_message": message},
                path="/data/meta",
            ),
            self.emitter.audit("error", details=message),
        ]
