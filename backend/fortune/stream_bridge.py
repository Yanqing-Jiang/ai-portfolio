"""SSE/A2UI stream bridge for Ming Engine fortune readings.

Translates internal fortune pipeline results and streamed narrative deltas
into A2UI-compatible SSE messages using custom widget components.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
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

            # Spooky Accuracy retrodictions
            A2UIComponent(id="fortune_spooky", component={
                "SpookyAccuracyCard": {
                    "retrodictionsPath": {"path": "/data/retrodictions"},
                }
            }),

            # Citation viewer (interactive dual-pane)
            A2UIComponent(id="fortune_citations", component={
                "CitationViewer": {
                    "referencesPath": {"path": "/data/classics"},
                }
            }),

            # Pipeline DAG (Inspector mode only)
            A2UIComponent(id="fortune_dag", component={
                "PipelineDag": {
                    "stepsPath": {"path": "/data/trace/steps"},
                }
            }),

            # Classical references (legacy card view)
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

            # Spooky Accuracy (full width)
            A2UIComponent.card("fortune_spooky_card", "fortune_spooky"),

            # Timeline (full width)
            A2UIComponent.card("fortune_timeline_card", "fortune_timeline"),

            # Pipeline DAG (full width, inspector only)
            A2UIComponent.card("fortune_dag_card", "fortune_dag"),

            # Row 3: Insights + Citations
            A2UIComponent.card("fortune_reading_card", "fortune_reading"),
            A2UIComponent.card("fortune_citations_card", "fortune_citations"),
            A2UIComponent.row("row_reading_citations", [
                "fortune_reading_card", "fortune_citations_card",
            ]),

            # Disclaimer
            A2UIComponent.card("fortune_disclaimer_card", "fortune_disclaimer"),

            # Agent Trace Sidebar
            A2UIComponent(id="fortune_trace", component={
                "AgentTraceSidebar": {
                    "stepsPath": {"path": "/data/trace/steps"},
                    "summaryPath": {"path": "/data/trace/summary"},
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
                    "fortune_spooky_card",
                    "fortune_timeline_card",
                    "fortune_dag_card",
                    "row_reading_citations",
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

    def begin_messages(self, fortune_id: str | None = None) -> list[str]:
        """Initial SSE messages: begin rendering + surface layout + meta status."""
        meta: dict[str, Any] = {"status": "streaming"}
        if fortune_id:
            meta["fortuneId"] = fortune_id
        return [
            self.emitter.begin_rendering(root_id="layout_root"),
            self.emitter.surface_update(self._root_components()),
            self.emitter.data_update(meta, path="/data/meta"),
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

    @staticmethod
    def _trace_kind(step_type: Any) -> str:
        """Map internal trace step types to the frontend's simplified kind set."""
        normalized = str(step_type or "").strip().lower()
        if normalized == "tool_call":
            return "tool_call"
        if normalized in {"tool_result", "tool_output", "data_emit"}:
            return "tool_output"
        if normalized in {"llm_start", "llm_complete", "message"}:
            return "llm"
        if normalized in {"handoff", "handoff_call"}:
            return "handoff"
        return "llm"

    @staticmethod
    def _progress_percent(phase: str, message: str) -> int:
        """Derive a stable progress percentage for AgentPhaseStrip."""
        normalized_phase = (phase or "").strip().lower()
        normalized_message = (message or "").strip().lower()
        if normalized_phase == "foundation":
            if "person b" in normalized_message:
                return 30
            return 20
        if normalized_phase == "narrative":
            if normalized_message.startswith("routing"):
                return 45
            if normalized_message.startswith("calling tool"):
                return 60
            if normalized_message.startswith("tool returned"):
                return 75
            if "response received" in normalized_message:
                return 85
            return 55
        if normalized_phase == "guardrail":
            return 95
        return 0

    @staticmethod
    def _normalize_mechanism_type(scope: str, item: dict[str, Any]) -> str | None:
        """Infer a mechanism filter type when the model leaves it blank."""
        raw_type = item.get("type")
        if isinstance(raw_type, str) and raw_type.strip():
            return raw_type.strip()

        text = " ".join(
            str(part)
            for part in [
                item.get("title", ""),
                " ".join(item.get("bullets") or []),
            ]
            if part
        ).lower()

        if scope == "compatibility":
            if "clash" in text:
                return "clash"
            if "harm" in text:
                return "harm"
            if "punish" in text:
                return "punishment"
            if "support" in text or "assist" in text:
                return "support"
            if "combine" in text or "combination" in text or "transform" in text:
                return "combination"
            return "support"

        if scope == "occasion":
            if "avoid" in text or "clash" in text or "unstable" in text:
                return "Caution"
            if "hour" in text or "timing" in text or "window" in text:
                return "Timing"
            if any(element in text for element in ("wood", "fire", "earth", "metal", "water")):
                return "Element"
            if "support" in text or "combine" in text:
                return "Support"
            return "Timing"

        if scope == "luck_cycle":
            if "avoid" in text or "caution" in text or "unstable" in text:
                return "caution"
            if "support" in text or "assist" in text or "combine" in text:
                return "support"
            if any(element in text for element in ("wood", "fire", "earth", "metal", "water")):
                return "element"
            if "timing" in text or "window" in text or "year" in text:
                return "timing"
            return "cycle"

        if scope == "wish":
            if "luck" in text or "cycle" in text or "decade" in text or "year" in text:
                return "luck"
            if any(keyword in text for keyword in ("interaction", "clash", "combine", "harm", "punish")):
                return "interaction"
            return "chart"

        return None

    def _normalize_mechanism_cards(
        self,
        mechanisms: list[dict[str, Any]],
        *,
        scope: str,
    ) -> list[dict[str, Any]]:
        """Normalize mechanism cards across fortune sub-modes."""
        normalized: list[dict[str, Any]] = []
        for item in mechanisms:
            mech = item.model_dump() if hasattr(item, "model_dump") else dict(item)
            card = {
                "id": mech.get("id"),
                "title": mech.get("title"),
                "type": self._normalize_mechanism_type(scope, mech),
                "icon": mech.get("icon"),
                "bullets": mech.get("bullets", []),
                "citationIds": mech.get("citation_ids") or mech.get("citationIds") or [],
            }
            normalized.append({k: v for k, v in card.items() if v is not None})
        return normalized

    @staticmethod
    def _compat_interaction_description(item: dict[str, Any]) -> str:
        """Backfill a concise rationale for compatibility interactions."""
        description = item.get("description")
        if isinstance(description, str) and description.strip():
            return description.strip()

        interaction_type = str(item.get("type") or "interaction").strip().lower()
        source = item.get("from") or item.get("from_") or "this pillar"
        target = item.get("to") or "that pillar"
        person_a = item.get("person_a") or item.get("personA") or "Person A"
        person_b = item.get("person_b") or item.get("personB") or "Person B"
        templates = {
            "combination": f"{source} and {target} combine between {person_a} and {person_b}, creating an easier point of alignment.",
            "clash": f"{source} clashes with {target} between {person_a} and {person_b}, so this axis needs extra care.",
            "harm": f"{source} harms {target} between {person_a} and {person_b}, adding subtle friction under the surface.",
            "support": f"{source} supports {target} between {person_a} and {person_b}, helping the pairing stabilize.",
            "punishment": f"{source} punishes {target} between {person_a} and {person_b}, which can amplify internal tension.",
        }
        return templates.get(
            interaction_type,
            f"{source} and {target} form a notable interaction between {person_a} and {person_b}.",
        )

    def _default_pick_mechanisms(
        self,
        pick: dict[str, Any],
        fallback_mechanisms: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Derive a minimal per-pick mechanism list when the model omits one."""
        day_stem = pick.get("day_pillar_stem") or pick.get("dayPillarStem") or ""
        day_branch = pick.get("day_pillar_branch") or pick.get("dayPillarBranch") or ""
        reason = pick.get("one_line_reason") or pick.get("oneLineReason") or ""
        best_hours = pick.get("best_hours") or pick.get("bestHours") or []
        fallback_cards = self._normalize_mechanism_cards(fallback_mechanisms or [], scope="occasion")
        bullets = [reason] if reason else []
        if day_stem or day_branch:
            bullets.append(f"Day pillar: {day_stem}{day_branch}")
        if best_hours:
            bullets.append(f"Best hours: {', '.join(best_hours[:2])}")
        card = {
            "id": f"pick_{pick.get('date') or pick.get('rank') or 'day'}",
            "title": "Why this day works",
            "type": "Timing",
            "icon": "sparkles",
            "bullets": bullets[:3],
            "citationIds": fallback_cards[0].get("citationIds", []) if fallback_cards else [],
        }
        return [card] if card["bullets"] else []

    @staticmethod
    def _normalize_relevance(value: Any) -> float:
        """Clamp wish anchor relevance into the 0-1 range expected by the UI."""
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = 0.5
        return max(0.0, min(1.0, numeric))

    @staticmethod
    def _normalize_condition_type(value: Any) -> str:
        """Collapse loose wish condition labels into the UI's three states."""
        normalized = str(value or "").strip().lower()
        if normalized in {"check", "pass", "yes", "good", "positive", "support"}:
            return "check"
        if normalized in {"cross", "block", "blocked", "avoid", "no"}:
            return "cross"
        return "warn"

    def _normalize_wish_conditions(self, conditions: list[Any]) -> list[dict[str, str]]:
        """Convert raw verdict conditions into `{type, text}` objects."""
        normalized: list[dict[str, str]] = []
        for item in conditions:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    normalized.append({"type": "warn", "text": text})
                continue

            if not isinstance(item, dict):
                continue

            text = item.get("text") or item.get("label") or item.get("description")
            if not isinstance(text, str) or not text.strip():
                continue
            normalized.append({
                "type": self._normalize_condition_type(item.get("type")),
                "text": text.strip(),
            })
        return normalized

    @staticmethod
    def _normalize_luck_pillar_item(lp: Any) -> dict[str, Any]:
        """Normalize one decade pillar for both the top-level and timeline paths."""
        return {
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

    @staticmethod
    def _normalize_annual_pillar_item(ap: Any) -> dict[str, Any]:
        """Normalize one annual pillar for both the top-level and timeline paths."""
        return {
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

    @staticmethod
    def _active_luck_pillar(luck_pillars: list[Any]) -> Any | None:
        """Pick the active decade pillar for the current calendar year."""
        current_year = datetime.now().year
        for pillar in luck_pillars:
            start_year = pillar.start_year if hasattr(pillar, "start_year") else pillar["start_year"]
            end_year = pillar.end_year if hasattr(pillar, "end_year") else pillar["end_year"]
            if start_year <= current_year <= end_year:
                return pillar
        return luck_pillars[0] if luck_pillars else None

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

    def emit_compat_person(
        self,
        person_key: str,
        *,
        name: str | None,
        pillars: dict[str, Any],
        elements: dict[str, Any] | None,
        ten_gods: list[Any] | None = None,
        hidden_stems: dict[str, list[Any]] | None = None,
    ) -> str:
        """Emit a single person's chart into the compatibility data model.

        person_key: 'personA' or 'personB'. The frontend's CompatibilityModel
        expects dataModel.compatibility.{personA,personB} of shape PersonChart.
        """
        normalized_pillars: dict[str, Any] = {}
        for key in ("year", "month", "day"):
            if key in pillars and pillars[key]:
                normalized_pillars[key] = self._normalize_pillar(pillars[key])
        if "hour" in pillars and pillars["hour"]:
            normalized_pillars["hour"] = self._normalize_pillar(pillars["hour"])
        else:
            normalized_pillars["hour"] = None

        payload: dict[str, Any] = {
            "pillars": normalized_pillars,
            "dayMaster": pillars.get("day_master", ""),
            "dayMasterElement": pillars.get("day_master_element", ""),
        }
        if name:
            payload["name"] = name
        if elements is not None:
            payload["elements"] = elements
        if ten_gods is not None:
            payload["tenGods"] = [
                tg.model_dump() if hasattr(tg, "model_dump") else tg for tg in ten_gods
            ]
        if hidden_stems is not None:
            payload["hiddenStems"] = {
                k: [s.model_dump() if hasattr(s, "model_dump") else s for s in v]
                for k, v in hidden_stems.items()
            }
        return self.emitter.data_update(payload, path=f"/data/compatibility/{person_key}")

    def emit_compat_overview(self, overview: dict[str, Any]) -> str:
        return self.emitter.data_update(overview, path="/data/compatibility/overview")

    def emit_compat_pair_interactions(self, interactions: list[dict[str, Any]]) -> str:
        # Frontend PairInteraction uses camelCase keys personA/personB; the
        # narrative agent emits snake_case so we normalize here.
        normalized = [
            {
                "type": item.get("type"),
                "from": item.get("from") or item.get("from_"),
                "to": item.get("to"),
                "personA": item.get("person_a") or item.get("personA"),
                "personB": item.get("person_b") or item.get("personB"),
                "description": self._compat_interaction_description(item),
                "effect": item.get("effect"),
            }
            for item in interactions
        ]
        return self.emitter.data_update({"pairInteractions": normalized}, path="/data/compatibility")

    def emit_compat_mechanisms(self, mechanisms: list[dict[str, Any]]) -> str:
        # Frontend Mechanism shape: {id, title, type, bullets[], citationIds[], icon}
        normalized = self._normalize_mechanism_cards(mechanisms, scope="compatibility")
        return self.emitter.data_update({"mechanisms": normalized}, path="/data/compatibility")

    # --- Occasion (lucky-day) ---
    def emit_occasion_top_picks(
        self,
        picks: list[dict[str, Any]],
        *,
        fallback_mechanisms: list[dict[str, Any]] | None = None,
    ) -> str:
        normalized = []
        for p in picks:
            pick = p.model_dump() if hasattr(p, "model_dump") else dict(p)
            row = {
                "rank": pick.get("rank"),
                "date": pick.get("date"),
                "dayPillar": {
                    "stem": pick.get("day_pillar_stem") or pick.get("dayPillarStem"),
                    "branch": pick.get("day_pillar_branch") or pick.get("dayPillarBranch"),
                },
                "score": pick.get("score"),
                "oneLineReason": pick.get("one_line_reason") or pick.get("oneLineReason"),
                "bestHours": pick.get("best_hours") or pick.get("bestHours") or [],
            }
            mechanisms = self._normalize_mechanism_cards(
                pick.get("mechanisms") or [],
                scope="occasion",
            ) or self._default_pick_mechanisms(pick, fallback_mechanisms)
            if mechanisms:
                row["mechanisms"] = mechanisms
            normalized.append(row)
        return self.emitter.data_update({"topPicks": normalized}, path="/data/occasion")

    def emit_occasion_analysis(self, analysis: dict[str, Any]) -> str:
        def _titlecase_element(s: Any) -> str:
            if not isinstance(s, str):
                return ""
            return s.strip().capitalize()

        key_elems = analysis.get("key_elements") or analysis.get("keyElements") or []
        avoid_elems = analysis.get("avoid_elements") or analysis.get("avoidElements") or []
        normalized = {
            "occasionType": analysis.get("occasion_type") or analysis.get("occasionType"),
            "keyElements": [_titlecase_element(x) for x in key_elems if x],
            "avoidElements": [_titlecase_element(x) for x in avoid_elems if x],
            "description": analysis.get("description", ""),
        }
        return self.emitter.data_update({"analysis": normalized}, path="/data/occasion")

    def emit_occasion_mechanisms(self, mechs: list[dict[str, Any]]) -> str:
        normalized = self._normalize_mechanism_cards(mechs, scope="occasion")
        return self.emitter.data_update({"mechanisms": normalized}, path="/data/occasion")

    # --- Luck Cycle ---
    def emit_luck_cycle_current_window(
        self,
        window: dict[str, Any],
        *,
        luck_pillars: list[Any] | None = None,
    ) -> str:
        active = self._active_luck_pillar(luck_pillars or [])
        active_decade = None
        active_element = None
        active_cycle = None
        if active is not None:
            start_year = active.start_year if hasattr(active, "start_year") else active["start_year"]
            end_year = active.end_year if hasattr(active, "end_year") else active["end_year"]
            stem = active.stem if hasattr(active, "stem") else active["stem"]
            branch = active.branch if hasattr(active, "branch") else active["branch"]
            stem_element = active.stem_element if hasattr(active, "stem_element") else active["stem_element"]
            branch_element = active.branch_element if hasattr(active, "branch_element") else active["branch_element"]
            active_decade = f"{start_year}-{end_year}"
            active_element = stem_element or branch_element
            active_cycle = f"{stem}{branch}"

        summary = window.get("summary")
        if not summary:
            if active_cycle and active_element:
                summary = f"Active decade {active_cycle} emphasizes {active_element.lower()} themes."
            elif active_cycle:
                summary = f"Active decade {active_cycle} is shaping the current timing."
            else:
                summary = "Active cycle analysis is pending."
        return self.emitter.data_update({
            "currentWindow": {
                "decade": window.get("decade") or active_decade or "Pending",
                "score": window.get("score") if isinstance(window.get("score"), (int, float)) else 0,
                "summary": summary,
                "element": window.get("element") or active_element or "Unknown",
            }
        }, path="/data/luckCycle")

    def emit_luck_cycle_timeline(
        self,
        *,
        luck_pillars: list[Any] | None = None,
        annual_pillars: list[Any] | None = None,
    ) -> str:
        return self.emitter.data_update(
            {
                "timeline": {
                    "decades": [self._normalize_luck_pillar_item(lp) for lp in (luck_pillars or [])],
                    "years": [self._normalize_annual_pillar_item(ap) for ap in (annual_pillars or [])],
                    "months": [],
                }
            },
            path="/data/luckCycle",
        )

    def emit_luck_cycle_mechanisms(self, mechs: list[dict[str, Any]]) -> str:
        normalized = self._normalize_mechanism_cards(mechs, scope="luck_cycle")
        return self.emitter.data_update({"mechanisms": normalized}, path="/data/luckCycle")

    # --- Wish ---
    def emit_wish_verdict(self, verdict: dict[str, Any]) -> str:
        return self.emitter.data_update({
            "verdict": {
                "title": verdict.get("title"),
                "score": verdict.get("score"),
                "summary": verdict.get("summary"),
                "caution": verdict.get("caution"),
                "conditions": self._normalize_wish_conditions(verdict.get("conditions", [])),
            }
        }, path="/data/wish")

    def emit_wish_anchors(self, anchors: list[dict[str, Any]]) -> str:
        normalized = [{
            "id": a.get("id"),
            "label": a.get("label"),
            "symbol": a.get("symbol"),
            "element": a.get("element"),
            "relevance": self._normalize_relevance(a.get("relevance")),
            "bullets": a.get("bullets", []),
        } for a in anchors]
        return self.emitter.data_update({"anchors": normalized}, path="/data/wish")

    def emit_wish_mechanisms(self, mechs: list[dict[str, Any]]) -> str:
        normalized = self._normalize_mechanism_cards(mechs, scope="wish")
        return self.emitter.data_update({"mechanisms": normalized}, path="/data/wish")

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
        # Include year predictions from EnrichedNarrativeOutput
        year_preds = narrative_data.get("year_predictions", [])
        year_predictions = [
            {
                "year": yp.get("year"),
                "prediction": yp.get("prediction", ""),
                "confidence": yp.get("confidence", 0),
                "evidenceRefs": yp.get("evidence_refs", []),
            }
            for yp in year_preds
        ]

        return self.emitter.data_update(
            {
                "tldr": narrative_data.get("tldr", ""),
                "insights": insights,
                "yearPredictions": year_predictions,
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
        normalized = [self._normalize_luck_pillar_item(lp) for lp in luck_pillars]
        return self.emitter.data_update({"items": normalized}, path="/data/luckPillars")

    def emit_annual_pillars(self, annual_pillars: list[Any]) -> str:
        """Emit annual pillars (流年)."""
        normalized = [self._normalize_annual_pillar_item(ap) for ap in annual_pillars]
        return self.emitter.data_update({"items": normalized}, path="/data/annualPillars")

    def emit_retrodictions(self, retrodictions: list[Any]) -> str:
        """Emit Spooky Accuracy retrodictions."""
        normalized = [
            {
                "year": r.year if hasattr(r, "year") else r["year"],
                "prediction": r.prediction if hasattr(r, "prediction") else r["prediction"],
                "interactionType": r.interaction_type if hasattr(r, "interaction_type") else r["interaction_type"],
                "interactionDescription": r.interaction_description if hasattr(r, "interaction_description") else r["interaction_description"],
                "affectedPillar": r.affected_pillar if hasattr(r, "affected_pillar") else r["affected_pillar"],
                "confidence": r.confidence if hasattr(r, "confidence") else r["confidence"],
            }
            for r in retrodictions
        ]
        return self.emitter.data_update({"items": normalized}, path="/data/retrodictions")

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
            "kind": self._trace_kind(data.get("step_type")),
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
                "kind": self._trace_kind(s.step_type if hasattr(s, "step_type") else s.get("step_type", "")),
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

    def emit_progress(self, phase: str, message: str) -> str:
        """Emit a progress event so the frontend can show phase status."""
        return self.emitter.data_update(
            {
                "phase": phase,
                "message": message,
                "percent": self._progress_percent(phase, message),
            },
            path="/data/meta/progress",
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
        """Terminal error: set status + audit event + done signal.

        Must include '{"done": true}' so the frontend useA2UIStream hook
        cleanly closes the EventSource instead of retrying 5 times.
        """
        return [
            self.emitter.data_update(
                {"status": "error", "error_message": message},
                path="/data/meta",
            ),
            self.emitter.audit("error", details=message),
            '{"done": true}',
        ]
