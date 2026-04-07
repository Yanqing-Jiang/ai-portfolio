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
        """Build the full dashboard component tree with custom fortune widgets.

        Layout:
        [KPI Row: 4 x KpiCard]
        [FourPillarsCard | ElementBalanceStacked]
        [InteractionGraph | TenGodsTable]
        [LifeTimeline (full width)]
        [InsightAccordion | ClassicalReferenceCard]
        [Action Buttons]
        [DisclaimerBanner]
        """
        return [
            # ---- Widget definitions ----

            # KPI cards (reuse standard KpiCard)
            A2UIComponent(id="kpi_day_master", component={
                "KpiCard": {
                    "title": {"literalString": "Day Master"},
                    "valuePath": {"path": "/data/kpi/dayMaster"},
                    "subtitlePath": {"path": "/data/kpi/dayMasterElement"},
                }
            }),
            A2UIComponent(id="kpi_harmony", component={
                "KpiCard": {
                    "title": {"literalString": "Harmony Score"},
                    "valuePath": {"path": "/data/kpi/harmonyScore"},
                    "subtitlePath": {"literalString": "/ 100"},
                }
            }),
            A2UIComponent(id="kpi_cycle", component={
                "KpiCard": {
                    "title": {"literalString": "Current Cycle"},
                    "valuePath": {"path": "/data/kpi/currentCycle"},
                    "subtitlePath": {"literalString": "\u5927\u8fd0"},
                }
            }),
            A2UIComponent(id="kpi_seasonal", component={
                "KpiCard": {
                    "title": {"literalString": "Seasonal Strength"},
                    "valuePath": {"path": "/data/kpi/seasonalStrength"},
                    "subtitlePath": {"path": "/data/kpi/seasonalScore"},
                }
            }),

            # Four Pillars
            A2UIComponent(id="fortune_pillars", component={
                "FourPillarsCard": {
                    "title": {"literalString": "Four Pillars"},
                    "pillarsPath": {"path": "/data/pillars"},
                }
            }),

            # Element balance (stacked bar)
            A2UIComponent(id="fortune_elements_stacked", component={
                "ElementBalanceStacked": {
                    "sourcePath": {"path": "/data/elementBySource"},
                }
            }),

            # Element balance (radar — legacy, kept as secondary)
            A2UIComponent(id="fortune_elements_radar", component={
                "ElementBalanceRadar": {
                    "title": {"literalString": "Element Radar"},
                    "elementsPath": {"path": "/data/elements"},
                }
            }),

            # Interaction graph
            A2UIComponent(id="fortune_interactions", component={
                "InteractionGraph": {
                    "interactionsPath": {"path": "/data/interactions"},
                    "pillarsPath": {"path": "/data/pillars"},
                }
            }),

            # Ten Gods table
            A2UIComponent(id="fortune_ten_gods", component={
                "TenGodsTable": {
                    "godsPath": {"path": "/data/tenGods"},
                }
            }),

            # Life Timeline
            A2UIComponent(id="fortune_timeline", component={
                "LifeTimeline": {
                    "luckPillarsPath": {"path": "/data/luckPillars"},
                    "annualPillarsPath": {"path": "/data/annualPillars"},
                    "narrativePath": {"path": "/data/narrative"},
                    "correctionsPath": {"path": "/data/corrections"},
                }
            }),

            # Classical references
            A2UIComponent(id="fortune_classics", component={
                "ClassicalReferenceCard": {
                    "referencesPath": {"path": "/data/classics"},
                }
            }),

            # Insight accordion
            A2UIComponent(id="fortune_reading", component={
                "InsightAccordion": {
                    "insightsPath": {"path": "/data/narrative"},
                }
            }),

            # Disclaimer
            A2UIComponent(id="fortune_disclaimer", component={
                "DisclaimerBanner": {
                    "guardrailPath": {"path": "/data/guardrail"},
                }
            }),

            # Action buttons
            *FortuneStreamBridge._action_button_components(),

            # ---- Layout structure ----

            # KPI row (4 across)
            A2UIComponent.row("kpi_row", [
                "kpi_day_master", "kpi_harmony", "kpi_cycle", "kpi_seasonal",
            ]),

            # Row 1: Pillars + Element Balance
            A2UIComponent.card("fortune_pillars_card", "fortune_pillars"),
            A2UIComponent.card("fortune_elements_card", "fortune_elements_stacked"),
            A2UIComponent.row("row_pillars_elements", [
                "fortune_pillars_card", "fortune_elements_card",
            ]),

            # Row 2: Interactions + Ten Gods
            A2UIComponent.card("fortune_interactions_card", "fortune_interactions"),
            A2UIComponent.card("fortune_ten_gods_card", "fortune_ten_gods"),
            A2UIComponent.row("row_interactions_gods", [
                "fortune_interactions_card", "fortune_ten_gods_card",
            ]),

            # Timeline (full width)
            A2UIComponent.card("fortune_timeline_card", "fortune_timeline"),

            # Row 3: Insights + Classics
            A2UIComponent.card("fortune_reading_card", "fortune_reading"),
            A2UIComponent.card("fortune_classics_card", "fortune_classics"),
            A2UIComponent.row("row_reading_classics", [
                "fortune_reading_card", "fortune_classics_card",
            ]),

            # Disclaimer
            A2UIComponent.card("fortune_disclaimer_card", "fortune_disclaimer"),

            # Agent Trace Sidebar
            A2UIComponent(id="fortune_trace", component={
                "AgentTraceSidebar": {
                    "stepsPath": {"path": "/data/trace/steps"},
                    "summaryPath": {"path": "/data/summary"},
                }
            }),
            A2UIComponent.card("fortune_trace_card", "fortune_trace"),

            # Root column (main dashboard)
            A2UIComponent.column(
                "fortune_root",
                [
                    "kpi_row",
                    "row_pillars_elements",
                    "row_interactions_gods",
                    "fortune_timeline_card",
                    "row_reading_classics",
                    "fortune_actions_row",
                    "fortune_disclaimer_card",
                ],
            ),
            # Layout root: main dashboard + trace sidebar
            A2UIComponent.row("layout_root", ["fortune_root", "fortune_trace_card"]),
        ]

    @staticmethod
    def _action_button_components() -> list[A2UIComponent]:
        """Build follow-up action button components for the fortune surface."""
        buttons = [
            ("btn_year", "📅 Year Forecast", "year_forecast"),
            ("btn_career", "📐 Career Deep Dive", "career_focus"),
            ("btn_compat", "🤝 Compatibility", "relationship_focus"),
            ("btn_elements", "🔮 Element Deep Dive", "deep_dive_element"),
        ]
        components: list[A2UIComponent] = []
        for btn_id, label, action_id in buttons:
            # Label text component
            components.append(A2UIComponent(
                id=f"{btn_id}_label",
                component={
                    "Text": {"text": {"literalString": label}, "usageHint": "body"}
                },
            ))
            # Button component
            components.append(A2UIComponent(
                id=btn_id,
                component={
                    "Button": {
                        "child": f"{btn_id}_label",
                        "action": {
                            "name": "userAction",
                            "context": [
                                {"key": "actionId", "value": {"literalString": action_id}}
                            ],
                        },
                        "variant": "secondary",
                    }
                },
            ))
        btn_ids = [b[0] for b in buttons]
        components.append(A2UIComponent.row("fortune_actions_row", btn_ids))
        return components

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
        """Accumulate streaming text — show loading state until complete."""
        self._live_narrative += delta
        return self.emitter.data_update(
            {"isComplete": False, "streamingText": self._live_narrative[:120]},
            path="/data/narrative",
        )

    def emit_narrative_complete(self, narrative_data: dict[str, Any]) -> str:
        """Emit final insight-based narrative with tldr + insight sections."""
        insights = []
        for item in narrative_data.get("insights", []):
            bullets = [
                {"icon": b.get("icon", "•"), "text": b.get("text", "")}
                for b in item.get("bullets", [])
            ]
            insights.append({
                "id": item.get("id") or _stable_id("insight", item.get("heading", "")),
                "icon": item.get("icon", "📖"),
                "heading": item.get("heading", ""),
                "tagline": item.get("tagline", ""),
                "bullets": bullets,
                "citations": item.get("citations", []),
            })
        return self.emitter.data_update(
            {
                "tldr": narrative_data.get("tldr", ""),
                "insights": insights,
                "isComplete": True,
            },
            path="/data/narrative",
        )

    # ------------------------------------------------------------------
    # Enriched data emission helpers (Phase 1 — bazi_engine outputs)
    # ------------------------------------------------------------------

    def emit_hidden_stems(self, hidden_stems: dict[str, Any]) -> str:
        """Emit hidden stems (藏干) per pillar."""
        normalized: dict[str, Any] = {}
        for pillar_name, stems in hidden_stems.items():
            normalized[pillar_name] = [
                {
                    "stem": s.stem if hasattr(s, "stem") else s["stem"],
                    "element": s.element if hasattr(s, "element") else s["element"],
                    "strength": s.strength if hasattr(s, "strength") else s["strength"],
                }
                for s in stems
            ]
        return self.emitter.data_update(normalized, path="/data/hiddenStems")

    def emit_ten_gods(self, ten_gods: list[Any]) -> str:
        """Emit ten gods (十神) classification."""
        normalized = [
            {
                "stem": tg.stem if hasattr(tg, "stem") else tg["stem"],
                "god": tg.god if hasattr(tg, "god") else tg["god"],
                "english": tg.english if hasattr(tg, "english") else tg["english"],
                "pillar": tg.pillar if hasattr(tg, "pillar") else tg["pillar"],
                "position": tg.position if hasattr(tg, "position") else tg["position"],
            }
            for tg in ten_gods
        ]
        return self.emitter.data_update({"items": normalized}, path="/data/tenGods")

    def emit_interactions(self, interactions: list[Any]) -> str:
        """Emit branch interactions (冲合害刑破)."""
        normalized = [
            {
                "type": ix.type if hasattr(ix, "type") else ix["type"],
                "between": ix.between if hasattr(ix, "between") else ix["between"],
                "pillars": ix.pillars if hasattr(ix, "pillars") else ix["pillars"],
                "resultElement": (ix.result_element if hasattr(ix, "result_element") else ix.get("result_element")),
                "description": ix.description if hasattr(ix, "description") else ix["description"],
            }
            for ix in interactions
        ]
        return self.emitter.data_update({"items": normalized}, path="/data/interactions")

    def emit_seasonal_strength(self, seasonal: Any) -> str:
        """Emit seasonal strength (旺相休囚死)."""
        data = seasonal.model_dump() if hasattr(seasonal, "model_dump") else seasonal
        normalized = {
            "dayMasterElement": data.get("day_master_element", ""),
            "monthBranch": data.get("month_branch", ""),
            "season": data.get("season", ""),
            "strength": data.get("strength", ""),
            "score": data.get("score", 0),
        }
        return self.emitter.data_update(normalized, path="/data/seasonalStrength")

    def emit_element_by_source(self, element_by_source: dict[str, dict[str, float]]) -> str:
        """Emit per-pillar element breakdown for stacked bar chart."""
        return self.emitter.data_update(element_by_source, path="/data/elementBySource")

    def emit_luck_pillars(self, luck_pillars: list[Any]) -> str:
        """Emit luck pillars (大运)."""
        normalized = [
            {
                "index": lp.index if hasattr(lp, "index") else lp["index"],
                "startAge": lp.start_age if hasattr(lp, "start_age") else lp["start_age"],
                "endAge": lp.end_age if hasattr(lp, "end_age") else lp["end_age"],
                "stem": lp.stem if hasattr(lp, "stem") else lp["stem"],
                "branch": lp.branch if hasattr(lp, "branch") else lp["branch"],
                "stemElement": lp.stem_element if hasattr(lp, "stem_element") else lp["stem_element"],
                "branchElement": lp.branch_element if hasattr(lp, "branch_element") else lp["branch_element"],
                "startYear": lp.start_year if hasattr(lp, "start_year") else lp["start_year"],
                "endYear": lp.end_year if hasattr(lp, "end_year") else lp["end_year"],
            }
            for lp in luck_pillars
        ]
        return self.emitter.data_update({"items": normalized}, path="/data/luckPillars")

    def emit_annual_pillars(self, annual_pillars: list[Any]) -> str:
        """Emit annual pillars (流年)."""
        normalized = [
            {
                "year": ap.year if hasattr(ap, "year") else ap["year"],
                "stem": ap.stem if hasattr(ap, "stem") else ap["stem"],
                "branch": ap.branch if hasattr(ap, "branch") else ap["branch"],
                "stemElement": ap.stem_element if hasattr(ap, "stem_element") else ap["stem_element"],
                "branchElement": ap.branch_element if hasattr(ap, "branch_element") else ap["branch_element"],
                "interactions": [
                    {
                        "type": ix.type if hasattr(ix, "type") else ix["type"],
                        "between": ix.between if hasattr(ix, "between") else ix["between"],
                        "description": ix.description if hasattr(ix, "description") else ix["description"],
                    }
                    for ix in (ap.interactions_with_chart if hasattr(ap, "interactions_with_chart") else ap["interactions_with_chart"])
                ],
                "luckPillarIndex": ap.luck_pillar_index if hasattr(ap, "luck_pillar_index") else ap["luck_pillar_index"],
            }
            for ap in annual_pillars
        ]
        return self.emitter.data_update({"items": normalized}, path="/data/annualPillars")

    def emit_kpi(self, analysis: Any) -> str:
        """Emit KPI summary data (harmony score, seasonal strength, etc.)."""
        pillars = analysis.pillars if hasattr(analysis, "pillars") else analysis["pillars"]
        seasonal = analysis.seasonal_strength if hasattr(analysis, "seasonal_strength") else analysis["seasonal_strength"]
        harmony = analysis.harmony_score if hasattr(analysis, "harmony_score") else analysis["harmony_score"]
        luck_pillars = analysis.luck_pillars if hasattr(analysis, "luck_pillars") else analysis.get("luck_pillars", [])

        day_master = pillars.get("day_master", "") if isinstance(pillars, dict) else pillars.day_master
        day_master_element = pillars.get("day_master_element", "") if isinstance(pillars, dict) else pillars.day_master_element
        seasonal_strength = seasonal.strength if hasattr(seasonal, "strength") else seasonal["strength"]
        seasonal_score = seasonal.score if hasattr(seasonal, "score") else seasonal["score"]

        current_cycle = "N/A"
        if luck_pillars:
            from datetime import datetime as dt
            current_year = dt.now().year
            for lp in luck_pillars:
                sy = lp.start_year if hasattr(lp, "start_year") else lp["start_year"]
                ey = lp.end_year if hasattr(lp, "end_year") else lp["end_year"]
                stem = lp.stem if hasattr(lp, "stem") else lp["stem"]
                branch = lp.branch if hasattr(lp, "branch") else lp["branch"]
                if sy <= current_year <= ey:
                    current_cycle = f"{stem}{branch}"
                    break

        return self.emitter.data_update(
            {
                "dayMaster": day_master,
                "dayMasterElement": day_master_element,
                "harmonyScore": harmony,
                "currentCycle": current_cycle,
                "seasonalStrength": seasonal_strength,
                "seasonalScore": round(seasonal_score * 100, 1),
            },
            path="/data/kpi",
        )

    # ------------------------------------------------------------------
    # Agent Trace emission helpers (Phase 4 — Glass Box)
    # ------------------------------------------------------------------

    def emit_trace_step(self, step: Any) -> str:
        """Emit a single trace step for the Agent Trace Sidebar."""
        data = step.model_dump() if hasattr(step, "model_dump") else step
        normalized = {
            "stepId": data.get("step_id", ""),
            "stepType": data.get("step_type", ""),
            "agentName": data.get("agent_name", ""),
            "toolName": data.get("tool_name"),
            "label": data.get("label", ""),
            "inputSummary": data.get("input_summary", ""),
            "outputSummary": data.get("output_summary", ""),
            "timestamp": data.get("timestamp", ""),
            "durationMs": data.get("duration_ms", 0),
            "status": data.get("status", "pending"),
        }
        return self.emitter.data_update(
            {"step": normalized},
            path=f"/data/trace/steps/{normalized['stepId']}",
        )

    def emit_trace_steps_batch(self, steps: list[Any]) -> str:
        """Emit all foundation trace steps at once."""
        normalized = [
            {
                "stepId": (s.step_id if hasattr(s, "step_id") else s.get("step_id", "")),
                "stepType": (s.step_type if hasattr(s, "step_type") else s.get("step_type", "")),
                "agentName": (s.agent_name if hasattr(s, "agent_name") else s.get("agent_name", "")),
                "toolName": (s.tool_name if hasattr(s, "tool_name") else s.get("tool_name")),
                "label": (s.label if hasattr(s, "label") else s.get("label", "")),
                "inputSummary": (s.input_summary if hasattr(s, "input_summary") else s.get("input_summary", "")),
                "outputSummary": (s.output_summary if hasattr(s, "output_summary") else s.get("output_summary", "")),
                "timestamp": (s.timestamp if hasattr(s, "timestamp") else s.get("timestamp", "")),
                "durationMs": (s.duration_ms if hasattr(s, "duration_ms") else s.get("duration_ms", 0)),
                "status": (s.status if hasattr(s, "status") else s.get("status", "pending")),
            }
            for s in steps
        ]
        return self.emitter.data_update({"items": normalized}, path="/data/trace/steps")

    def emit_trace_summary(self, summary: dict[str, Any]) -> str:
        """Emit aggregate trace summary (total duration, counts)."""
        return self.emitter.data_update(summary, path="/data/trace/summary")

    def emit_guardrail(self, payload: dict[str, Any]) -> str:
        normalized = {
            "level": payload.get("level", "info"),
            "message": payload.get("message", ""),
            "disclaimer": payload.get("disclaimer", ""),
            "followUpButtons": payload.get("follow_up_buttons", []),
        }
        return self.emitter.data_update(normalized, path="/data/guardrail")

    def emit_complete(self) -> list[str]:
        """Terminal success: set status + audit event + done signal.

        The final '{"done": true}' is required by the frontend useA2UIStream
        hook — without it, EventSource interprets the server-side close as an
        error and retries 5 times before surfacing "Stream connection lost".
        """
        return [
            self.emitter.data_update({"status": "complete"}, path="/data/meta"),
            self.emitter.audit("stream_complete"),
            '{"done": true}',
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
