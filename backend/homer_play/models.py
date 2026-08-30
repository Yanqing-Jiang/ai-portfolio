from __future__ import annotations

import html
import re
import unicodedata
from datetime import datetime
from typing import Annotated, Any, Literal, Union
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    Tag,
    TypeAdapter,
    field_validator,
)


HTML_RE = re.compile(r"<[^>]+>")
BIDI_OVERRIDE_CHARS = frozenset("\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def normalize_message(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    if "\x00" in value or any(char in BIDI_OVERRIDE_CHARS for char in value):
        raise ValueError("message contains a prohibited control character")
    value = "".join(
        char
        for char in value
        if char in "\t\n\r" or not unicodedata.category(char).startswith("C")
    ).strip()
    if not value:
        raise ValueError("message cannot be empty")
    if HTML_RE.search(value) or HTML_RE.search(html.unescape(value)):
        raise ValueError("HTML is not accepted")
    return value


class CommonRequest(StrictModel):
    version: Literal["1"]
    tab: str
    action: str
    message: str = Field(min_length=1, max_length=500)
    input: StrictModel
    client_turn_id: UUID | None = None

    @field_validator("message")
    @classmethod
    def _normalize_message(cls, value: str) -> str:
        return normalize_message(value)


class MemorySearchInput(StrictModel):
    limit: int = Field(default=4, ge=1, le=4)


class MemoryExtractInput(StrictModel):
    target: Literal["architecture"] = "architecture"


class SchedulerQueryInput(StrictModel):
    max_jobs: int = Field(default=8, ge=1, le=8)
    max_runs_per_job: int = Field(default=3, ge=1, le=3)


class ExecutorRouteInput(StrictModel):
    answer_max_tokens: int = Field(default=160, ge=1, le=160)


class McpListInput(StrictModel):
    pass


class McpCallInput(StrictModel):
    # Kept as a constrained string so an unknown tool reaches the explicit
    # allowlist check and returns 403 rather than becoming a schema-level 400.
    tool: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    arguments: dict[str, Any]


class McpMemorySearchArguments(StrictModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=3, ge=1, le=4)

    @field_validator("query")
    @classmethod
    def _normalize_query(cls, value: str) -> str:
        return normalize_message(value)


class McpScheduleStatusArguments(StrictModel):
    status: Literal["all", "success", "failed", "running"] = "all"
    since_hours: Literal[1, 24, 168] = 24
    include_next_run: bool = False


class McpRuntimeStatusArguments(StrictModel):
    window: Literal["1h", "24h", "7d"] = "24h"
    view: Literal["overview", "threads", "runs", "events"] = "overview"


MCP_ARGUMENT_MODEL_BY_TOOL: dict[str, type[StrictModel]] = {
    "memory_search": McpMemorySearchArguments,
    "public_schedule_status": McpScheduleStatusArguments,
    "public_runtime_status": McpRuntimeStatusArguments,
}


class VoiceInput(StrictModel):
    format: Literal["ogg_opus"] = "ogg_opus"


class WebActivityInput(StrictModel):
    window: Literal["1h", "24h", "7d"] = "24h"


class MemorySearchRequest(CommonRequest):
    tab: Literal["memory"]
    action: Literal["search"]
    input: MemorySearchInput


class MemoryExtractRequest(CommonRequest):
    tab: Literal["memory"]
    action: Literal["extract_dry_run"]
    input: MemoryExtractInput


class SchedulerQueryRequest(CommonRequest):
    tab: Literal["scheduler"]
    action: Literal["query"]
    input: SchedulerQueryInput


class ExecutorRouteRequest(CommonRequest):
    tab: Literal["executors"]
    action: Literal["route_and_answer"]
    input: ExecutorRouteInput


class McpListRequest(CommonRequest):
    tab: Literal["mcp"]
    action: Literal["list_tools"]
    input: McpListInput


class McpCallRequest(CommonRequest):
    tab: Literal["mcp"]
    action: Literal["call_tool"]
    input: McpCallInput


class VoiceRequest(CommonRequest):
    tab: Literal["voice"]
    action: Literal["synthesize"]
    message: str = Field(min_length=1, max_length=80)
    input: VoiceInput


class WebActivityRequest(CommonRequest):
    tab: Literal["web"]
    action: Literal["activity"]
    input: WebActivityInput


def _tab_action(value: Any) -> str | None:
    if isinstance(value, dict):
        tab, action = value.get("tab"), value.get("action")
    else:
        tab, action = getattr(value, "tab", None), getattr(value, "action", None)
    if isinstance(tab, str) and isinstance(action, str):
        return f"{tab}.{action}"
    return None


PlayRequest = Annotated[
    Union[
        Annotated[MemorySearchRequest, Tag("memory.search")],
        Annotated[MemoryExtractRequest, Tag("memory.extract_dry_run")],
        Annotated[SchedulerQueryRequest, Tag("scheduler.query")],
        Annotated[ExecutorRouteRequest, Tag("executors.route_and_answer")],
        Annotated[McpListRequest, Tag("mcp.list_tools")],
        Annotated[McpCallRequest, Tag("mcp.call_tool")],
        Annotated[VoiceRequest, Tag("voice.synthesize")],
        Annotated[WebActivityRequest, Tag("web.activity")],
    ],
    Discriminator(_tab_action),
]
PLAY_REQUEST_ADAPTER = TypeAdapter(PlayRequest)


class SearchTrace(StrictModel):
    bm25_rank: int | None
    bm25_score: float | None
    vector_rank: int | None
    cosine: float | None
    rrf_score: float
    tier_multiplier: float
    recency_multiplier: float
    final_score: float


class SearchResult(StrictModel):
    id: str
    content: str
    claim_type: str
    target: str
    status: str
    created_at: str
    trace: SearchTrace


class SearchMeta(StrictModel):
    legs_used: list[Literal["bm25", "vector"]]
    corpus_size: int = Field(ge=0)
    fused_candidates: int = Field(ge=0)
    query_embedding_ms: int | None = Field(default=None, ge=0)


class MemorySearchData(StrictModel):
    query: str
    vector_leg: Literal["available", "unavailable"]
    results: list[SearchResult] = Field(max_length=4)
    meta: SearchMeta


class ExtractorInfo(StrictModel):
    name: str
    version: str


class CandidateRoute(StrictModel):
    tier: Literal["passive"]
    decision: Literal[
        "candidate",
        "duplicate",
        "possible_supersede",
        "dropped_noise",
        "conflict_check_unavailable",
    ]
    reason: str
    would_persist: Literal[False]


class CandidateMatch(StrictModel):
    public_claim_id: str
    content: str
    cosine: float = Field(ge=-1, le=1)
    relation: Literal["duplicate", "possible_supersede", "related"]


class ExtractCandidate(StrictModel):
    candidate_id: str
    content: str
    claim_type: str
    confidence: float = Field(ge=0, le=1)
    provenance: Literal["public_visitor_untrusted"]
    route: CandidateRoute
    matches: list[CandidateMatch]


class ExtractPolicy(StrictModel):
    corpus: Literal["public_sanitized_only"]
    conflict_threshold: float = Field(ge=0, le=1)
    writes_attempted: Literal[0]


class MemoryExtractData(StrictModel):
    extractor: ExtractorInfo
    candidates: list[ExtractCandidate]
    policy: ExtractPolicy


class InterpretedQuery(StrictModel):
    status: Literal["all", "success", "failed", "running"] = "all"
    since_hours: Literal[1, 24, 168] = 24
    job_ids: list[str] = Field(default_factory=list, max_length=8)
    include_next_run: bool = False

    @field_validator("job_ids")
    @classmethod
    def _validate_job_ids(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            candidate = value.strip().lower()
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", candidate):
                raise ValueError("job_ids must be lowercase public job identifiers")
            if candidate not in normalized:
                normalized.append(candidate)
        return normalized


class SchedulerRun(StrictModel):
    started_at: datetime
    outcome: Literal["success", "failed", "running"]
    duration_ms_bucket: Literal["<1s", "1-10s", "10-60s", "1-10m", "10m+"]


class SchedulerJob(StrictModel):
    id: str
    name: str
    kind: str
    cadence: str
    enabled: bool
    running: bool
    next_run_at: datetime | None
    last_success_at: datetime | None
    consecutive_failures_bucket: Literal["0", "1", "2-3", "4+"]
    recent_runs: list[SchedulerRun]


class SchedulerMeta(StrictModel):
    public_jobs_scanned: int = Field(ge=0)
    runs_scanned: int = Field(ge=0)


class SchedulerData(StrictModel):
    interpreted_query: InterpretedQuery
    jobs: list[SchedulerJob]
    meta: SchedulerMeta


class ExecutorClassification(StrictModel):
    task_type: str
    urgency: str
    estimated_tokens_bucket: str


class ExecutorRouting(StrictModel):
    logic: str
    chosen_executor: str
    chosen_model_family: str
    tier: str
    reason: str
    fallback_chain: list[str]
    would_execute_chosen_route: Literal[False]


class DemoExecution(StrictModel):
    executor: str
    model: str
    answer: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class ExecutorData(StrictModel):
    classification: ExecutorClassification
    routing: ExecutorRouting
    demo_execution: DemoExecution


class McpTool(StrictModel):
    name: Literal["memory_search", "public_schedule_status", "public_runtime_status"]
    description: str
    input_schema: dict[str, Any]
    data_source: Literal["public_corpus", "live_bridge"]
    side_effect_class: Literal["none"]


class McpListData(StrictModel):
    protocol: Literal["mcp"]
    tools: list[McpTool]
    hidden_tool_count: Literal[0]


class McpContent(StrictModel):
    type: Literal["text"]
    text: str


class McpTrace(StrictModel):
    allowlist_match: Literal[True]
    handler: str


class McpCallData(StrictModel):
    protocol: Literal["mcp"]
    tool: Literal["memory_search", "public_schedule_status", "public_runtime_status"]
    content: list[McpContent]
    structured_content: dict[str, Any]
    is_error: bool
    trace: McpTrace


class VoiceAudio(StrictModel):
    mime_type: Literal["audio/ogg; codecs=opus"]
    encoding: Literal["base64"]
    data: str
    bytes: int = Field(ge=0)
    duration_ms: int = Field(ge=0)


class VoiceInfo(StrictModel):
    provider: Literal["elevenlabs"]
    class_: Literal["licensed_stock_public_demo"] = Field(alias="class")
    model: str


class VoiceData(StrictModel):
    text: str
    audio: VoiceAudio
    voice: VoiceInfo
    characters_billed: int = Field(ge=0, le=80)


class ProviderShare(StrictModel):
    family: str
    share_bucket: str


class ThreadActivity(StrictModel):
    active_bucket: str
    created: int = Field(ge=0)
    messages: int = Field(ge=0)
    providers: list[ProviderShare]


class RunCounts(StrictModel):
    completed: int = Field(ge=0)
    failed: int = Field(ge=0)
    running: int = Field(ge=0)


class EventKindCount(StrictModel):
    kind: str
    count: int = Field(ge=0)


class WebActivityCounts(StrictModel):
    cli_runs: RunCounts
    scheduled_runs: RunCounts
    events_by_kind: list[EventKindCount]


class Freshness(StrictModel):
    db_observed_at: datetime
    cache_age_seconds: int = Field(ge=0)


class WebActivityData(StrictModel):
    window: Literal["1h", "24h", "7d"]
    as_of: datetime
    threads: ThreadActivity
    activity: WebActivityCounts
    freshness: Freshness


class Receipt(StrictModel):
    source: Literal["public_corpus", "live_bridge", "homer_code", "elevenlabs"]
    observed_at: datetime
    read_only: Literal[True]
    persisted: Literal[False]


class Limits(StrictModel):
    remaining_this_hour: int = Field(ge=0, le=10)
    reset_at: datetime


class Spend(StrictModel):
    reserved_usd: float = Field(ge=0)
    charged_usd: float = Field(ge=0)
    daily_cap_usd: float = Field(gt=0)


class Degraded(StrictModel):
    active: Literal[True]
    reason: Literal[
        "not_yet_enabled",
        "daily_spend_cap",
        "rate_backend_unavailable",
        "bridge_unavailable",
        "provider_unavailable",
        "live_timeout",
        "stale_projection",
    ]
    replay_id: str
    captured_at: datetime
    live_data_age_seconds: int | None = Field(default=None, ge=0)


class CommonSuccess(StrictModel):
    ok: Literal[True]
    version: Literal["1"]
    request_id: UUID
    tab: str
    action: str
    mode: Literal["live", "degraded"]
    reply: str
    data: StrictModel
    receipt: Receipt
    limits: Limits
    spend: Spend
    degraded: Degraded | None


class MemorySearchResponse(CommonSuccess):
    tab: Literal["memory"]
    action: Literal["search"]
    data: MemorySearchData


class MemoryExtractResponse(CommonSuccess):
    tab: Literal["memory"]
    action: Literal["extract_dry_run"]
    data: MemoryExtractData


class SchedulerResponse(CommonSuccess):
    tab: Literal["scheduler"]
    action: Literal["query"]
    data: SchedulerData


class ExecutorResponse(CommonSuccess):
    tab: Literal["executors"]
    action: Literal["route_and_answer"]
    data: ExecutorData


class McpListResponse(CommonSuccess):
    tab: Literal["mcp"]
    action: Literal["list_tools"]
    data: McpListData


class McpCallResponse(CommonSuccess):
    tab: Literal["mcp"]
    action: Literal["call_tool"]
    data: McpCallData


class VoiceResponse(CommonSuccess):
    tab: Literal["voice"]
    action: Literal["synthesize"]
    data: VoiceData


class WebActivityResponse(CommonSuccess):
    tab: Literal["web"]
    action: Literal["activity"]
    data: WebActivityData


PlaySuccessResponse = Annotated[
    Union[
        Annotated[MemorySearchResponse, Tag("memory.search")],
        Annotated[MemoryExtractResponse, Tag("memory.extract_dry_run")],
        Annotated[SchedulerResponse, Tag("scheduler.query")],
        Annotated[ExecutorResponse, Tag("executors.route_and_answer")],
        Annotated[McpListResponse, Tag("mcp.list_tools")],
        Annotated[McpCallResponse, Tag("mcp.call_tool")],
        Annotated[VoiceResponse, Tag("voice.synthesize")],
        Annotated[WebActivityResponse, Tag("web.activity")],
    ],
    Discriminator(_tab_action),
]
PLAY_SUCCESS_ADAPTER = TypeAdapter(PlaySuccessResponse)


RESPONSE_MODEL_BY_KEY: dict[str, type[CommonSuccess]] = {
    "memory.search": MemorySearchResponse,
    "memory.extract_dry_run": MemoryExtractResponse,
    "scheduler.query": SchedulerResponse,
    "executors.route_and_answer": ExecutorResponse,
    "mcp.list_tools": McpListResponse,
    "mcp.call_tool": McpCallResponse,
    "voice.synthesize": VoiceResponse,
    "web.activity": WebActivityResponse,
}


class ErrorDetail(StrictModel):
    code: Literal[
        "invalid_request",
        "tool_not_allowed",
        "unsafe_voice_text",
        "payload_too_large",
        "rate_limited",
        "service_unavailable",
    ]
    message: str
    retryable: bool
    fields: dict[str, str] | None = None


class ErrorResponse(StrictModel):
    ok: Literal[False]
    request_id: UUID
    error: ErrorDetail
    limits: Limits | None = None
