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
import uuid
import time
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

from calendar_service import get_available_slots, create_booking_event, delete_booking_event
from telegram_service import send_booking_notification
from email_service import send_booking_confirmation_email, send_admin_booking_alert
from intake_agent import (
    run_turn as intake_run_turn,
    new_state as intake_new_state,
    sign_session as intake_sign_session,
    verify_session as intake_verify_session,
    clamp_brief as intake_clamp_brief,
    intake_available,
    MAX_USER_TURNS,
)
from rate_limiter import parse_user_id, ParsedToken

# Booking DB pool (shares SUPABASE_DB_URL with token_store)
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
            import ssl as _ssl
            ssl_ctx = _ssl.create_default_context()
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
    # that medium-thinking gpt-5-mini narratives (compatibility / occasion
    # mode in particular) don't get cut off at the SDK's 600s HTTP read
    # default. The SSE path streams progress so the user UX is unaffected,
    # but the underlying HTTP read budget needs headroom for the 5-10 min
    # reasoning tail observed on heavy two-chart compatibility runs.
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

# Request model for streaming TTS
class TTSStreamRequest(BaseModel):
    text: str
    session_id: Optional[str] = None


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
    path: Literal["business", "individual"]
    session: Optional[str] = Field(None, max_length=16000)  # signed session token
    message: str = Field("", max_length=2000)


class IntakeBriefRequest(BaseModel):
    # Persisting a brief requires a valid signed intake session (proves a real
    # interview happened). The brief is the client-reviewed/edited version; it is
    # re-validated + clamped server-side before the write.
    session: str = Field(..., max_length=16000)
    brief: dict = Field(default_factory=dict)
    name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=200)
    recommended_next_step: Optional[str] = Field(None, max_length=8)
    booking_id: Optional[str] = Field(None, max_length=64)


class FreeConsultRequest(BaseModel):
    """Free enterprise fit-call booking (no payment). Mirrors the paid
    checkout request but skips Stripe — the slot is confirmed directly."""
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

# -------------------- Streaming TTS Endpoints --------------------

@app.post("/api/tts/stream/start")
async def start_tts_stream(request: TTSStreamRequest):
    """Start streaming TTS generation"""
    try:
        session_id = request.session_id or str(uuid.uuid4())
        
        return JSONResponse(
            content={"session_id": session_id, "message": "TTS stream ready"}, 
            headers={"Access-Control-Allow-Origin": "*"}
        )
        
    except Exception as e:
        logger.error("TTS stream start failed", exc_info=True)
        error_detail = {"error": str(e)}
        if os.getenv("ENVIRONMENT") != "production":
            import traceback
            error_detail["detail"] = traceback.format_exc()
        return JSONResponse(content=error_detail, status_code=500)

@app.get("/api/tts/stream/{session_id}")
async def stream_tts_audio(session_id: str, text: str):
    """Stream TTS audio with progress tracking"""
    
    async def generate_audio_stream():
        try:
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': '?? Generating speech...', 'session_id': session_id})}\n\n"
            await asyncio.sleep(0)
            
            total_chunks = 0
            
            # Stream audio from TTS service
            async for chunk in tts_streaming_service.generate_audio_stream(session_id, text):
                if chunk:
                    try:
                        # Convert bytes to base64 for JSON transmission
                        import base64
                        chunk_b64 = base64.b64encode(chunk).decode('utf-8')
                        
                        # Send audio chunk
                        yield f"data: {json.dumps({'type': 'audio_chunk', 'data': chunk_b64, 'chunk_id': total_chunks, 'session_id': session_id})}\n\n"
                        await asyncio.sleep(0)
                        
                        total_chunks += 1
                        
                        # Send progress update every 10 chunks
                        if total_chunks % 10 == 0:
                            yield f"data: {json.dumps({'type': 'progress', 'chunks_sent': total_chunks, 'session_id': session_id})}\n\n"
                            await asyncio.sleep(0)
                        
                    except Exception as chunk_error:
                        yield f"data: {json.dumps({'type': 'error', 'message': f'Audio chunk error: {str(chunk_error)}', 'session_id': session_id})}\n\n"
                        await asyncio.sleep(0)
                        break
            
            # Get final audio info
            audio_info = tts_streaming_service.get_audio_info(session_id)
            
            # Send completion signal with audio metadata
            yield f"data: {json.dumps({'type': 'complete', 'total_chunks': total_chunks, 'session_id': session_id, 'audio_info': audio_info})}\n\n"
            await asyncio.sleep(0)
            
        except GeneratorExit:
            return
        except Exception as e:
            try:
                error_msg = f"Error during TTS streaming: {str(e)}"
                yield f"data: {json.dumps({'type': 'error', 'message': error_msg, 'session_id': session_id})}\n\n"
                await asyncio.sleep(0)
            except:
                return
    
    return StreamingResponse(
        with_heartbeat(generate_audio_stream()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )

@app.get("/api/tts/audio/{session_id}")
async def get_complete_audio(session_id: str):
    """Get complete audio file for a session"""
    try:
        audio_data = tts_streaming_service.get_complete_audio(session_id)
        
        if not audio_data:
            return JSONResponse(
                content={"error": "Audio session not found or not ready"}, 
                status_code=404, 
                headers={"Access-Control-Allow-Origin": "*"}
            )
        
        return Response(
            content=audio_data, 
            media_type="audio/mpeg", 
            headers={
                "Access-Control-Allow-Origin": "*",
                "Content-Length": str(len(audio_data))
            }
        )
        
    except Exception as e:
        return JSONResponse(
            content={"error": str(e)}, 
            status_code=500, 
            headers={"Access-Control-Allow-Origin": "*"}
        )

@app.get("/api/tts/info/{session_id}")
async def get_audio_info(session_id: str):
    """Get audio session information"""
    try:
        audio_info = tts_streaming_service.get_audio_info(session_id)
        
        if not audio_info:
            return JSONResponse(
                content={"error": "Audio session not found"}, 
                status_code=404, 
                headers={"Access-Control-Allow-Origin": "*"}
            )
        
        return JSONResponse(
            content=audio_info, 
            headers={"Access-Control-Allow-Origin": "*"}
        )
        
    except Exception as e:
        return JSONResponse(
            content={"error": str(e)}, 
            status_code=500, 
            headers={"Access-Control-Allow-Origin": "*"}
        )

@app.delete("/api/tts/{session_id}")
async def cleanup_tts_session(session_id: str):
    """Clean up TTS session"""
    try:
        tts_streaming_service.cleanup_session(session_id)
        return JSONResponse(
            content={"message": "TTS session cleaned up"}, 
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        return JSONResponse(
            content={"error": str(e)}, 
            status_code=500, 
            headers={"Access-Control-Allow-Origin": "*"}
        )

# -------------------- Gemini API Endpoints --------------------

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
# NOTE: Rate limiting needed on /api/booking/slots (30 req/min) and
# /api/booking/checkout (5 req/min). Add when rate_limiter supports
# endpoint-specific limits without auth.

# SQL for bookings table (run once in Supabase SQL editor):
# ----------------------------------------------------------------
# CREATE TABLE bookings (
#     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
#     stripe_session_id TEXT UNIQUE NOT NULL,
#     stripe_event_id TEXT,
#     session_type TEXT NOT NULL CHECK (session_type IN ('30', '60')),
#     slot_start TIMESTAMPTZ NOT NULL,
#     slot_end TIMESTAMPTZ NOT NULL,
#     client_name TEXT NOT NULL,
#     client_email TEXT NOT NULL,
#     notes TEXT,
#     status TEXT NOT NULL DEFAULT 'hold' CHECK (status IN (
#         'hold', 'confirmed', 'calendar_failed', 'expired', 'cancelled', 'refunded'
#     )),
#     calendar_event_id TEXT,
#     meet_link TEXT,
#     amount_cents INTEGER NOT NULL,
#     created_at TIMESTAMPTZ DEFAULT NOW(),
#     updated_at TIMESTAMPTZ DEFAULT NOW(),
#     UNIQUE(slot_start) WHERE (status IN ('hold', 'confirmed'))
# );
# CREATE INDEX idx_bookings_slot ON bookings (slot_start, status);
# CREATE INDEX idx_bookings_stripe ON bookings (stripe_session_id);
# ----------------------------------------------------------------


@app.get("/api/booking/slots")
async def get_booking_slots(date: str, session_type: str = "30"):
    """Return available booking slots for a given date.

    Queries Google Calendar freebusy API and checks Supabase bookings table
    for existing holds/confirmed bookings. Returns available 30-min slot
    boundaries.

    Query param `date`: YYYY-MM-DD format.
    Query param `session_type`: '30' or '60' (default '30').
    """
    from datetime import date as date_type
    from calendar_service import BOOKING_TIMEZONE

    if session_type not in ("30", "60"):
        raise HTTPException(status_code=400, detail="session_type must be '30' or '60'.")

    # Parse date
    try:
        target_date = date_type.fromisoformat(date)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    # Don't allow booking too far in the future (90 days) or in the past
    today = date_type.today()
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
    if pool is not None:
        try:
            # Expire stale holds first (lazy cleanup)
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE bookings
                    SET status = 'expired', updated_at = NOW()
                    WHERE status = 'hold'
                      AND created_at < NOW() - INTERVAL '30 minutes'
                    """
                )

                # Get all held/confirmed slot_starts for this date
                from zoneinfo import ZoneInfo
                tz = ZoneInfo(BOOKING_TIMEZONE)
                day_start = _DateTime(
                    target_date.year, target_date.month, target_date.day,
                    0, 0, 0, tzinfo=tz,
                )
                day_end = _DateTime(
                    target_date.year, target_date.month, target_date.day,
                    23, 59, 59, tzinfo=tz,
                )
                rows = await conn.fetch(
                    """
                    SELECT slot_start, slot_end
                    FROM bookings
                    WHERE status IN ('hold', 'confirmed')
                      AND slot_start >= $1
                      AND slot_start <= $2
                    """,
                    day_start, day_end,
                )

                booked_starts = set()
                for row in rows:
                    booked_starts.add(row["slot_start"].isoformat())

                # Remove slots whose start time matches a booked slot
                slots = [
                    s for s in slots
                    if s["start"] not in booked_starts
                ]
        except Exception as exc:
            logger.error("[BOOKING] DB slot check failed (returning calendar-only slots): %s", exc)

    return BookingSlotsResponse(
        slots=[BookingSlot(**s) for s in slots],
        timezone=BOOKING_TIMEZONE,
    )


@app.post("/api/booking/checkout")
async def create_booking_checkout(req: BookingCheckoutRequest):
    """Create a Stripe Checkout Session for a consulting booking.

    Server-side pricing: maps session_type to Stripe Price ID.
    Revalidates slot availability before creating hold.
    Inserts hold row into Supabase bookings table.
    Returns Stripe Checkout redirect URL.
    """
    if stripe is None or not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe payments not configured.")

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
                await conn.execute(
                    """
                    UPDATE bookings
                    SET status = 'expired', updated_at = NOW()
                    WHERE status = 'hold'
                      AND created_at < NOW() - INTERVAL '30 minutes'
                    """
                )

                # Attempt insert — the partial unique index on (slot_start)
                # WHERE status IN ('hold', 'confirmed') prevents double-booking
                try:
                    await conn.execute(
                        """
                        INSERT INTO bookings (
                            id, stripe_session_id, session_type,
                            slot_start, slot_end, client_name, client_email,
                            notes, status, amount_cents
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'hold', $9)
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
                    )
                except Exception as db_exc:
                    # Likely unique constraint violation — slot already taken
                    logger.warning("[BOOKING] Slot conflict: %s", db_exc)
                    raise HTTPException(
                        status_code=409,
                        detail="This time slot is no longer available. Please choose another.",
                    )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("[BOOKING] DB insert failed: %s", exc)
            raise HTTPException(status_code=500, detail="Booking system error. Please try again.")
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


async def _assert_slot_offered(slot_start: "_DateTime") -> None:
    """Revalidate `slot_start` against the SAME availability source as
    GET /api/booking/slots (office hours, 30-min boundaries, 90-day horizon,
    Google Calendar freebusy). Raises HTTPException if the instant is not a
    currently-offered 30-min slot start."""
    from datetime import date as _date_type
    from calendar_service import BOOKING_TIMEZONE
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(BOOKING_TIMEZONE)
    local_date = slot_start.astimezone(tz).date()

    today = _date_type.today()
    if local_date < today:
        raise HTTPException(status_code=400, detail="Cannot book a slot in the past.")
    if (local_date - today).days > 90:
        raise HTTPException(status_code=400, detail="Cannot book more than 90 days in advance.")

    try:
        offered = await get_available_slots(local_date, "30")
    except Exception as exc:
        logger.error("[BOOKING] Free-consult availability lookup failed: %s", exc)
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
    """Book a FREE enterprise fit call (no payment).

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
                await conn.execute(
                    """
                    UPDATE bookings
                    SET status = 'expired', updated_at = NOW()
                    WHERE status = 'hold'
                      AND created_at < NOW() - INTERVAL '30 minutes'
                    """
                )

                # Atomic overlap-safe insert: the overlap check and the insert
                # are ONE statement, so there is no app-level read-then-write gap
                # (session_type is stored schema-valid '30'; free/fit is encoded
                # by amount_cents = 0 and the 'free_' session id). The partial
                # UNIQUE(slot_start) index additionally guards identical-start
                # races. 0 rows inserted => an overlapping hold/confirmed exists.
                # DEBT: true cross-path overlap safety (a 60-min paid booking
                # straddling this 30-min slot under concurrent uncommitted writes)
                # needs a tstzrange GIST exclusion constraint on the bookings
                # table — not present in the current schema. The paid checkout
                # path shares this gap. Upgrade when 30/60-min bookings are taken
                # concurrently at volume or the first real double-book is observed.
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
                            WHERE status IN ('hold', 'confirmed')
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
                    )
                except Exception as db_exc:
                    # Identical-start collision caught by the partial unique index.
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
    else:
        logger.warning("[BOOKING] No database — proceeding without hold (dev mode)")

    # Create the calendar event. Only a successful event confirms the booking;
    # a failure frees the slot and returns an error (B3 — never a false success).
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
        raise HTTPException(
            status_code=502,
            detail="We couldn't confirm that time on the calendar. Please pick another slot — you have not been booked.",
        )

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE bookings
                    SET status = 'confirmed', calendar_event_id = $1, meet_link = $2, updated_at = NOW()
                    WHERE id = $3
                    """,
                    calendar_event_id,
                    meet_link,
                    uuid.UUID(booking_id),
                )
        except Exception as exc:
            logger.error("[BOOKING] Free-consult status update failed: %s", exc)

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

    try:
        await send_admin_booking_alert(
            name=req.name, email=req.email,
            session_type="fit", slot_start=req.slot_start,
            notes=req.notes, meet_link=meet_link,
        )
    except Exception as exc:
        logger.error("[BOOKING] Admin email alert failed (non-blocking): %s", exc)

    try:
        await send_booking_confirmation_email(
            name=req.name, email=req.email,
            session_type="30", slot_start=req.slot_start, meet_link=meet_link,
            notes=req.notes,
        )
    except Exception as exc:
        logger.error("[BOOKING] Confirmation email failed (non-blocking): %s", exc)

    return JSONResponse(content={
        "id": booking_id,
        "status": "confirmed",
        "meet_link": meet_link,
        "slot_start": req.slot_start,
    })


# ---------------------------------------------------------------------------
# AI Brief Agent (Phase 2) — /consult intake chat
# ---------------------------------------------------------------------------

def _check_intake_rate(request: Request) -> None:
    # ~12-turn interview + a couple of retries; keyed per trusted visitor IP.
    _check_rate(request, "intake", 900, 40,
                "Too many messages. Please slow down and try again shortly.")


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
            # Tampered/expired token — restart cleanly (client falls back or reseeds).
            raise HTTPException(status_code=400, detail="intake_session_invalid")
        # Path is fixed by the session, not the per-request field.
        if state.get("path") not in ("business", "individual"):
            raise HTTPException(status_code=400, detail="intake_session_invalid")
    else:
        state = intake_new_state(req.path)

    # Server-enforced turn cap — cannot be bypassed by the client.
    if int(state.get("turns", 0)) >= MAX_USER_TURNS:
        brief = state.get("brief", {})
        return JSONResponse(content={
            "reply": "I've got enough to prepare your brief. Review it on the right, correct anything I misread, then choose how to book below.",
            "brief": brief,
            "quick_replies": [],
            "complete": True,
            "recommended_next_step": "fit" if state.get("path") == "business" else "30",
            "session": intake_sign_session({**state, "complete": True}),
            "capped": True,
        })

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: intake_run_turn(state, req.message))
        new_state = result.pop("state")
        result["session"] = intake_sign_session(new_state)
        return JSONResponse(content=result)
    except Exception as exc:
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

    # Gate on a valid session token — no valid interview, no write.
    state = intake_verify_session(req.session)
    if state is None:
        raise HTTPException(status_code=400, detail="intake_session_invalid")
    path = state.get("path") if state.get("path") in ("business", "individual") else "unknown"

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
        logger.error("[BOOKING] No database — cannot process webhook")
        return JSONResponse(content={"received": True})

    async with pool.acquire() as conn:
        # Idempotency check: if this event was already processed, return 200
        existing = await conn.fetchrow(
            "SELECT id, status FROM bookings WHERE stripe_event_id = $1",
            event_id,
        )
        if existing is not None:
            logger.info("[BOOKING] Duplicate webhook event %s — already processed", event_id)
            return JSONResponse(content={"received": True})

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
            logger.error("[BOOKING] No booking found for session %s / booking %s", stripe_session_id, booking_id)
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

        # Update booking status
        await conn.execute(
            """
            UPDATE bookings
            SET status = $1,
                stripe_event_id = $2,
                calendar_event_id = $3,
                meet_link = $4,
                updated_at = NOW()
            WHERE id = $5
            """,
            new_status,
            event_id,
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

        if row["status"] != "confirmed":
            raise HTTPException(status_code=400, detail=f"Cannot cancel booking with status '{row['status']}'.")

        slot_start = row["slot_start"]
        if slot_start and slot_start <= now:
            raise HTTPException(status_code=400, detail="Cannot cancel a past session.")

        # Determine refund eligibility (>24 hours before session)
        refund_eligible = slot_start and slot_start > now + timedelta(hours=24)
        refund_id = None
        refund_amount = 0

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

        # Delete Google Calendar event
        cal_event_id = row["calendar_event_id"]
        if cal_event_id:
            try:
                await delete_booking_event(cal_event_id)
            except Exception as exc:
                logger.error("[BOOKING] Calendar event deletion failed for %s: %s", booking_id, exc)

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

    # Send notification
    try:
        await send_booking_notification(
            name=row["client_name"],
            email=row["client_email"],
            session_type=row["session_type"],
            slot_start=str(slot_start),
            status=f"CANCELLED ({new_status})",
        )
    except Exception:
        pass

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

        if row["status"] != "confirmed":
            raise HTTPException(status_code=400, detail=f"Cannot reschedule booking with status '{row['status']}'.")

        slot_start = row["slot_start"]
        if slot_start and slot_start <= now + timedelta(hours=2):
            raise HTTPException(status_code=400, detail="Cannot reschedule less than 2 hours before session.")

        # Compute new slot end
        duration_minutes = 30 if row["session_type"] == "30" else 60
        new_slot_end = new_slot_start + timedelta(minutes=duration_minutes)
        new_booking_id = uuid.uuid4()

        # Transaction: mark old as rescheduled, create new booking, handle calendar
        try:
            async with conn.transaction():
                # Mark old booking as rescheduled
                await conn.execute(
                    "UPDATE bookings SET status = 'rescheduled', updated_at = NOW() WHERE id = $1",
                    uuid.UUID(booking_id),
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
        except Exception as db_exc:
            logger.error("[BOOKING] Reschedule DB error: %s", db_exc)
            raise HTTPException(status_code=409, detail="New time slot is no longer available.")

        # Delete old calendar event
        cal_event_id = row["calendar_event_id"]
        if cal_event_id:
            try:
                await delete_booking_event(cal_event_id)
            except Exception as exc:
                logger.error("[BOOKING] Old calendar event deletion failed: %s", exc)

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

        # Update new booking with calendar info
        await conn.execute(
            """
            UPDATE bookings SET calendar_event_id = $1, meet_link = $2, updated_at = NOW()
            WHERE id = $3
            """,
            new_cal_event_id, new_meet_link, new_booking_id,
        )

    # Notification
    try:
        await send_booking_notification(
            name=row["client_name"],
            email=row["client_email"],
            session_type=row["session_type"],
            slot_start=req.new_slot_start,
            status="RESCHEDULED",
        )
    except Exception:
        pass

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

