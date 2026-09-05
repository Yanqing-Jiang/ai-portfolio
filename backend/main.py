import asyncio
import logging
from typing import Any, Dict, List, Literal, Optional
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response, JSONResponse, FileResponse
from pydantic import BaseModel, EmailStr, Field
from pathlib import Path
import os
from dotenv import load_dotenv
import json
from datetime import datetime as _DateTime, timezone, timedelta
from zoneinfo import ZoneInfo
import uuid
import time
import threading
try:
    import stripe  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    stripe = None  # type: ignore
import httpx

from sse_utils import with_heartbeat

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
AI_FACTS_PATH = BASE_DIR / "public" / "ai-projects.json"
# Patterns for monitoring/telemetry (which UAs do we track in logs).
AI_CRAWLER_PATTERNS = (
    "oai-searchbot",
    "chatgpt-user",
    "gptbot",
    "claude-searchbot",
    "claude-user",
    "claudebot",
    "perplexitybot",
    "perplexity-user",
    "google-agent",
    "google-extended",
    "bytespider",
    "dataforseobot",
    "amazonbot",
)
# Crawlers we intentionally permit (search/retrieval + user-triggered ONLY).
# Training crawlers (gptbot, claudebot, google-extended, ccbot) are intentionally
# NOT allowlisted per Tw93 GEO playbook (2026-05-03). They are monitored above
# for observability but not given preferential routing.
AI_CRAWLER_ALLOWLIST = {
    "oai-searchbot",
    "claude-searchbot",
    "perplexitybot",
    "chatgpt-user",
    "claude-user",
    "perplexity-user",
    "google-agent",
}

_ai_facts_cache: Optional[List[Dict[str, Any]]] = None
_ai_facts_mtime: float = 0.0

# Always load the .env file located in the backend directory (same folder as this file)
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_PROMPT_PACK = os.getenv("STRIPE_PRICE_PROMPT_PACK")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_TOKEN_UNITS = int(os.getenv("STRIPE_TOKEN_UNITS", "100"))
if STRIPE_SECRET_KEY and stripe:
    stripe.api_key = STRIPE_SECRET_KEY

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID")
PAYPAL_ENV = os.getenv("PAYPAL_ENV", "sandbox").lower()
PAYPAL_TOKEN_UNITS = int(os.getenv("PAYPAL_TOKEN_UNITS", "100"))

# Booking / consulting configuration
STRIPE_PRICE_30MIN = os.getenv("STRIPE_PRICE_30MIN", "")
STRIPE_PRICE_60MIN = os.getenv("STRIPE_PRICE_60MIN", "")
STRIPE_BOOKING_WEBHOOK_SECRET = os.getenv("STRIPE_BOOKING_WEBHOOK_SECRET", "")
SITE_ORIGIN = os.getenv("SITE_ORIGIN", "https://yanqing.app")
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL", "")
BOOKING_PRICE_MAP = {
    "30": STRIPE_PRICE_30MIN,
    "60": STRIPE_PRICE_60MIN,
}
BOOKING_AMOUNT_CENTS = {
    "30": 5000,   # $50
    "60": 9000,   # $90
}

from calendar_service import (
    get_available_slots,
    create_booking_event,
    delete_booking_event,
    BOOKING_TIMEZONE,
)
from telegram_service import send_booking_notification
from email_service import send_booking_confirmation_email, send_admin_booking_alert
from intake_agent import (
    run_turn as intake_run_turn,
    new_state as intake_new_state,
    sign_session as intake_sign_session,
    verify_session as intake_verify_session,
    clamp_brief as intake_clamp_brief,
    min_brief_ok as intake_min_brief_ok,
    fit_session_to_cap as intake_fit_session,
    intake_available,
    MAX_USER_TURNS,
    MAX_SESSION_TOKEN_CHARS,
)
from rate_limiter import parse_user_id, ParsedToken

# Booking DB pool (shares SUPABASE_DB_URL with token_store)
# Statuses whose rows OCCUPY their slot. Anything here must be excluded from
# availability and must block a competing insert; anything not here has released
# its time. `calendar_failed` belongs here and was missing: it is set after a
# successful payment when the calendar write fails, and the UI shows it as
# confirmed — so leaving it out re-offered a slot somebody had already paid for.
# `blocked` is the owner's own busy time (see BOOKING_NOTIFICATIONS.md).
BLOCKING_STATUSES = ("hold", "confirmed", "calendar_failed", "blocked")

# Statuses a client may cancel or reschedule. `calendar_failed` is a CONFIRMED
# booking that merely failed to get a calendar event — BookingCard.tsx already
# shows it as "Confirmed", so refusing to manage it handed the client a green
# badge with buttons that returned "Cannot cancel booking with status
# 'calendar_failed'". Unreachable while no calendar is connected; the moment one
# is, any Google hiccup mid-booking produces exactly this row.
MANAGEABLE_STATUSES = ("confirmed", "calendar_failed")

_BOOKING_TZ = ZoneInfo(BOOKING_TIMEZONE)

# One definition of the hold-expiry policy. Every path that reads or writes
# availability sweeps first, so this ran verbatim in three places and any change
# to the window had to be made three times to be true.
EXPIRE_STALE_HOLDS_SQL = """
    UPDATE bookings
    SET status = 'expired', updated_at = NOW()
    WHERE status = 'hold'
      AND created_at < NOW() - INTERVAL '30 minutes'
"""

_booking_pool: Optional[Any] = None
_booking_pool_lock = asyncio.Lock()


async def _get_booking_pool():
    """Get or create the asyncpg connection pool for bookings table."""
    global _booking_pool
    if _booking_pool is not None:
        return _booking_pool
    if not SUPABASE_DB_URL:
        logger.warning("[BOOKING] SUPABASE_DB_URL not configured — booking persistence disabled")
        return None
    async with _booking_pool_lock:
        if _booking_pool is not None:
            return _booking_pool
        try:
            import asyncpg
            from db_ssl import supabase_ssl_context
            ssl_ctx = supabase_ssl_context()
            _booking_pool = await asyncpg.create_pool(
                SUPABASE_DB_URL,
                min_size=1,
                max_size=5,
                ssl=ssl_ctx,
                statement_cache_size=0,  # pgbouncer compatibility
            )
            logger.info("[BOOKING] Database pool initialized")
            return _booking_pool
        except Exception as exc:
            logger.error("[BOOKING] Database pool creation failed: %s", exc)
            return None


def _extract_user_uuid(identifier: str) -> Optional[str]:
    if identifier.startswith("user:"):
        return identifier.split("user:", 1)[-1]
    return None


def _paypal_base_url() -> str:
    return "https://api-m.paypal.com" if PAYPAL_ENV == "live" else "https://api-m.sandbox.paypal.com"


async def _get_paypal_access_token() -> str:
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        raise RuntimeError("PayPal credentials not configured")

    auth = httpx.BasicAuth(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET)
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{_paypal_base_url()}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=auth,
        )
        response.raise_for_status()
        data = response.json()
        return data["access_token"]


async def _paypal_verify_webhook(
    transmission_id: str,
    timestamp: str,
    signature: str,
    cert_url: str,
    webhook_id: str,
    event_body: str,
) -> bool:
    access_token = await _get_paypal_access_token()
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "transmission_id": transmission_id,
        "transmission_time": timestamp,
        "cert_url": cert_url,
        "auth_algo": "SHA256withRSA",
        "transmission_sig": signature,
        "webhook_id": webhook_id,
        "webhook_event": json.loads(event_body),
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{_paypal_base_url()}/v1/notifications/verify-webhook-signature",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("verification_status") == "SUCCESS"

from tts import get_voice_bytes
from gemini_service import gemini_service
try:
    from linkedin_photo import router as linkedin_photo_router
except ImportError:  # pragma: no cover - support running as module
    from .linkedin_photo import router as linkedin_photo_router  # type: ignore
from rate_limiter import (
    init_rate_limiter,
    smart_rate_limit,
    get_user_usage,
    who_am_i,
    resolve_scope,
    build_scoped_identifier,
    RateLimitScope,
    is_superuser,
    _guest_ip,
)
try:
    from token_store import token_store
except ImportError:  # pragma: no cover - support module execution
    from .token_store import token_store  # type: ignore
log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_name, logging.INFO)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)

app = FastAPI()
app.include_router(linkedin_photo_router)

# Conversational Analytics router (canonical analytics stack)
try:
    from conversational_analytics.routes import router as conv_analytics_router
    app.include_router(conv_analytics_router)
    logger.info("[STARTUP] Mounted Conversational Analytics router at /api/conv-analytics (canonical)")
except ImportError as e:
    logger.warning("[STARTUP] Conversational Analytics not available: %s", e)

# Generative UI - A2UI Dashboard router (2026 project)
try:
    from generative_ui.routes import dashboard_router as genui_router
    app.include_router(genui_router)
    logger.info("[STARTUP] Mounted Generative UI router at /api/dash (A2UI v0.8)")
except ImportError as e:
    logger.warning("[STARTUP] Generative UI not available: %s", e)

# Ming Engine - Fortune / BaZi reading router (2026 project)
try:
    from fortune import router as fortune_router
    app.include_router(fortune_router)
    logger.info("[STARTUP] Mounted Ming Engine router at /api/fortune")
except ImportError as e:
    logger.warning("[STARTUP] Ming Engine not available: %s", e)

# Homer memory search demo (static public-safe corpus, no private DB reads)
try:
    from homer_memory import router as homer_memory_router
    app.include_router(homer_memory_router)
    logger.info("[STARTUP] Mounted Homer memory search router at /api/homer/memory-search")
except ImportError as e:
    logger.warning("[STARTUP] Homer memory search not available: %s", e)

# Homer playable architecture (public policy/orchestration boundary)
try:
    from homer_play import router as homer_play_router
    app.include_router(homer_play_router)
    logger.info("[STARTUP] Mounted Homer play router at /api/homer/play")
except ImportError as e:
    logger.warning("[STARTUP] Homer play not available: %s", e)


@app.get("/health")
async def health():
    """Lightweight health check for deployment probes."""
    return {"status": "ok"}


@app.get("/project-showcase")
async def project_showcase():
    """Serve the conversational analytics project showcase HTML at a friendly URL."""
    static_path = Path(__file__).parent / "conversational_analytics" / "static" / "showcase.html"
    if not static_path.exists():
        raise HTTPException(status_code=404, detail="Showcase not found")
    return FileResponse(path=static_path, media_type="text/html")


@app.get("/api/analytics/canonical")
async def analytics_canonical():
    """Function: analytics_canonical — called by ops smoke checks and docs to confirm the canonical analytics router.
    Called from: deployment health checks and docs/analytics references.
    Invokes: no downstream services; returns the canonical router path and service label.
    Purpose: Advertise that Conversational Analytics is the primary analytics API surface."""
    return {
        "service": "conversational-analytics",
        "router": "/api/conv-analytics",
        "status": "healthy",
    }


def _match_ai_crawlers(user_agent: str) -> List[str]:
    if not user_agent:
        return []
    lowered = user_agent.lower()
    return [pattern for pattern in AI_CRAWLER_PATTERNS if pattern in lowered]


def load_ai_facts_cache() -> List[Dict[str, Any]]:
    global _ai_facts_cache, _ai_facts_mtime
    try:
        stat = AI_FACTS_PATH.stat()
    except FileNotFoundError:
        _ai_facts_cache = []
        _ai_facts_mtime = 0.0
        return _ai_facts_cache or []
    if _ai_facts_cache is None or stat.st_mtime > _ai_facts_mtime:
        with AI_FACTS_PATH.open(encoding="utf-8") as fp:
            _ai_facts_cache = json.load(fp)
        _ai_facts_mtime = stat.st_mtime
    return _ai_facts_cache or []

# Initialize rate limiter on startup
@app.on_event("startup")
async def startup_event():
    """
    Function: startup_event — initialize services on app startup.
    Called from: FastAPI lifespan.
    Invokes: init_rate_limiter, token_store.initialize, get_pool (prewarm), close_http_client.
    Why: Prewarm DB pool to avoid first-query latency; initialize rate limiter and token store.
    """
    await init_rate_limiter()
    await token_store.initialize()
    
    # Optimization #1: Prewarm DB pool to avoid first-query latency
    try:
        from shared_tools.sql_executor import get_pool
        from shared_tools.db_config import get_db_config
        config = get_db_config()
        if config.database_url:
            await get_pool()
            logger.info("[STARTUP] DB connection pool prewarmed successfully")
        else:
            logger.info("[STARTUP] DATABASE_URL not set; skipping DB pool prewarm")
    except Exception as e:
        logger.warning("[STARTUP] DB pool prewarm failed (non-fatal): %s", e)

    # Register the Ming Engine tracing processor for Glass Box durability.
    try:
        from fortune.tracing import ensure_registered as register_fortune_tracing
        register_fortune_tracing()
    except Exception as e:
        logger.warning("[STARTUP] Fortune trace processor registration failed: %s", e)

    # Override the default OpenAI client used by the openai-agents SDK so
    # long-running GPT-5.6 reasoning stages have headroom beyond the SDK's
    # default HTTP read timeout. The SSE path streams progress so the user UX
    # remains active while the underlying Responses call finishes.
    try:
        import os as _os
        from openai import AsyncOpenAI
        from agents import set_default_openai_client
        api_key = _os.getenv("OPENAI_API_KEY") or _os.getenv("FORTUNE_OPENAI_API_KEY")
        if api_key:
            set_default_openai_client(
                AsyncOpenAI(api_key=api_key, timeout=1200.0),
                use_for_tracing=True,
            )
            logger.info("[STARTUP] openai-agents SDK client timeout set to 1200s")
    except Exception as e:
        logger.warning("[STARTUP] openai-agents SDK client override failed: %s", e)

    # Sweep any fortune_run rows left in `queued` / `streaming` by a previous
    # worker that crashed mid-stream. Without this, replay keeps reporting
    # 'pending' forever and the Activity Rail shows a permanent spinner.
    async def _sweep_stuck_fortune_runs() -> None:
        try:
            from fortune.store import get_repository as _get_repo
            repo = await _get_repo()
            if not repo.available:
                return
            # 20 min buys enough headroom for a legitimately slow narrative
            # (~9s p50 + OpenAI tail) without rescuing truly dead runs too
            # late. If workloads shift, the right next step is a heartbeat
            # column on fortune_run that the stream loop touches each emit.
            records = await repo.sweep_stuck_run_records(older_than_minutes=20)
            if records:
                from fortune import events as _fortune_events
                message = "Reading interrupted by a service restart. Please retry."
                for record in records:
                    terminal_ok = await _fortune_events.publish_interrupted_terminal(
                        record["run_id"],
                        fortune_id=record["fortune_id"],
                        message=message,
                    )
                    record_ok = await _fortune_events.set_run_record(
                        record["run_id"],
                        fortune_id=record["fortune_id"],
                        status="interrupted",
                        error_message=message,
                    )
                    if terminal_ok and record_ok:
                        await repo.mark_run_recovery_published(
                            uuid.UUID(record["run_id"]),
                        )
                logger.info("[STARTUP] Swept %d stuck fortune_run rows", len(records))
        except Exception as exc:
            logger.warning("[STARTUP] stuck-run sweep failed: %s", exc)

    await _sweep_stuck_fortune_runs()

    # Periodic sweep so a crash mid-shift doesn't leave stragglers until next
    # boot. 5-minute cadence keeps the overhead negligible; the sweep itself
    # is a single indexed UPDATE.
    async def _periodic_stuck_sweep() -> None:
        import asyncio as _asyncio
        while True:
            try:
                await _asyncio.sleep(300)
                await _sweep_stuck_fortune_runs()
            except _asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("[STARTUP] periodic stuck-run sweep iteration failed: %s", exc)

    import asyncio as _asyncio
    app.state.fortune_stuck_sweep_task = _asyncio.create_task(_periodic_stuck_sweep())


@app.on_event("shutdown")
async def shutdown_event():
    """
    Function: shutdown_event — cleanup services on app shutdown.
    Called from: FastAPI lifespan.
    Invokes: token_store.shutdown, close_pool, close_http_client.
    Why: Clean shutdown of DB pool and HTTP clients to release resources.
    """
    await token_store.shutdown()

    # Cancel the periodic stuck-run sweep before closing the DB pool.
    sweep_task = getattr(app.state, "fortune_stuck_sweep_task", None)
    if sweep_task is not None:
        sweep_task.cancel()
        try:
            await sweep_task
        except Exception:
            pass

    # Close DB pool
    try:
        from shared_tools.sql_executor import close_pool
        await close_pool()
        logger.info("[SHUTDOWN] DB connection pool closed")
    except Exception as e:
        logger.warning("[SHUTDOWN] DB pool close failed: %s", e)

    # Drain outstanding trace span writes BEFORE closing the DB pool; the
    # processor writes through the fortune pool, so draining after a pool
    # close would be a no-op that loses the tail of the last trace.
    try:
        from fortune.tracing import flush_pending_spans
        await flush_pending_spans()
        logger.info("[SHUTDOWN] Fortune trace span writes flushed")
    except Exception as e:
        logger.warning("[SHUTDOWN] Fortune trace span flush failed: %s", e)

    # Close fortune Supabase pool
    try:
        from fortune.store import close_fortune_pool
        await close_fortune_pool()
        logger.info("[SHUTDOWN] Fortune Supabase pool closed")
    except Exception as e:
        logger.warning("[SHUTDOWN] Fortune Supabase pool close failed: %s", e)

    # Close fortune ask-session SQLAlchemy engine
    try:
        from fortune.session_store import close_ask_engine
        await close_ask_engine()
        logger.info("[SHUTDOWN] Fortune ask-session engine closed")
    except Exception as e:
        logger.warning("[SHUTDOWN] Fortune ask-session engine close failed: %s", e)

    # Close shared httpx client for news service
    try:
        from shared_tools.news_service import close_http_client
        await close_http_client()
        logger.info("[SHUTDOWN] News HTTP client closed")
    except Exception as e:
        logger.warning("[SHUTDOWN] News HTTP client close failed: %s", e)

# CORS: use CORS_ORIGINS env var in production, fall back to localhost for dev
_cors_env = os.getenv("CORS_ORIGINS", "")
origins = [o.strip() for o in _cors_env.split(",") if o.strip()] if _cors_env else [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
local_dev_origin_regex = None if _cors_env else r"^https?://(localhost|127\.0\.0\.1|\[::1\]):\d+$"
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=local_dev_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def ai_crawler_middleware(request: Request, call_next):
    user_agent = request.headers.get("user-agent", "")
    matches = _match_ai_crawlers(user_agent)
    if matches:
        logger.info(
            "[AI_CRAWLER] matches=%s path=%s allowed=%s",
            matches,
            request.url.path,
            bool(AI_CRAWLER_ALLOWLIST.intersection(matches)),
        )
        request.state.ai_crawler_matches = matches
    response = await call_next(request)
    if matches:
        response.headers["X-AI-Crawler-Matched"] = ",".join(matches)
        policy = "allow" if AI_CRAWLER_ALLOWLIST.intersection(matches) else "monitor"
        response.headers["X-AI-Crawler-Policy"] = policy
    return response

# Request model for TTS
class TTSRequest(BaseModel):
    text: str

# Request models for Gemini API
class GeminiChatRequest(BaseModel):
    system_instruction: str

class GeminiMessageRequest(BaseModel):
    message: str
    session_id: str

class StripeSessionRequest(BaseModel):
    success_url: str
    cancel_url: str


class PayPalOrderRequest(BaseModel):
    return_url: str
    cancel_url: str


class TokenSpendRequest(BaseModel):
    amount: int
    reference_id: Optional[str] = None
    source: Optional[str] = None


# Booking / consulting models
class BookingCheckoutRequest(BaseModel):
    session_type: Literal["30", "60"]
    slot_start: str  # ISO 8601 with timezone
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    notes: Optional[str] = Field(None, max_length=2000)
    intake_brief_id: Optional[str] = Field(None, max_length=64)


class IntakeMessageRequest(BaseModel):
    # The next user reply only. History is server-owned inside the signed
    # `session` token; the client cannot forge past turns or the turn count.
    path: Literal["business", "individual", "training"]
    # Cap sits above the true max token size (see intake_agent.MAX_SESSION_TOKEN_CHARS);
    # the old 16 KB cap 422'd valid server-issued tokens once the transcript grew.
    session: Optional[str] = Field(None, max_length=MAX_SESSION_TOKEN_CHARS)
    message: str = Field("", max_length=2000)


class IntakeBriefRequest(BaseModel):
    # Persisting a brief requires a valid signed intake session (proves a real
    # interview happened). The brief is the client-reviewed/edited version; it is
    # re-validated + clamped server-side before the write.
    session: str = Field(..., max_length=MAX_SESSION_TOKEN_CHARS)
    brief: dict = Field(default_factory=dict)
    name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=200)
    recommended_next_step: Optional[str] = Field(None, max_length=8)
    booking_id: Optional[str] = Field(None, max_length=64)


class FreeConsultRequest(BaseModel):
    """Free first-call booking (no payment). Mirrors the paid checkout
    request but skips Stripe — the 30-minute slot is confirmed directly."""
    slot_start: str  # ISO 8601 with timezone
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    notes: Optional[str] = Field(None, max_length=2000)
    intake_brief_id: Optional[str] = Field(None, max_length=64)


class BookingSlot(BaseModel):
    start: str
    end: str


class BookingSlotsResponse(BaseModel):
    slots: list[BookingSlot]
    timezone: str
    # False when POST /api/booking/free could not honour a pick — i.e. the
    # bookings table is unreachable, so nothing can hold the slot. The consult UI
    # offers an email fallback rather than let someone pick a time that cannot be
    # booked. A missing Google Calendar does NOT make a day unbookable.
    bookable: bool = True


class CancelBookingRequest(BaseModel):
    reason: str = ""


class RescheduleBookingRequest(BaseModel):
    new_slot_start: str  # ISO 8601 with timezone


class BookingEntry(BaseModel):
    id: str
    session_type: str
    slot_start: Optional[str] = None
    slot_end: Optional[str] = None
    status: str
    meet_link: Optional[str] = None
    amount_cents: int = 0
    created_at: Optional[str] = None
    can_cancel: bool = False
    can_reschedule: bool = False
    refund_eligible: bool = False


class MyBookingsResponse(BaseModel):
    bookings: list[BookingEntry]


class CancelBookingResponse(BaseModel):
    success: bool
    refunded: bool = False
    refund_amount_cents: int = 0
    message: str


class RescheduleBookingResponse(BaseModel):
    success: bool
    new_booking: Optional[BookingEntry] = None
    message: str = ""


# Auth dependency for booking management endpoints
async def require_auth(request: Request) -> ParsedToken:
    """Extract and verify Supabase JWT. Returns ParsedToken or raises 401."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authentication required.")
    parsed = parse_user_id(auth_header)
    if parsed is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return parsed


@app.get("/api/ai-facts.json")
async def ai_facts_endpoint():
    facts = load_ai_facts_cache()
    return JSONResponse(
        {
            "updated": _DateTime.utcnow().isoformat(),
            "count": len(facts),
            "facts": facts,
        }
    )


# -------------------- TTS Endpoint --------------------

@app.post("/api/tts")
async def tts_endpoint(request: TTSRequest):
    """Convert text to speech using ElevenLabs and return MP3 bytes."""
    try:
        audio_bytes = get_voice_bytes(request.text)
        return Response(content=audio_bytes, media_type="audio/mpeg", headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e:
        logger.error("TTS generation failed", exc_info=True)
        error_detail = {"error": str(e)}
        if os.getenv("ENVIRONMENT") != "production":
            import traceback
            error_detail["detail"] = traceback.format_exc()
        return JSONResponse(content=error_detail, status_code=500)

@app.post("/api/gemini/chat/create")
async def create_gemini_chat(request: GeminiChatRequest):
    """Create a new Gemini chat session"""
    try:
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # Create chat session using the improved service
        result = gemini_service.create_chat(session_id, request.system_instruction)
        
        if not result:
            return JSONResponse(
                content={"error": "Failed to create chat session - check if GEMINI_API_KEY is configured"}, 
                status_code=500, 
                headers={"Access-Control-Allow-Origin": "*"}
            )
        
        return JSONResponse(
            content={"session_id": session_id}, 
            headers={"Access-Control-Allow-Origin": "*"}
        )
        
    except Exception as e:
        logger.error("Gemini chat creation failed", exc_info=True)
        error_detail = {"error": str(e)}
        if os.getenv("ENVIRONMENT") != "production":
            import traceback
            error_detail["detail"] = traceback.format_exc()
        return JSONResponse(content=error_detail, status_code=500)

@app.get("/api/gemini/chat/stream")
async def gemini_chat_stream(session_id: str, message: str, request: Request):
    """Stream Gemini chat response with no buffering"""
    
    async def generate_stream():
        try:
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': '?? Gemini is thinking...', 'replace': False})}\n\n"
            await asyncio.sleep(0)
            
            chunk_count = 0
            current_text = ""
            
            # Stream response from improved Gemini service
            async for chunk in gemini_service.send_message_stream(session_id, message):
                if chunk:
                    try:
                        # Check for error messages
                        if chunk.startswith("Error:"):
                            yield f"data: {json.dumps({'type': 'error', 'message': chunk})}\n\n"
                            await asyncio.sleep(0)
                            break
                        
                        current_text += chunk
                        
                        # Send chunk immediately without buffering
                        yield f"data: {json.dumps({'type': 'response', 'text': chunk})}\n\n"
                        await asyncio.sleep(0)  # Force immediate flush
                        
                        chunk_count += 1
                        
                        # Prevent too many chunks (safety)
                        if chunk_count > 10000:
                            yield f"data: {json.dumps({'type': 'status', 'message': '?? Response truncated due to length', 'replace': True})}\n\n"
                            await asyncio.sleep(0)
                            break
                            
                    except Exception as chunk_error:
                        yield f"data: {json.dumps({'type': 'error', 'message': f'Chunk error: {str(chunk_error)}'})}\n\n"
                        await asyncio.sleep(0)
                        break
            
            # Send completion signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            await asyncio.sleep(0)
            
        except GeneratorExit:
            return
        except Exception as e:
            try:
                error_msg = f"Error during Gemini chat: {str(e)}"
                yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                await asyncio.sleep(0)
            except:
                return
    
    return StreamingResponse(
        with_heartbeat(generate_stream()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",  # Disable nginx buffering for no-stream buffering
        }
    )

@app.post("/api/gemini/chat/message")
async def send_gemini_message(request: GeminiMessageRequest):
    """Send message to Gemini chat (non-streaming)"""
    try:
        response = gemini_service.send_message_sync(request.session_id, request.message)
        
        if response.startswith("Error:"):
            return JSONResponse(
                content={"error": response}, 
                status_code=400, 
                headers={"Access-Control-Allow-Origin": "*"}
            )
        
        return JSONResponse(
            content={"response": response}, 
            headers={"Access-Control-Allow-Origin": "*"}
        )
        
    except Exception as e:
        logger.error("Gemini message failed", exc_info=True)
        error_detail = {"error": str(e)}
        if os.getenv("ENVIRONMENT") != "production":
            import traceback
            error_detail["detail"] = traceback.format_exc()
        return JSONResponse(content=error_detail, status_code=500)

@app.delete("/api/gemini/chat/{session_id}")
async def delete_gemini_chat(session_id: str):
    """Delete a Gemini chat session"""
    try:
        gemini_service.delete_chat(session_id)
        return JSONResponse(
            content={"message": "Chat session deleted"}, 
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        return JSONResponse(
            content={"error": str(e)}, 
            status_code=500, 
            headers={"Access-Control-Allow-Origin": "*"}
        )

# -------------------- Rate Limiting Endpoints --------------------

@app.post("/api/user-input")
async def count_user_input(request: Request):
    """Count a user input against a scoped rate limit without executing a workflow."""
    try:
        body = {}
        try:
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
        except Exception:
            body = {}
        
        scope = resolve_scope(body.get("scope"))
        weight_raw = body.get("weight", 1)
        try:
            weight = int(weight_raw)
        except (TypeError, ValueError):
            weight = 1
        if weight < 1:
            weight = 1
        elif weight > 1000:
            weight = 1000

        # Enforce the scoped rate limit before returning usage stats
        await smart_rate_limit(request, scope=scope, weight=weight)

        identifier = await who_am_i(request)
        scoped_identifier = build_scoped_identifier(identifier, scope)
        is_authenticated = not identifier.startswith("ip:")
        user_type = "member" if is_authenticated else "guest"

        snapshot = getattr(request.state, "rate_limit_snapshot", None)
        if snapshot is None:
            snapshot = await get_user_usage(identifier, scope)

        remaining = max(0, snapshot.limit - min(snapshot.count, snapshot.limit))
        daily_reset_iso = _DateTime.fromtimestamp(snapshot.reset_epoch, tz=timezone.utc).isoformat()
        token_fallback_used = bool(getattr(request.state, "token_fallback_used", False))

        token_balance = None
        token_balance_updated_at = None
        if is_authenticated and token_store.is_available:
            user_id = identifier.split("user:", 1)[-1] if ":" in identifier else None
            if user_id:
                balance = await token_store.get_balance(user_id)
                if balance is not None:
                    token_balance = balance.balance
                    if balance.updated_at:
                        token_balance_updated_at = balance.updated_at.isoformat()

        print(
            f"User input counted - Identifier: {identifier}, Scope: {scope.value}, "
            f"Scoped ID: {scoped_identifier}, Usage: {snapshot.count}/{snapshot.limit}, "
            f"Type: {user_type}, Weight: {weight}, TokensUsed: {token_fallback_used}"
        )

        return JSONResponse(
            content={
                "success": True,
                "scope": scope.value,
                "identifier": scoped_identifier,
                "base_identifier": identifier,
                "current_usage": snapshot.count,
                "limit": snapshot.limit,
                "remaining": remaining,
                "user_type": user_type,
                "prompt_units_spent_today": snapshot.count,
                "daily_reset_epoch": snapshot.reset_epoch,
                "daily_reset_iso": daily_reset_iso,
                "weight_applied": weight,
                "token_fallback_used": token_fallback_used,
                "token_balance": token_balance,
                "token_balance_updated_at": token_balance_updated_at,
                "daily_reset_notice": "Free daily quota resets at 00:00 UTC.",
                "message": "User input counted successfully"
            },
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        print(f"Error in count_user_input: {e}")
        return JSONResponse(
            content={"error": str(e)}, 
            status_code=500, 
            headers={"Access-Control-Allow-Origin": "*"}
        )

@app.get("/api/rate-limit/usage")
async def get_usage_stats(request: Request):
    """Get current rate limit usage for the user"""
    try:
        # Get user identifier
        identifier = await who_am_i(request)
        scope = resolve_scope(request.query_params.get("scope"))

        if is_superuser(request):
            scoped_identifier = build_scoped_identifier(identifier, scope)
            return JSONResponse(
                content={
                    "current_usage": 0,
                    "limit": 999999,
                    "remaining": 999999,
                    "user_type": "superuser",
                    "identifier": scoped_identifier,
                    "base_identifier": identifier,
                    "scope": scope.value,
                    "prompt_units_spent_today": 0,
                    "daily_reset_epoch": 0,
                    "daily_reset_iso": None,
                    "token_balance": None,
                    "token_balance_updated_at": None,
                    "daily_reset_notice": "Superuser — unlimited access.",
                },
                headers={"Access-Control-Allow-Origin": "*"},
            )

        # Get usage stats
        snapshot = await get_user_usage(identifier, scope)
        scoped_identifier = build_scoped_identifier(identifier, scope)
        
        # Determine user type
        is_authenticated = not identifier.startswith("ip:")
        user_type = "member" if is_authenticated else "guest"
        remaining = max(0, snapshot.limit - min(snapshot.count, snapshot.limit))
        daily_reset_iso = _DateTime.fromtimestamp(snapshot.reset_epoch, tz=timezone.utc).isoformat()

        token_balance = None
        token_balance_updated_at = None
        if is_authenticated and token_store.is_available:
            user_id = identifier.split("user:", 1)[-1] if ":" in identifier else None
            if user_id:
                balance = await token_store.get_balance(user_id)
                if balance is not None:
                    token_balance = balance.balance
                    if balance.updated_at:
                        token_balance_updated_at = balance.updated_at.isoformat()
        
        # Debug logging
        print(
            f"Usage stats - Identifier: {identifier}, Scope: {scope.value}, "
            f"Scoped ID: {scoped_identifier}, Usage: {snapshot.count}/{snapshot.limit}, "
            f"Type: {user_type}"
        )
        
        return JSONResponse(
            content={
                "current_usage": snapshot.count,
                "limit": snapshot.limit,
                "remaining": remaining,
                "user_type": user_type,
                "identifier": scoped_identifier,
                "base_identifier": identifier,
                "scope": scope.value,
                "prompt_units_spent_today": snapshot.count,
                "daily_reset_epoch": snapshot.reset_epoch,
                "daily_reset_iso": daily_reset_iso,
                "token_balance": token_balance,
                "token_balance_updated_at": token_balance_updated_at,
                "daily_reset_notice": "Free daily quota resets at 00:00 UTC.",
            },
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        print(f"Error in get_usage_stats: {e}")
        return JSONResponse(
            content={"error": str(e)}, 
            status_code=500, 
            headers={"Access-Control-Allow-Origin": "*"}
        )


@app.get("/api/token-balance")
async def get_token_balance(request: Request):
    """Return the user's purchased token balance along with daily quota info."""
    identifier = await who_am_i(request)
    user_id = _extract_user_uuid(identifier)
    if not user_id:
        raise HTTPException(status_code=401, detail="Sign in to view token balance.")

    snapshot = await get_user_usage(identifier, RateLimitScope.GLOBAL)
    daily_reset_iso = _DateTime.fromtimestamp(snapshot.reset_epoch, tz=timezone.utc).isoformat()

    if not token_store.is_available:
        return JSONResponse(
            content={
                "balance": 0,
                "balance_updated_at": None,
                "token_store_available": False,
                "daily_prompt_limit": snapshot.limit,
                "prompt_units_spent_today": snapshot.count,
                "daily_reset_epoch": snapshot.reset_epoch,
                "daily_reset_iso": daily_reset_iso,
                "daily_reset_notice": "Free daily quota resets at 00:00 UTC.",
            },
            headers={"Access-Control-Allow-Origin": "*"},
        )

    balance = await token_store.get_balance(user_id)
    balance_value = balance.balance if balance else 0
    balance_updated_at = balance.updated_at.isoformat() if balance and balance.updated_at else None

    return JSONResponse(
        content={
            "balance": balance_value,
            "balance_updated_at": balance_updated_at,
            "token_store_available": True,
            "daily_prompt_limit": snapshot.limit,
            "prompt_units_spent_today": snapshot.count,
            "daily_reset_epoch": snapshot.reset_epoch,
            "daily_reset_iso": daily_reset_iso,
            "daily_reset_notice": "Free daily quota resets at 00:00 UTC.",
        },
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.post("/api/token-spend")
async def spend_tokens(request: Request, payload: TokenSpendRequest):
    """Spend purchased prompt tokens manually."""
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive.")

    identifier = await who_am_i(request)
    user_id = _extract_user_uuid(identifier)
    if not user_id:
        raise HTTPException(status_code=401, detail="Sign in to spend tokens.")

    if not token_store.is_available:
        raise HTTPException(status_code=503, detail="Token store unavailable.")

    succeeded = await token_store.consume(user_id, payload.amount)
    if not succeeded:
        raise HTTPException(status_code=400, detail="Insufficient token balance.")

    balance = await token_store.get_balance(user_id)
    balance_value = balance.balance if balance else 0
    balance_updated_at = balance.updated_at.isoformat() if balance and balance.updated_at else None

    return JSONResponse(
        content={
            "success": True,
            "balance": balance_value,
            "balance_updated_at": balance_updated_at,
        },
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.post("/api/payments/stripe/session")
async def create_stripe_checkout_session(request: Request, payload: StripeSessionRequest):
    """Create a Stripe Checkout session for purchasing prompt tokens."""
    if stripe is None or not STRIPE_SECRET_KEY or not STRIPE_PRICE_PROMPT_PACK:
        raise HTTPException(status_code=503, detail="Stripe payments not configured.")

    identifier = await who_am_i(request)
    user_id = _extract_user_uuid(identifier)
    if not user_id:
        raise HTTPException(status_code=401, detail="Sign in to purchase tokens.")

    metadata = {"user_id": user_id, "token_units": str(STRIPE_TOKEN_UNITS)}

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": STRIPE_PRICE_PROMPT_PACK, "quantity": 1}],
            success_url=payload.success_url,
            cancel_url=payload.cancel_url,
            metadata=metadata,
            payment_intent_data={"metadata": metadata},
        )
    except Exception as exc:  # pragma: no cover - network/lib errors
        raise HTTPException(status_code=500, detail=f"Stripe session creation failed: {exc}") from exc

    return JSONResponse(
        content={"url": session.url, "session_id": session.id},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.post("/api/payments/stripe/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events to credit purchased tokens."""
    if stripe is None or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Stripe webhook not configured.")

    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    if sig_header is None:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header.")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid Stripe webhook: {exc}") from exc

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata") or {}
        user_id = metadata.get("user_id")
        token_units = int(metadata.get("token_units") or STRIPE_TOKEN_UNITS)
        reference_id = session.get("id")

        if user_id and token_units > 0 and token_store.is_available:
            await token_store.increment(
                user_id,
                token_units,
                source="stripe_checkout",
                reference_id=reference_id,
            )

    return JSONResponse(content={"received": True})


@app.post("/api/payments/paypal/order")
async def create_paypal_order(request: Request, payload: PayPalOrderRequest):
    """Create a PayPal order for purchasing prompt tokens."""
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="PayPal payments not configured.")

    identifier = await who_am_i(request)
    user_id = _extract_user_uuid(identifier)
    if not user_id:
        raise HTTPException(status_code=401, detail="Sign in to purchase tokens.")

    access_token = await _get_paypal_access_token()
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    body = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": str(uuid.uuid4()),
                "custom_id": user_id,
                "description": f"{PAYPAL_TOKEN_UNITS} prompt tokens",
                "amount": {"currency_code": "USD", "value": "1.00"},
            }
        ],
        "application_context": {
            "brand_name": "AI Portfolio",
            "shipping_preference": "NO_SHIPPING",
            "user_action": "PAY_NOW",
            "return_url": payload.return_url,
            "cancel_url": payload.cancel_url,
        },
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{_paypal_base_url()}/v2/checkout/orders",
            json=body,
            headers=headers,
        )

    if response.status_code >= 400:
        detail = response.text
        raise HTTPException(status_code=response.status_code, detail=f"PayPal order failed: {detail}")

    data = response.json()
    approve_link = next((link.get("href") for link in data.get("links", []) if link.get("rel") == "approve"), None)

    return JSONResponse(
        content={"id": data.get("id"), "approve_link": approve_link},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.post("/api/payments/paypal/webhook")
async def paypal_webhook(request: Request):
    """Handle PayPal webhook events."""
    if not PAYPAL_WEBHOOK_ID:
        raise HTTPException(status_code=503, detail="PayPal webhook not configured.")

    transmission_id = request.headers.get("PAYPAL-TRANSMISSION-ID")
    timestamp = request.headers.get("PAYPAL-TRANSMISSION-TIME")
    signature = request.headers.get("PAYPAL-TRANSMISSION-SIG")
    cert_url = request.headers.get("PAYPAL-CERT-URL")

    if not all([transmission_id, timestamp, signature, cert_url]):
        raise HTTPException(status_code=400, detail="Missing PayPal webhook headers.")

    body_bytes = await request.body()
    body_text = body_bytes.decode("utf-8")

    try:
        verified = await _paypal_verify_webhook(
            transmission_id,
            timestamp,
            signature,
            cert_url,
            PAYPAL_WEBHOOK_ID,
            body_text,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"PayPal verification failed: {exc}") from exc

    if not verified:
        raise HTTPException(status_code=400, detail="Invalid PayPal webhook signature.")

    event = json.loads(body_text)
    event_type = event.get("event_type")

    if event_type == "CHECKOUT.ORDER.APPROVED":
        order = event.get("resource", {})
        purchase_units = order.get("purchase_units") or []
        custom_id = purchase_units[0].get("custom_id") if purchase_units else None
        order_id = order.get("id")

        if custom_id and order_id and token_store.is_available:
            try:
                access_token = await _get_paypal_access_token()
                headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
                async with httpx.AsyncClient(timeout=10.0) as client:
                    capture_response = await client.post(
                        f"{_paypal_base_url()}/v2/checkout/orders/{order_id}/capture",
                        json={},
                        headers=headers,
                    )
                    capture_response.raise_for_status()
            except Exception as exc:
                print(f"PayPal capture failed for order {order_id}: {exc}")
                raise HTTPException(status_code=500, detail="Failed to capture PayPal order.")

            await token_store.increment(
                custom_id,
                PAYPAL_TOKEN_UNITS,
                source="paypal_checkout",
                reference_id=order_id,
            )

    return JSONResponse(content={"received": True})


# ---------------------------------------------------------------------------
# Booking / Consulting Endpoints
# ---------------------------------------------------------------------------
# The `bookings` table is defined by its migrations, which are immutable once
# applied: 001 creates it, 012 adds the tstzrange GiST exclusion constraint that
# is THE overlap fence (enforced on INSERT and UPDATE, so it holds even for a
# writer that forgets its app-level guard), 013 adds the partial unique index on
# stripe_event_id. See backend/migrations/. A copy of the DDL used to live here
# and had already drifted from the live schema within hours of being written.


@app.get("/api/booking/slots")
async def get_booking_slots(date: str, request: Request, session_type: str = "30"):
    """Return available booking slots for a given date.

    Queries Google Calendar freebusy API and checks Supabase bookings table
    for existing holds/confirmed bookings. Returns available 30-min slot
    boundaries.

    Query param `date`: YYYY-MM-DD format.
    Query param `session_type`: '30' or '60' (default '30').
    """
    from datetime import date as date_type

    # Generous enough for a visitor clicking through a month, tight enough that the
    # endpoint isn't a free availability-scraping API.
    _check_rate(request, "slots", 60, 30, "Too many availability requests. Please slow down.")

    if session_type not in ("30", "60"):
        raise HTTPException(status_code=400, detail="session_type must be '30' or '60'.")

    # Parse date
    try:
        target_date = date_type.fromisoformat(date)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    # Don't allow booking too far in the future (90 days) or in the past.
    # "Today" must be today in BOOKING_TIMEZONE, not in the container's clock: it
    # runs UTC, so every Pacific evening date_type.today() is already tomorrow and
    # a request for the current Pacific date 400'd as "in the past".
    today = _DateTime.now(ZoneInfo(BOOKING_TIMEZONE)).date()
    if target_date < today:
        raise HTTPException(status_code=400, detail="Cannot book dates in the past.")
    if (target_date - today).days > 90:
        raise HTTPException(status_code=400, detail="Cannot book more than 90 days in advance.")

    # Get slots from Google Calendar
    try:
        slots = await get_available_slots(target_date, session_type)
    except Exception as exc:
        logger.error("[BOOKING] Failed to get available slots: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve availability.")

    # Filter out slots that have holds or confirmed bookings in Supabase
    pool = await _get_booking_pool()
    db_filter_ok = True
    if pool is not None:
        try:
            # Expire stale holds first (lazy cleanup)
            async with pool.acquire() as conn:
                await conn.execute(EXPIRE_STALE_HOLDS_SQL)

                # Get all held/confirmed slot_starts for this date
                tz = ZoneInfo(BOOKING_TIMEZONE)
                day_start = _DateTime(
                    target_date.year, target_date.month, target_date.day,
                    0, 0, 0, tzinfo=tz,
                )
                day_end = _DateTime(
                    target_date.year, target_date.month, target_date.day,
                    23, 59, 59, tzinfo=tz,
                )
                # Overlap, not "starts within the day": an owner block can span a
                # whole day (or several), in which case its slot_start is BEFORE
                # this day began and a slot_start-range filter would miss it
                # entirely and re-offer blocked time.
                rows = await conn.fetch(
                    """
                    SELECT slot_start, slot_end
                    FROM bookings
                    WHERE status = ANY($3::text[])
                      AND slot_start < $2
                      AND slot_end > $1
                    """,
                    day_start, day_end, list(BLOCKING_STATUSES),
                )

                # Compare instants, never ISO strings: asyncpg hands back
                # timestamptz as UTC ("T20:00:00+00:00") while the offered slots
                # are in BOOKING_TIMEZONE ("T13:00:00-07:00"). Those are the same
                # moment and different text, so string matching silently kept
                # every booked slot on offer. Aware datetimes compare (and hash)
                # by instant, so this matches across offsets.
                booked: list[tuple[_DateTime, _DateTime]] = [
                    (row["slot_start"], row["slot_end"]) for row in rows
                ]

                # Exclude any offered slot that OVERLAPS a booked one, not just
                # one that starts at the same time: a 60-minute booking at 13:00
                # also consumes the 13:30 slot.
                def _is_free(slot: dict) -> bool:
                    start = _DateTime.fromisoformat(slot["start"])
                    end = _DateTime.fromisoformat(slot["end"])
                    return not any(b_start < end and b_end > start for b_start, b_end in booked)

                slots = [s for s in slots if _is_free(s)]
        except Exception as exc:
            # The bookings table is the only thing that knows a slot is taken
            # (more so with no calendar connected). If we cannot read it, we do
            # not know what is free — so offer nothing rather than offer a slot
            # the insert would reject with a 409 at the last click.
            logger.error("[BOOKING] DB slot check failed — offering nothing: %s", exc)
            slots = []
            db_filter_ok = False

    # A booking needs the hold/overlap store, or two visitors can take the same
    # slot and neither gets a record they can reschedule from. POST refuses in
    # that state, so the offer must not promise otherwise. A connected Google
    # Calendar is NOT required — availability is defined by the published hours
    # and narrowed by this table (see calendar_service._ruleset_available_slots);
    # without one the booking simply gets no event and no Meet link.
    persistence_ok = pool is not None or os.getenv("ENVIRONMENT") != "production"

    return BookingSlotsResponse(
        slots=[BookingSlot(**s) for s in slots],
        timezone=BOOKING_TIMEZONE,
        bookable=persistence_ok and db_filter_ok,
    )


@app.post("/api/booking/checkout")
async def create_booking_checkout(req: BookingCheckoutRequest, request: Request):
    """Create a Stripe Checkout Session for a consulting booking.

    Server-side pricing: maps session_type to Stripe Price ID.
    Revalidates slot availability against the published offer before holding.
    Inserts hold row into Supabase bookings table.
    Returns Stripe Checkout redirect URL.
    """
    if stripe is None or not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe payments not configured.")

    _check_rate(request, "checkout", 900, 5,
                "Too many checkout attempts. Please wait a few minutes and try again.")

    price_id = BOOKING_PRICE_MAP.get(req.session_type)
    if not price_id:
        raise HTTPException(status_code=503, detail=f"Stripe price not configured for {req.session_type}min sessions.")

    amount_cents = BOOKING_AMOUNT_CENTS.get(req.session_type, 0)

    # Parse and validate slot_start
    try:
        slot_start = _DateTime.fromisoformat(req.slot_start)
        if slot_start.tzinfo is None:
            raise ValueError("Timezone required")
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid slot_start: {exc}")

    # Validate slot is in the future
    if slot_start <= _DateTime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Cannot book a slot in the past.")

    # Revalidate against the published offer. Without this the docstring's promise
    # was false: this endpoint took ANY future instant, so a hand-rolled POST could
    # buy 3am Sunday, or a date years out, and get a real Stripe session for it.
    await _assert_slot_offered(slot_start, req.session_type)

    # Compute slot_end
    duration_minutes = 30 if req.session_type == "30" else 60
    from datetime import timedelta
    slot_end = slot_start + timedelta(minutes=duration_minutes)

    # Generate booking ID
    booking_id = str(uuid.uuid4())

    # Insert hold row into Supabase (with conflict check)
    pool = await _get_booking_pool()
    stripe_session_id_placeholder = f"pending_{booking_id}"

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                # Expire stale holds first
                await conn.execute(EXPIRE_STALE_HOLDS_SQL)

                # Same overlap-safe insert the free path uses. Previously this was a
                # plain INSERT relying on a unique index over identical slot_start,
                # so a 60-min checkout at 13:30 landed cleanly on top of an existing
                # 13:00-14:00 booking — no concurrency needed. Migration 012's
                # exclusion constraint is the backstop; this gives the friendly 409.
                try:
                    insert_status = await conn.execute(
                        """
                        INSERT INTO bookings (
                            id, stripe_session_id, session_type,
                            slot_start, slot_end, client_name, client_email,
                            notes, status, amount_cents
                        )
                        SELECT $1, $2, $3, $4, $5, $6, $7, $8, 'hold', $9
                        WHERE NOT EXISTS (
                            SELECT 1 FROM bookings
                            WHERE status = ANY($10::text[])
                              AND slot_start < $5
                              AND slot_end > $4
                        )
                        """,
                        uuid.UUID(booking_id),
                        stripe_session_id_placeholder,
                        req.session_type,
                        slot_start,
                        slot_end,
                        req.name,
                        req.email,
                        req.notes,
                        amount_cents,
                        list(BLOCKING_STATUSES),
                    )
                except Exception as db_exc:
                    logger.warning("[BOOKING] Slot conflict: %s", db_exc)
                    raise HTTPException(
                        status_code=409,
                        detail="This time slot is no longer available. Please choose another.",
                    )

                # "INSERT 0 0" => the NOT EXISTS guard blocked it. Without this
                # check the caller got a Stripe session for a slot never held.
                if insert_status.strip().endswith(" 0"):
                    raise HTTPException(
                        status_code=409,
                        detail="This time slot is no longer available. Please choose another.",
                    )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("[BOOKING] DB insert failed: %s", exc)
            raise HTTPException(status_code=500, detail="Booking system error. Please try again.")
    elif os.getenv("ENVIRONMENT") == "production":
        # The free path already refuses here; this one used to fall through and
        # take a PAYMENT for a slot nothing was holding — worse, because money
        # changes hands and the webhook then has no row to confirm.
        logger.error("[BOOKING] Refusing paid checkout: database unavailable in production")
        raise HTTPException(
            status_code=503,
            detail="Booking is temporarily unavailable. Please email "
                   "jiangyanqing91@gmail.com and Yanqing will set up the call directly.",
        )
    else:
        logger.warning("[BOOKING] No database — proceeding without hold (dev mode)")

    # Create Stripe Checkout Session
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": price_id, "quantity": 1}],
            expires_at=int(time.time()) + 1800,  # 30 minutes
            metadata={
                "booking_id": booking_id,
                "session_type": req.session_type,
                "slot_start": req.slot_start,
                "client_name": req.name,
                "client_email": req.email,
                "intake_brief_id": req.intake_brief_id or "",
            },
            customer_email=req.email,
            success_url=f"{SITE_ORIGIN}/consult?status=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{SITE_ORIGIN}/consult?cancelled=true",
        )
    except Exception as exc:
        logger.error("[BOOKING] Stripe session creation failed: %s", exc)
        # Clean up hold if Stripe fails
        if pool is not None:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE bookings SET status = 'expired', updated_at = NOW() WHERE id = $1",
                        uuid.UUID(booking_id),
                    )
            except Exception:
                pass
        raise HTTPException(status_code=500, detail="Payment session creation failed.")

    # Update hold with actual Stripe session ID
    if pool is not None:
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE bookings
                    SET stripe_session_id = $1, updated_at = NOW()
                    WHERE id = $2
                    """,
                    session.id,
                    uuid.UUID(booking_id),
                )
        except Exception as exc:
            logger.error("[BOOKING] Failed to update stripe_session_id: %s", exc)

    return JSONResponse(content={"url": session.url})


# In-process anti-automation for the de-walled unauthenticated endpoints.
# Keyed by the TRUSTED visitor IP (_guest_ip resolves the Cloudflare-forwarded
# caller when TRUST_FORWARDED_IP is on, not the tunnel peer) so buckets are
# per-visitor, and spoofed forwarding headers are rejected when trust is off.
# DEBT: in-memory / per-process — resets on restart. Upgrade to the Redis
# rate_limiter when it grows an unauthenticated per-endpoint mode.
_RATE_BUCKETS: dict[str, dict[str, list[float]]] = {}


def _rate_key(request: Request) -> str:
    return _guest_ip(request)


def _check_rate(request: Request, bucket: str, window_s: int, limit: int, detail: str) -> None:
    key = _rate_key(request)
    now = time.time()
    store = _RATE_BUCKETS.setdefault(bucket, {})
    hits = [t for t in store.get(key, []) if now - t < window_s]
    if len(hits) >= limit:
        raise HTTPException(status_code=429, detail=detail)
    hits.append(now)
    store[key] = hits


def _check_free_consult_rate(request: Request) -> None:
    _check_rate(request, "free_consult", 900, 6,
                "Too many booking attempts. Please wait a few minutes and try again.")


async def _ics_identity(conn, booking_id) -> tuple[str, int]:
    """Return (calendar UID, SEQUENCE) for a booking row.

    A reschedule creates a NEW row, but the client's calendar must MOVE the event
    it already has rather than gain a second one — and that only happens if the
    iCalendar UID stays the same and SEQUENCE increases. `rescheduled_from` chains
    each row to its predecessor, so the stable identity is the ROOT of that chain
    and the revision number is how far we are from it.
    """
    row = await conn.fetchrow(
        """
        WITH RECURSIVE chain AS (
            SELECT id, rescheduled_from, 0 AS depth
            FROM bookings WHERE id = $1
            UNION ALL
            SELECT b.id, b.rescheduled_from, c.depth + 1
            FROM bookings b JOIN chain c ON b.id = c.rescheduled_from
        )
        SELECT id::text AS root_id, depth FROM chain ORDER BY depth DESC LIMIT 1
        """,
        booking_id,
    )
    if row is None:                      # row vanished; fall back to its own id
        return str(booking_id), 0
    return row["root_id"], int(row["depth"])


async def _assert_slot_offered(slot_start: "_DateTime", session_type: str = "30") -> None:
    """Revalidate `slot_start` against the SAME availability source as
    GET /api/booking/slots (office hours, slot boundaries, 90-day horizon, and
    the calendar's busy periods when one is connected). Raises HTTPException if
    the instant is not a currently-offered slot start for `session_type`.

    `session_type` matters: the weekday grid is staggered, so the second slot of
    a 2-slot window is a valid 30-min start but NOT a valid 60-min start — the
    back half would spill into unpublished time. get_available_slots already
    enforces that adjacency, so passing the real duration is what makes this a
    revalidation rather than a rubber stamp.
    """

    tz = ZoneInfo(BOOKING_TIMEZONE)
    local_date = slot_start.astimezone(tz).date()

    # Today in booking time, not in the container's UTC clock (see get_booking_slots).
    today = _DateTime.now(tz).date()
    if local_date < today:
        raise HTTPException(status_code=400, detail="Cannot book a slot in the past.")
    if (local_date - today).days > 90:
        raise HTTPException(status_code=400, detail="Cannot book more than 90 days in advance.")

    try:
        offered = await get_available_slots(local_date, session_type)
    except Exception as exc:
        logger.error("[BOOKING] Availability lookup failed: %s", exc)
        raise HTTPException(status_code=503, detail="Availability is temporarily unavailable. Please try again.")

    for s in offered:
        try:
            if _DateTime.fromisoformat(s["start"]) == slot_start:
                return
        except (ValueError, TypeError, KeyError):
            continue
    raise HTTPException(
        status_code=409,
        detail="That time is no longer available. Please pick another slot.",
    )


@app.post("/api/booking/free")
async def create_free_consult(req: FreeConsultRequest, request: Request):
    """Book a FREE first 30-minute call (no payment).

    De-walled direct booking. The slot is server-side revalidated against the
    same availability source as the paid flow, rate-limited per IP, and only
    confirmed once the Google Calendar event is created — a calendar failure
    frees the slot and surfaces an error (never a false "confirmed"). Stored
    as a schema-valid 30-min booking with amount 0; the free/fit framing lives
    in notes + the admin alert. Intake context rides in `notes` and is copied
    to both admin recipients (D5).
    """
    _check_free_consult_rate(request)

    # Parse and validate slot_start (tz-aware, future)
    try:
        slot_start = _DateTime.fromisoformat(req.slot_start)
        if slot_start.tzinfo is None:
            raise ValueError("Timezone required")
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid slot_start: {exc}")

    if slot_start <= _DateTime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Cannot book a slot in the past.")

    # Enforce horizon / office hours / boundaries / calendar availability
    await _assert_slot_offered(slot_start)

    from datetime import timedelta
    slot_end = slot_start + timedelta(minutes=30)

    booking_id = str(uuid.uuid4())
    free_session_id = f"free_{booking_id}"

    pool = await _get_booking_pool()
    if pool is not None:
        try:
            async with pool.acquire() as conn:
                await conn.execute(EXPIRE_STALE_HOLDS_SQL)

                # Atomic overlap-safe insert: the overlap check and the insert are
                # ONE statement, so there is no app-level read-then-write gap
                # (session_type is stored schema-valid '30'; free/fit is encoded by
                # amount_cents = 0 and the 'free_' session id). 0 rows inserted =>
                # an overlapping occupied row exists, which we turn into a friendly
                # 409. Behind this, migration 012's tstzrange exclusion constraint
                # is the real fence: it holds under true concurrency and for any
                # writer that skips this guard.
                try:
                    insert_status = await conn.execute(
                        """
                        INSERT INTO bookings (
                            id, stripe_session_id, session_type,
                            slot_start, slot_end, client_name, client_email,
                            notes, status, amount_cents
                        )
                        SELECT $1, $2, '30', $3, $4, $5, $6, $7, 'hold', 0
                        WHERE NOT EXISTS (
                            SELECT 1 FROM bookings
                            WHERE status = ANY($8::text[])
                              AND slot_start < $4
                              AND slot_end > $3
                        )
                        """,
                        uuid.UUID(booking_id),
                        free_session_id,
                        slot_start,
                        slot_end,
                        req.name,
                        req.email,
                        req.notes,
                        list(BLOCKING_STATUSES),
                    )
                except Exception as db_exc:
                    # Lost a genuine race: the exclusion constraint refused it.
                    logger.warning("[BOOKING] Free-consult slot conflict: %s", db_exc)
                    raise HTTPException(
                        status_code=409,
                        detail="That time is no longer available. Please pick another slot.",
                    )

                # asyncpg returns a command tag like "INSERT 0 1"; "INSERT 0 0"
                # means the NOT EXISTS guard blocked it — the slot is taken.
                if insert_status.strip().endswith(" 0"):
                    raise HTTPException(
                        status_code=409,
                        detail="That time is no longer available. Please pick another slot.",
                    )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("[BOOKING] Free-consult DB insert failed: %s", exc)
            raise HTTPException(status_code=500, detail="Booking system error. Please try again.")
    elif os.getenv("ENVIRONMENT") == "production":
        # Without the bookings table there is no hold, so nothing stops two
        # visitors taking the same slot, and a confirmed call leaves no record to
        # reschedule or cancel from. Refuse rather than "confirm" that.
        logger.error("[BOOKING] Refusing free booking: database unavailable in production")
        raise HTTPException(
            status_code=503,
            detail="Booking is temporarily unavailable. Please email "
                   "jiangyanqing91@gmail.com and Yanqing will set up the call directly.",
        )
    else:
        logger.warning("[BOOKING] No database — proceeding without hold (dev mode)")

    # Create the calendar event, if a calendar is connected at all. With none,
    # this returns empty ids and the DB row alone confirms the booking (the owner
    # gets an "ACTION NEEDED — no Meet link" alert). With one connected, a failure
    # frees the slot and returns an error (B3 — never a false success).
    calendar_event_id = None
    meet_link = None
    try:
        cal_result = await create_booking_event(
            session_type="30",
            slot_start=slot_start,
            name=req.name,
            email=req.email,
            notes=req.notes,
        )
        calendar_event_id = cal_result.get("event_id")
        meet_link = cal_result.get("meet_link")
    except Exception as exc:
        logger.error("[BOOKING] Free-consult calendar event failed: %s", exc)
        if pool is not None:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE bookings SET status = 'expired', updated_at = NOW() WHERE id = $1",
                        uuid.UUID(booking_id),
                    )
            except Exception:
                pass
        # A prospect reached the last click and got nothing. Without this the
        # attempt is invisible — no booking row, no email, no Telegram.
        try:
            await send_admin_booking_alert(
                name=req.name, email=req.email,
                session_type="fit", slot_start=req.slot_start,
                notes=req.notes, meet_link=None,
                failure_reason=f"Calendar event creation failed: {exc}",
            )
        except Exception as alert_exc:
            logger.error("[BOOKING] Failed-attempt alert also failed: %s", alert_exc)
        raise HTTPException(
            status_code=502,
            detail="We couldn't confirm that time on the calendar. Please pick another slot — you have not been booked.",
        )

    # Promote the hold to a real booking. This is the step that makes the booking
    # exist, so its failure must NOT be swallowed: the row would stay 'hold', get
    # swept 30 minutes later, and quietly free the slot — while the visitor holds a
    # "confirmed" response and a confirmation email for a call with no record.
    # `AND status = 'hold'` makes it a compare-and-set: 0 rows means someone else
    # already expired or took this row, which is equally not a confirmation.
    if pool is not None:
        promoted = False
        try:
            async with pool.acquire() as conn:
                tag = await conn.execute(
                    """
                    UPDATE bookings
                    SET status = 'confirmed', calendar_event_id = $1, meet_link = $2, updated_at = NOW()
                    WHERE id = $3 AND status = 'hold'
                    """,
                    calendar_event_id,
                    meet_link,
                    uuid.UUID(booking_id),
                )
            promoted = not tag.strip().endswith(" 0")
        except Exception as exc:
            logger.error("[BOOKING] Free-consult status update failed: %s", exc)

        if not promoted:
            # Undo the calendar side so we don't leave a ghost event, tell the
            # owner, and refuse — the visitor is explicitly told they are NOT booked.
            if calendar_event_id:
                try:
                    await delete_booking_event(calendar_event_id)
                except Exception as exc:
                    logger.error("[BOOKING] Could not remove ghost calendar event %s: %s",
                                 calendar_event_id, exc)
            try:
                await send_admin_booking_alert(
                    name=req.name, email=req.email,
                    session_type="fit", slot_start=req.slot_start,
                    notes=req.notes, meet_link=None,
                    failure_reason="Hold could not be promoted to confirmed — booking refused",
                )
            except Exception as alert_exc:
                logger.error("[BOOKING] Failed-attempt alert also failed: %s", alert_exc)
            raise HTTPException(
                status_code=503,
                detail="We couldn't finish confirming that time — you have not been "
                       "booked. Please try again, or email jiangyanqing91@gmail.com.",
            )

    # Link the intake brief (if any) to this booking.
    await _link_brief_to_booking(req.intake_brief_id, booking_id, req.email)

    # Confirmed — fire notifications (session_type "fit" is a display-only label
    # for the admin alert; the DB row stays '30').
    try:
        await send_booking_notification(
            name=req.name, email=req.email,
            session_type="fit", slot_start=req.slot_start,
            notes=req.notes,
        )
    except Exception as exc:
        logger.error("[BOOKING] Telegram notification failed (non-blocking): %s", exc)

    # Both senders return False instead of raising, so the return value is the
    # ONLY signal that an email actually went out. Ignoring it made "confirmed"
    # mean "the DB row was written", not "both parties were told".
    owner_emailed = False
    try:
        owner_emailed = await send_admin_booking_alert(
            name=req.name, email=req.email,
            session_type="fit", slot_start=req.slot_start,
            notes=req.notes, meet_link=meet_link,
        )
    except Exception as exc:
        logger.error("[BOOKING] Admin email alert failed (non-blocking): %s", exc)

    requestor_emailed = False
    try:
        requestor_emailed = await send_booking_confirmation_email(
            name=req.name, email=req.email,
            session_type="30", slot_start=req.slot_start, meet_link=meet_link,
            notes=req.notes,
            # First revision of this booking's calendar entry; a later move or
            # cancellation reuses this UID so the client's calendar updates in place.
            kind="confirmed", booking_id=booking_id, ics_sequence=0,
        )
    except Exception as exc:
        logger.error("[BOOKING] Confirmation email failed (non-blocking): %s", exc)

    if not owner_emailed or not requestor_emailed:
        logger.error(
            "[BOOKING] Booking %s confirmed but notifications incomplete "
            "(owner=%s requestor=%s meet_link=%s) — the event exists, tell "
            "%s manually.",
            booking_id, owner_emailed, requestor_emailed, bool(meet_link), req.email,
        )

    return JSONResponse(content={
        "id": booking_id,
        "status": "confirmed",
        "meet_link": meet_link,
        "slot_start": req.slot_start,
        # The UI promises "a confirmation email is on its way" — it may only say
        # that when one actually was.
        "notification_status": {
            "owner_email": "sent" if owner_emailed else "failed",
            "requestor_email": "sent" if requestor_emailed else "failed",
        },
    })


# ---------------------------------------------------------------------------
# AI Brief Agent (Phase 2) — /consult intake chat
# ---------------------------------------------------------------------------

def _check_intake_rate(request: Request) -> None:
    # ~12-turn interview + a couple of retries; keyed per trusted visitor IP.
    _check_rate(request, "intake", 900, 40,
                "Too many messages. Please slow down and try again shortly.")


# Per-session turn ledger for replay defense. Signed tokens are stateless, so an
# OLD (or concurrently duplicated) token can be resubmitted to fork state and
# re-spend model calls below the 12-turn cap. The ledger records the highest turn
# already CONSUMED per `sid`; a token is accepted only if its turn strictly
# exceeds that. The check + record is a single atomic compare-and-set under a
# lock and happens BEFORE the model call, so two concurrent uses of the same
# token can't both spend. Pure server-side state is unavoidable for replay
# detection.
# DEBT: in-memory / per-process — a restart clears it, so tokens are replayable
# again until their ~2h TTL (intake_agent.SESSION_TTL_SECONDS) expires. Upgrade
# to Redis when the booking limiter grows a shared unauthenticated store.
_INTAKE_SESSION_TURNS: dict[str, tuple[int, float]] = {}
_INTAKE_LEDGER_LOCK = threading.Lock()
_INTAKE_LEDGER_MAX = 20000


def _prune_session_ledger(now: float) -> None:
    # Caller holds _INTAKE_LEDGER_LOCK.
    if len(_INTAKE_SESSION_TURNS) <= _INTAKE_LEDGER_MAX:
        return
    from intake_agent import SESSION_TTL_SECONDS
    stale = [k for k, (_, ts) in _INTAKE_SESSION_TURNS.items() if now - ts > SESSION_TTL_SECONDS]
    for k in stale:
        _INTAKE_SESSION_TURNS.pop(k, None)
    # Hard fallback if still oversized (all fresh): drop the oldest half.
    if len(_INTAKE_SESSION_TURNS) > _INTAKE_LEDGER_MAX:
        for k in sorted(_INTAKE_SESSION_TURNS, key=lambda k: _INTAKE_SESSION_TURNS[k][1])[: _INTAKE_LEDGER_MAX // 2]:
            _INTAKE_SESSION_TURNS.pop(k, None)


def _intake_reserve_turn(sid: str, turns: int) -> bool:
    """Atomic compare-and-set. Returns True and reserves `turns` for `sid` if it
    strictly advances the highest turn already consumed; False if it's a stale or
    concurrently-duplicated (replayed) token. Consuming BEFORE the model call is
    what stops two concurrent identical tokens from both spending."""
    now = time.time()
    with _INTAKE_LEDGER_LOCK:
        prev = _INTAKE_SESSION_TURNS.get(sid)
        if prev is not None and turns <= prev[0]:
            return False
        _INTAKE_SESSION_TURNS[sid] = (turns, now)
        _prune_session_ledger(now)
    return True


def _intake_release_turn(sid: str, turns: int) -> None:
    """Roll back a reservation whose turn never spent a model call (transient
    502): without this, retrying the same valid token would 409 forever. Only
    rolls back if our reservation is still the latest, and only to turns-1 —
    never below what any prior token had already consumed."""
    with _INTAKE_LEDGER_LOCK:
        cur = _INTAKE_SESSION_TURNS.get(sid)
        if cur is not None and cur[0] == turns:
            _INTAKE_SESSION_TURNS[sid] = (turns - 1, time.time())


def _require_bound_session(state: dict) -> None:
    """Hard-reject any signed token lacking a session id or numeric issued-at.
    Such tokens (pre-fix, never deployed) would otherwise bypass expiry + the
    replay ledger and retain indefinite-replay behavior."""
    if not state.get("sid") or not isinstance(state.get("iat"), (int, float)):
        raise HTTPException(status_code=401, detail="intake_session_invalid")


async def _link_brief_to_booking(brief_id: Optional[str], booking_id: str, email: Optional[str] = None) -> None:
    """Best-effort: attach a stored intake brief to the booking it produced."""
    if not brief_id:
        return
    pool = await _get_booking_pool()
    if pool is None:
        return
    try:
        bid = uuid.UUID(brief_id)
    except Exception:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE intake_briefs SET booking_id = $1, client_email = COALESCE($2, client_email) WHERE id = $3",
                booking_id, email, bid,
            )
    except Exception as exc:
        logger.error("[INTAKE] Failed to link brief %s to booking %s: %s", brief_id, booking_id, exc)


@app.post("/api/intake/message")
async def intake_message(req: IntakeMessageRequest, request: Request):
    """One turn of the guided intake interview.

    Server-authoritative: the transcript + turn count + running brief live in the
    signed `session` token, not in a client-supplied history. The browser sends
    only the next user reply. Scope-locked, turn-capped, rate-limited, output
    schema-validated. On any failure the client falls back to the guided form."""
    _check_intake_rate(request)

    if not intake_available():
        raise HTTPException(status_code=503, detail="intake_unavailable")

    # Resolve server-owned session state from the signed token (or start fresh).
    if req.session:
        state = intake_verify_session(req.session)
        if state is None:
            # Tampered or expired token — restart cleanly (client falls back or reseeds).
            raise HTTPException(status_code=400, detail="intake_session_invalid")
        # Path is fixed by the session, not the per-request field.
        if state.get("path") not in ("business", "individual", "training"):
            raise HTTPException(status_code=400, detail="intake_session_invalid")
        # Reject unbound legacy tokens (no sid/iat) outright — they'd bypass
        # expiry + the ledger. Then atomically reserve this turn BEFORE any model
        # call: a stale OR concurrently-duplicated token is a 409 (no double-spend).
        _require_bound_session(state)
        if not _intake_reserve_turn(state["sid"], int(state.get("turns", 0))):
            raise HTTPException(status_code=409, detail="intake_session_stale")
        reserved = (state["sid"], int(state.get("turns", 0)))
    else:
        state = intake_new_state(req.path)
        reserved = None

    # Server-enforced turn cap — cannot be bypassed by the client. run_turn already
    # ends the interview AT the last allowed answer, so reaching here means a client
    # kept talking past that. Answer with the same terminal state (complete + the
    # booking UI) rather than a dead end: the round budget is spent either way.
    if int(state.get("turns", 0)) >= MAX_USER_TURNS:
        brief = state.get("brief", {}) or {}
        return JSONResponse(content={
            "reply": "I've got enough to prepare your brief. Review it, correct anything I misread, then pick a time below.",
            "brief": brief,
            "quick_replies": [],
            "complete": True,
            "recommended_next_step": "fit",
            "ui": [
                {"kind": "calendar", "session_type": "fit"},
                {"kind": "contact"},
            ],
            "session": intake_sign_session(intake_fit_session({**state, "complete": True})),
            "capped": True,
        })

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: intake_run_turn(state, req.message))
        new_state = result.pop("state")
        result["session"] = intake_sign_session(new_state)
        return JSONResponse(content=result)
    except Exception as exc:
        # The turn never spent a model result — release the reservation so the
        # client can retry the same valid token instead of 409ing forever.
        if reserved is not None:
            _intake_release_turn(*reserved)
        logger.error("[INTAKE] Turn failed: %s", exc)
        raise HTTPException(status_code=502, detail="intake_error")


@app.post("/api/intake/brief")
async def intake_store_brief(req: IntakeBriefRequest, request: Request):
    """Persist a prospect-approved brief. Requires a valid signed intake session
    (proves a real interview) and re-validates/clamps the brief before writing —
    randoms cannot spray arbitrary JSON into the table. Rate-limited. Returns a
    brief_id the booking references. Never blocks the funnel on DB errors."""
    import hashlib

    _check_rate(request, "intake_brief", 900, 20,
                "Too many submissions. Please try again shortly.")

    # Gate on a valid, bound session token — no valid interview, no write.
    state = intake_verify_session(req.session)
    if state is None:
        raise HTTPException(status_code=400, detail="intake_session_invalid")
    _require_bound_session(state)
    path = state.get("path") if state.get("path") in ("business", "individual", "training") else "unknown"

    # Re-validate + clamp the (client-edited) brief server-side.
    brief = intake_clamp_brief(req.brief)
    step = req.recommended_next_step if req.recommended_next_step in ("fit", "30", "60") else None

    ip_hash = hashlib.sha256(_guest_ip(request).encode("utf-8")).hexdigest()[:32]

    pool = await _get_booking_pool()
    if pool is None:
        logger.warning("[INTAKE] No DB — brief not persisted (dev mode)")
        return JSONResponse(content={"brief_id": None, "stored": False})

    booking_uuid = None
    if req.booking_id:
        try:
            booking_uuid = uuid.UUID(req.booking_id)
        except Exception:
            booking_uuid = None

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO intake_briefs (path, brief, client_name, client_email, recommended_next_step, booking_id, source_ip_hash)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                path,
                json.dumps(brief),
                (req.name or None),
                (req.email or None),
                step,
                booking_uuid,
                ip_hash,
            )
        return JSONResponse(content={"brief_id": str(row["id"]), "stored": True})
    except Exception as exc:
        logger.error("[INTAKE] Brief persist failed (non-blocking): %s", exc)
        return JSONResponse(content={"brief_id": None, "stored": False})


@app.post("/api/booking/webhook")
async def booking_webhook(request: Request):
    """Handle Stripe webhook events for booking payments.

    Verifies Stripe signature with STRIPE_BOOKING_WEBHOOK_SECRET.
    Checks idempotency via stripe_event_id.
    Transitions hold -> confirmed, creates calendar event, sends Telegram notification.
    """
    if stripe is None or not STRIPE_BOOKING_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Booking webhook not configured.")

    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    if sig_header is None:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header.")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_BOOKING_WEBHOOK_SECRET)
    except Exception as exc:
        logger.error("[BOOKING] Invalid webhook signature: %s", exc)
        raise HTTPException(status_code=400, detail=f"Invalid Stripe webhook: {exc}") from exc

    if event["type"] != "checkout.session.completed":
        # We only care about completed checkouts for bookings
        return JSONResponse(content={"received": True})

    session_data = event["data"]["object"]
    stripe_session_id = session_data.get("id", "")
    event_id = event.get("id", "")
    metadata = session_data.get("metadata") or {}
    booking_id = metadata.get("booking_id", "")
    session_type = metadata.get("session_type", "30")
    slot_start_str = metadata.get("slot_start", "")
    client_name = metadata.get("client_name", "")
    client_email = metadata.get("client_email", "")

    pool = await _get_booking_pool()
    if pool is None:
        # 200 here told Stripe "handled" and it never retried, so a PAID booking
        # was lost for good. A 5xx makes Stripe redeliver, and this failure mode
        # (database briefly unreachable) is exactly what redelivery is for.
        logger.error("[BOOKING] No database — cannot process webhook, asking Stripe to retry")
        raise HTTPException(status_code=503, detail="Database unavailable; retry this event.")

    async with pool.acquire() as conn:
        # Find the booking by stripe_session_id
        booking = await conn.fetchrow(
            "SELECT id, status, client_name, client_email, session_type, slot_start, notes FROM bookings WHERE stripe_session_id = $1",
            stripe_session_id,
        )

        if booking is None:
            # Booking might have been created with pending_ prefix; try by booking_id
            if booking_id:
                try:
                    booking = await conn.fetchrow(
                        "SELECT id, status, client_name, client_email, session_type, slot_start, notes FROM bookings WHERE id = $1",
                        uuid.UUID(booking_id),
                    )
                except Exception:
                    pass

        if booking is None:
            # Money has been taken and there is no row to confirm. Alert, and let
            # Stripe retry rather than swallow it with a 200.
            logger.error("[BOOKING] PAID but no booking row for session %s / booking %s",
                         stripe_session_id, booking_id)
            try:
                await send_admin_booking_alert(
                    name=client_name or "unknown", email=client_email or "unknown",
                    session_type=session_type or "30", slot_start=slot_start_str,
                    notes=None, meet_link=None,
                    failure_reason=(
                        f"PAYMENT RECEIVED with no booking row (stripe_session={stripe_session_id}). "
                        "Check Stripe and book this person manually."
                    ),
                )
            except Exception as alert_exc:
                logger.error("[BOOKING] Orphan-payment alert failed: %s", alert_exc)
            raise HTTPException(status_code=500, detail="No booking row for this session.")

        # Promote the ledger BEFORE any outside work, in one atomic statement.
        #
        # `status = 'hold'` is the claim: exactly one delivery can move a row off
        # 'hold', so the loser of a concurrent redelivery stops here instead of
        # creating a second calendar event and sending a second confirmation
        # email. An earlier version claimed by writing stripe_event_id while
        # leaving the row on 'hold' — which is not exclusive at all, because the
        # second delivery's predicate matched precisely *because* the status had
        # not moved yet. Both then did the outside work.
        #
        # Promoting to 'confirmed' here (rather than after the calendar call) is
        # also what makes a crash survivable: the money is taken, so the booking
        # must not be left on 'hold' where the stale-hold sweep would expire it.
        # The trade is deliberate — a crash after this point can cost the calendar
        # event or the email, but never the booking. Repairing those is the
        # calendar_pending work, deferred until a calendar is connected.
        #
        # stripe_session_id is refreshed at the same time: checkout writes a
        # 'pending_<uuid>' placeholder first, and if its post-Stripe update failed
        # the row would keep the placeholder, which makes confirmation polling
        # 404 and cancellation skip the refund lookup. COALESCE leaves it alone if
        # this event carries no session id.
        claim = await conn.execute(
            """
            UPDATE bookings
            SET stripe_event_id = $1,
                stripe_session_id = COALESCE($2, stripe_session_id),
                status = 'confirmed',
                updated_at = NOW()
            WHERE id = $3 AND status = 'hold'
            """,
            event_id, stripe_session_id or None, booking["id"],
        )
        if claim.strip().endswith(" 0"):
            logger.info(
                "[BOOKING] Booking %s is no longer an unclaimed hold — event %s is a "
                "duplicate or late delivery, no-op", booking["id"], event_id,
            )
            return JSONResponse(content={"received": True})

        # Transition hold -> confirmed
        new_status = "confirmed"
        calendar_event_id = None
        meet_link = None

        # Try to create calendar event
        try:
            slot_dt = booking["slot_start"]
            if isinstance(slot_dt, str):
                slot_dt = _DateTime.fromisoformat(slot_dt)

            cal_result = await create_booking_event(
                session_type=booking["session_type"],
                slot_start=slot_dt,
                name=booking["client_name"],
                email=booking["client_email"],
                notes=booking.get("notes"),
            )
            calendar_event_id = cal_result.get("event_id")
            meet_link = cal_result.get("meet_link")
            logger.info("[BOOKING] Calendar event created: %s", calendar_event_id)
        except Exception as exc:
            logger.error("[BOOKING] Calendar event creation failed: %s", exc)
            new_status = "calendar_failed"

        # Record the calendar outcome on the already-promoted row. Migration 013's
        # unique index on stripe_event_id is the backstop under concurrent delivery.
        await conn.execute(
            """
            UPDATE bookings
            SET status = $1,
                calendar_event_id = $2,
                meet_link = $3,
                updated_at = NOW()
            WHERE id = $4
            """,
            new_status,
            calendar_event_id,
            meet_link,
            booking["id"],
        )

    # Link the intake brief (if the checkout carried one) to this booking.
    await _link_brief_to_booking(
        metadata.get("intake_brief_id") or None,
        str(booking["id"]),
        client_email or booking.get("client_email"),
    )

    # Send Telegram notification (fire-and-forget)
    try:
        await send_booking_notification(
            name=client_name or booking["client_name"],
            email=client_email or booking["client_email"],
            session_type=session_type or booking["session_type"],
            slot_start=slot_start_str or str(booking["slot_start"]),
            notes=booking.get("notes"),
        )
    except Exception as exc:
        logger.error("[BOOKING] Telegram notification failed (non-blocking): %s", exc)

    # Send admin email alert (fire-and-forget, non-blocking)
    try:
        await send_admin_booking_alert(
            name=client_name or booking["client_name"],
            email=client_email or booking["client_email"],
            session_type=session_type or booking["session_type"],
            slot_start=slot_start_str or str(booking["slot_start"]),
            notes=booking.get("notes"),
            meet_link=meet_link,
        )
    except Exception as exc:
        logger.error("[BOOKING] Admin email alert failed (non-blocking): %s", exc)

    # Send booking confirmation email via Gmail (fire-and-forget, non-blocking)
    try:
        await send_booking_confirmation_email(
            name=client_name or booking["client_name"],
            email=client_email or booking["client_email"],
            session_type=session_type or booking["session_type"],
            slot_start=slot_start_str or str(booking["slot_start"]),
            meet_link=meet_link,
            notes=booking.get("notes"),
            # Paid confirmations were the one path shipping no calendar file, while
            # the body said one was attached. They also need the stable UID, or a
            # later reschedule cannot move the client's event.
            kind="confirmed",
            booking_id=str(booking["id"]),
            ics_sequence=0,
        )
    except Exception as exc:
        logger.error("[BOOKING] Confirmation email failed (non-blocking): %s", exc)

    return JSONResponse(content={"received": True})


@app.get("/api/booking/confirmation/{stripe_session_id}")
async def get_booking_confirmation(stripe_session_id: str):
    """Return booking details for the confirmation page.

    Frontend polls this after Stripe redirect until status != 'hold'.
    """
    pool = await _get_booking_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Booking system not available.")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                id, stripe_session_id, session_type,
                slot_start, slot_end, client_name, client_email,
                notes, status, calendar_event_id, meet_link,
                amount_cents, created_at
            FROM bookings
            WHERE stripe_session_id = $1
            """,
            stripe_session_id,
        )

    if row is None:
        raise HTTPException(status_code=404, detail="Booking not found.")

    return JSONResponse(content={
        "id": str(row["id"]),
        "stripe_session_id": row["stripe_session_id"],
        "session_type": row["session_type"],
        "slot_start": row["slot_start"].isoformat() if row["slot_start"] else None,
        "slot_end": row["slot_end"].isoformat() if row["slot_end"] else None,
        "client_name": row["client_name"],
        "client_email": row["client_email"],
        "notes": row["notes"],
        "status": row["status"],
        "calendar_event_id": row["calendar_event_id"],
        "meet_link": row["meet_link"],
        "amount_cents": row["amount_cents"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    })


# ----------------------------------------------------------------
# Authenticated booking management endpoints
# ----------------------------------------------------------------

@app.get("/api/booking/my-bookings", response_model=MyBookingsResponse)
async def get_my_bookings(auth: ParsedToken = Depends(require_auth)):
    """Return all bookings for the authenticated user (by user_id or email)."""
    pool = await _get_booking_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Booking system not available.")

    now = _DateTime.now(timezone.utc)

    async with pool.acquire() as conn:
        # Backfill user_id on orphaned bookings matched by email
        if auth.email:
            await conn.execute(
                "UPDATE bookings SET user_id = $1, updated_at = NOW() WHERE client_email = $2 AND user_id IS NULL",
                uuid.UUID(auth.user_id), auth.email,
            )

        # Fetch bookings by user_id OR email
        params: list = [uuid.UUID(auth.user_id)]
        email_clause = ""
        if auth.email:
            email_clause = "OR client_email = $2"
            params.append(auth.email)

        rows = await conn.fetch(
            f"""
            SELECT id, session_type, slot_start, slot_end, status,
                   meet_link, amount_cents, created_at
            FROM bookings
            WHERE (user_id = $1 {email_clause})
              AND status NOT IN ('expired', 'hold')
            ORDER BY slot_start DESC
            """,
            *params,
        )

    entries = []
    for row in rows:
        slot_start = row["slot_start"]
        is_upcoming = slot_start and slot_start > now
        is_confirmed = row["status"] == "confirmed"
        entries.append(BookingEntry(
            id=str(row["id"]),
            session_type=row["session_type"],
            slot_start=slot_start.isoformat() if slot_start else None,
            slot_end=row["slot_end"].isoformat() if row["slot_end"] else None,
            status=row["status"],
            meet_link=row["meet_link"],
            amount_cents=row["amount_cents"] or 0,
            created_at=row["created_at"].isoformat() if row["created_at"] else None,
            can_cancel=is_confirmed and is_upcoming,
            can_reschedule=is_confirmed and is_upcoming and slot_start > now + timedelta(hours=2),
            refund_eligible=is_confirmed and is_upcoming and slot_start > now + timedelta(hours=24),
        ))

    return MyBookingsResponse(bookings=entries)


@app.post("/api/booking/{booking_id}/cancel", response_model=CancelBookingResponse)
async def cancel_booking(booking_id: str, req: CancelBookingRequest, auth: ParsedToken = Depends(require_auth)):
    """Cancel a confirmed booking. Full refund if >24 hours before session."""
    pool = await _get_booking_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Booking system not available.")

    now = _DateTime.now(timezone.utc)

    async with pool.acquire() as conn:
        # Fetch and verify ownership
        row = await conn.fetchrow(
            """
            SELECT id, status, slot_start, stripe_session_id, calendar_event_id,
                   client_name, client_email, session_type, amount_cents, user_id
            FROM bookings WHERE id = $1
            """,
            uuid.UUID(booking_id),
        )

        if row is None:
            raise HTTPException(status_code=404, detail="Booking not found.")

        # Verify ownership
        owns = (row["user_id"] and str(row["user_id"]) == auth.user_id) or \
               (auth.email and row["client_email"] == auth.email)
        if not owns:
            raise HTTPException(status_code=403, detail="Not your booking.")

        if row["status"] not in MANAGEABLE_STATUSES:
            raise HTTPException(status_code=400, detail=f"Cannot cancel booking with status '{row['status']}'.")

        slot_start = row["slot_start"]
        if slot_start and slot_start <= now:
            raise HTTPException(status_code=400, detail="Cannot cancel a past session.")

        # Determine refund eligibility (>24 hours before session). Nothing was paid
        # on a free call, so there is nothing to refund — without the amount check
        # we asked Stripe to retrieve a 'free_<uuid>' session on every cancellation
        # and logged the resulting error.
        refund_eligible = bool(
            slot_start and slot_start > now + timedelta(hours=24) and (row["amount_cents"] or 0) > 0
        )
        refund_id = None
        refund_amount = 0

        # Claim the cancellation BEFORE refunding. The status check above is a
        # read-then-act, so two clicks (or two tabs) could both reach the refund
        # and issue it twice. Whoever flips 'confirmed' away owns the refund;
        # everyone else is told it is already done.
        #
        # The claim lands directly on the terminal 'cancelled' rather than a
        # transient 'cancelling' marker. Both free the slot, but a crash between
        # here and the final write leaves 'cancelled' — already true, and nothing
        # to sweep — where 'cancelling' would strand the row in a state no code
        # recovers from. The write below still upgrades it to 'refunded' and adds
        # the reason and refund details.
        claim = await conn.execute(
            "UPDATE bookings SET status = 'cancelled', cancelled_at = NOW(), "
            "updated_at = NOW() WHERE id = $1 AND status = ANY($2::text[])",
            uuid.UUID(booking_id), list(MANAGEABLE_STATUSES),
        )
        if claim.strip().endswith(" 0"):
            raise HTTPException(status_code=409, detail="This booking is already cancelled.")

        # Attempt Stripe refund if eligible
        if refund_eligible and stripe and row["stripe_session_id"] and not row["stripe_session_id"].startswith("pending_"):
            try:
                checkout_session = stripe.checkout.Session.retrieve(row["stripe_session_id"])
                payment_intent_id = checkout_session.payment_intent
                if isinstance(payment_intent_id, dict):
                    payment_intent_id = payment_intent_id["id"]
                if payment_intent_id:
                    refund = stripe.Refund.create(
                        payment_intent=payment_intent_id,
                        reason="requested_by_customer",
                    )
                    refund_id = refund.id
                    refund_amount = refund.amount
            except Exception as exc:
                logger.error("[BOOKING] Stripe refund failed for %s: %s", booking_id, exc)
                # Continue with cancellation even if refund fails

        # Delete Google Calendar event. Best-effort for the same reason as
        # reschedule: the cancellation is already committed and refusing now would
        # tell the client it did not happen. A suppressed failure means a meeting
        # stays on YOUR calendar for a call that is not happening, so it is
        # alerted rather than only logged.
        calendar_drift: Optional[str] = None
        cal_event_id = row["calendar_event_id"]
        if cal_event_id:
            try:
                await delete_booking_event(cal_event_id)
            except Exception as exc:
                logger.error("[BOOKING] Calendar event deletion failed for %s: %s", booking_id, exc)
                calendar_drift = (
                    f"the event is still on your calendar (event {cal_event_id}): {exc}"
                )

        # Update booking status
        new_status = "refunded" if refund_id else "cancelled"
        await conn.execute(
            """
            UPDATE bookings
            SET status = $1, cancelled_at = NOW(), cancellation_reason = $2,
                refund_id = $3, refund_amount_cents = $4, calendar_event_id = NULL, updated_at = NOW()
            WHERE id = $5
            """,
            new_status, req.reason or None, refund_id, refund_amount, uuid.UUID(booking_id),
        )

        ics_uid, ics_seq = await _ics_identity(conn, uuid.UUID(booking_id))

    # Tell the client. Until now cancelling sent them nothing at all — only a
    # Telegram ping to the owner — so someone who cancelled on the site had no
    # confirmation it worked, and the event stayed in their calendar.
    try:
        cancel_emailed = await send_booking_confirmation_email(
            name=row["client_name"],
            email=row["client_email"],
            session_type=row["session_type"],
            slot_start=slot_start.isoformat() if slot_start else "",
            kind="cancelled",
            booking_id=ics_uid,
            ics_sequence=ics_seq + 1,   # a revision ON TOP of the current state
        )
        if not cancel_emailed:
            logger.error(
                "[BOOKING] Cancellation email FAILED for %s (%s) — booking IS "
                "cancelled; tell them by hand", booking_id, row["client_email"],
            )
    except Exception as exc:
        logger.error("[BOOKING] Cancellation email failed: %s", exc)

    if calendar_drift:
        try:
            await send_admin_booking_alert(
                name=row["client_name"], email=row["client_email"],
                session_type=row["session_type"],
                slot_start=slot_start.isoformat() if slot_start else "",
                notes=None, meet_link=None,
                failure_reason=(
                    f"CANCELLED in the database, but {calendar_drift}. The client has "
                    "been told it is cancelled; remove it from your calendar by hand."
                ),
            )
        except Exception as exc:
            logger.error("[BOOKING] Calendar-drift alert failed: %s", exc)

    # Send notification
    try:
        await send_booking_notification(
            name=row["client_name"],
            email=row["client_email"],
            session_type=row["session_type"],
            slot_start=str(slot_start),
            status=f"CANCELLED ({new_status})",
        )
    except Exception as exc:
        logger.error("[BOOKING] Cancellation notification failed: %s", exc)

    if refund_id:
        return CancelBookingResponse(
            success=True, refunded=True, refund_amount_cents=refund_amount,
            message="Booking cancelled and refund initiated.",
        )
    return CancelBookingResponse(
        success=True, refunded=False,
        message="Booking cancelled. No refund (less than 24 hours before session).",
    )


@app.post("/api/booking/{booking_id}/reschedule", response_model=RescheduleBookingResponse)
async def reschedule_booking(booking_id: str, req: RescheduleBookingRequest, auth: ParsedToken = Depends(require_auth)):
    """Reschedule a confirmed booking to a new time slot."""
    pool = await _get_booking_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Booking system not available.")

    now = _DateTime.now(timezone.utc)

    # Parse new slot
    try:
        new_slot_start = _DateTime.fromisoformat(req.new_slot_start)
        if new_slot_start.tzinfo is None:
            raise ValueError("Timezone required")
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid new_slot_start: {exc}")

    if new_slot_start <= now:
        raise HTTPException(status_code=400, detail="New slot must be in the future.")

    async with pool.acquire() as conn:
        # Fetch and verify ownership
        row = await conn.fetchrow(
            """
            SELECT id, status, slot_start, stripe_session_id, stripe_event_id,
                   calendar_event_id, client_name, client_email, session_type,
                   amount_cents, notes, user_id
            FROM bookings WHERE id = $1
            """,
            uuid.UUID(booking_id),
        )

        if row is None:
            raise HTTPException(status_code=404, detail="Booking not found.")

        owns = (row["user_id"] and str(row["user_id"]) == auth.user_id) or \
               (auth.email and row["client_email"] == auth.email)
        if not owns:
            raise HTTPException(status_code=403, detail="Not your booking.")

        if row["status"] not in MANAGEABLE_STATUSES:
            raise HTTPException(status_code=400, detail=f"Cannot reschedule booking with status '{row['status']}'.")

        slot_start = row["slot_start"]
        if slot_start and slot_start <= now + timedelta(hours=2):
            raise HTTPException(status_code=400, detail="Cannot reschedule less than 2 hours before session.")

        # The new time has to be one we actually offer — same check the booking
        # endpoints use. Without it, reschedule was a way around published hours:
        # any future instant was accepted.
        await _assert_slot_offered(new_slot_start, row["session_type"])

        # Compute new slot end
        duration_minutes = 30 if row["session_type"] == "30" else 60
        new_slot_end = new_slot_start + timedelta(minutes=duration_minutes)
        new_booking_id = uuid.uuid4()

        # Transaction: mark old as rescheduled, create new booking, handle calendar
        try:
            async with conn.transaction():
                # Mark old booking as rescheduled and hand BOTH unique Stripe columns
                # to the new row, which has to carry them (cancel/refund reads the
                # session id from there, and the webhook resolves a redelivery by
                # event id). Leaving either on both rows makes the insert below
                # violate its unique index, roll the transaction back, and report a
                # free slot as "no longer available":
                #   - stripe_session_id is UNIQUE outright, so it gets a superseded
                #     placeholder keyed on the row's own PK — rescheduling the same
                #     chain twice therefore cannot collide either;
                #   - stripe_event_id is UNIQUE where non-null (migration 013), so
                #     it is released to NULL. Only paid rows have one, which is why
                #     free reschedules never hit this.
                # The status predicate makes this a CLAIM, not just an update. The
                # check above is a read-then-act, so two tabs could both supersede
                # the same booking and each insert its own live row — one client,
                # two bookings, two of your hours gone.
                superseded = await conn.execute(
                    """
                    UPDATE bookings
                    SET status = 'rescheduled',
                        stripe_session_id = 'superseded_' || id::text,
                        stripe_event_id = NULL,
                        updated_at = NOW()
                    WHERE id = $1 AND status = ANY($2::text[])
                    """,
                    uuid.UUID(booking_id), list(MANAGEABLE_STATUSES),
                )
                if superseded.strip().endswith(" 0"):
                    raise HTTPException(
                        status_code=409,
                        detail="That booking was already changed. Reload and try again.",
                    )

                # Create new booking row
                await conn.execute(
                    """
                    INSERT INTO bookings (
                        id, stripe_session_id, stripe_event_id, session_type,
                        slot_start, slot_end, client_name, client_email,
                        notes, status, amount_cents, user_id, rescheduled_from
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'confirmed', $10, $11, $12)
                    """,
                    new_booking_id,
                    row["stripe_session_id"],
                    row["stripe_event_id"],
                    row["session_type"],
                    new_slot_start,
                    new_slot_end,
                    row["client_name"],
                    row["client_email"],
                    row["notes"],
                    row["amount_cents"],
                    row["user_id"],
                    uuid.UUID(booking_id),
                )
        except HTTPException:
            # Our own claim refusal above, already worded for the client. Without
            # this it fell into the generic handler and blamed the new slot.
            raise
        except Exception as db_exc:
            logger.error("[BOOKING] Reschedule DB error: %s", db_exc)
            raise HTTPException(status_code=409, detail="New time slot is no longer available.")

        # Delete old calendar event
        # Calendar mutations are best-effort: the booking has already moved in the
        # ledger, which is the record of truth, and failing the request now would
        # tell the client their reschedule did not happen when it did. But a
        # suppressed failure leaves YOUR calendar wrong — a ghost at the old time,
        # or nothing at the new one — so each failure is collected and alerted
        # below rather than only logged.
        calendar_drift: list[str] = []

        cal_event_id = row["calendar_event_id"]
        if cal_event_id:
            try:
                await delete_booking_event(cal_event_id)
            except Exception as exc:
                logger.error("[BOOKING] Old calendar event deletion failed: %s", exc)
                calendar_drift.append(
                    f"the old {slot_start.astimezone(_BOOKING_TZ).isoformat() if slot_start else '?'} "
                    f"event is still on your calendar "
                    f"(event {cal_event_id}): {exc}"
                )

        # Create new calendar event
        new_meet_link = None
        new_cal_event_id = None
        try:
            cal_result = await create_booking_event(
                session_type=row["session_type"],
                slot_start=new_slot_start,
                name=row["client_name"],
                email=row["client_email"],
                notes=row["notes"],
            )
            new_cal_event_id = cal_result.get("event_id")
            new_meet_link = cal_result.get("meet_link")
        except Exception as exc:
            logger.error("[BOOKING] New calendar event creation failed: %s", exc)
            calendar_drift.append(
                f"no event was created for the new "
                f"{new_slot_start.astimezone(_BOOKING_TZ).isoformat()} time: {exc}"
            )

        # Update new booking with calendar info
        await conn.execute(
            """
            UPDATE bookings SET calendar_event_id = $1, meet_link = $2, updated_at = NOW()
            WHERE id = $3
            """,
            new_cal_event_id, new_meet_link, new_booking_id,
        )

        ics_uid, ics_seq = await _ics_identity(conn, new_booking_id)

    # Tell the client — this sent nothing before, so a rescheduled call left them
    # with the OLD time in their inbox and calendar. Same UID as the original with
    # a higher SEQUENCE, so their calendar moves the event instead of duplicating it.
    try:
        move_emailed = await send_booking_confirmation_email(
            name=row["client_name"],
            email=row["client_email"],
            session_type=row["session_type"],
            slot_start=new_slot_start.isoformat(),
            meet_link=new_meet_link,
            notes=row["notes"],
            kind="rescheduled",
            booking_id=ics_uid,
            ics_sequence=ics_seq,
        )
        if not move_emailed:
            logger.error(
                "[BOOKING] Reschedule email FAILED for %s (%s) — the booking DID "
                "move; tell them by hand", new_booking_id, row["client_email"],
            )
    except Exception as exc:
        logger.error("[BOOKING] Reschedule email failed: %s", exc)

    # Your calendar disagrees with the ledger. The client has already been told
    # the right thing (their .ics moved the event), so this is yours to fix.
    if calendar_drift:
        try:
            await send_admin_booking_alert(
                name=row["client_name"], email=row["client_email"],
                session_type=row["session_type"],
                slot_start=new_slot_start.isoformat(),
                notes=row["notes"], meet_link=new_meet_link,
                failure_reason=(
                    "RESCHEDULED in the database, but your Google Calendar is now out "
                    "of step — " + "; ".join(calendar_drift)
                    + ". The client's invitation is correct; fix your calendar by hand."
                ),
            )
        except Exception as exc:
            logger.error("[BOOKING] Calendar-drift alert failed: %s", exc)

    # Notification
    try:
        await send_booking_notification(
            name=row["client_name"],
            email=row["client_email"],
            session_type=row["session_type"],
            slot_start=req.new_slot_start,
            status="RESCHEDULED",
        )
    except Exception as exc:
        logger.error("[BOOKING] Reschedule notification failed: %s", exc)

    return RescheduleBookingResponse(
        success=True,
        message="Booking rescheduled successfully.",
        new_booking=BookingEntry(
            id=str(new_booking_id),
            session_type=row["session_type"],
            slot_start=new_slot_start.isoformat(),
            slot_end=new_slot_end.isoformat(),
            status="confirmed",
            meet_link=new_meet_link,
            amount_cents=row["amount_cents"] or 0,
            can_cancel=True,
            can_reschedule=True,
            refund_eligible=new_slot_start > now + timedelta(hours=24),
        ),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
