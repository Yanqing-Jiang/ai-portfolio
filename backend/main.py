import asyncio
import logging
from typing import Any, Dict, List, Tuple, Optional
from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response, JSONResponse, FileResponse
from pydantic import BaseModel
from pathlib import Path
import os
from dotenv import load_dotenv
import json
from datetime import date as _Date, datetime as _DateTime, timezone
from decimal import Decimal
import uuid
import time
try:
    import stripe  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    stripe = None  # type: ignore
import httpx

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
AI_FACTS_PATH = BASE_DIR / "public" / "ai-projects.json"
AI_CRAWLER_PATTERNS = (
    "gptbot",
    "chatgpt-user",
    "google-extended",
    "claudebot",
    "perplexitybot",
    "amazonbot",
    "bytespider",
    "dataforseobot",
)
AI_CRAWLER_ALLOWLIST = {"gptbot", "chatgpt-user", "google-extended", "claudebot", "perplexitybot", "amazonbot"}

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

from research_agent import run_research_agent, run_research_agent_stream
from resume_agent import run_resume_agent, run_resume_agent_stream
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
    analytics_agent_rate_limit,
    analytics_sql_rate_limit,
)
try:
    from token_store import token_store
except ImportError:  # pragma: no cover - support module execution
    from .token_store import token_store  # type: ignore
from analytics_agent import create_analytics_workflow
from analytics.flows.workflow import analytics_memory_workflow
from analytics.flows.chart_revision import infer_chart_patch_from_query, is_analysis_revision_query
from analytics.core.clarify import put_answer
from analytics.core.types import ClarifyAnswerModel
from analytics.core.session_state import get_session_state_repository

from langchain.callbacks.base import BaseCallbackHandler




log_level_name = os.getenv("ANALYTICS_LOG_LEVEL", "INFO").upper()
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


def _serialize_debug(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (_DateTime, _Date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _serialize_debug(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize_debug(item) for item in value]
    if hasattr(value, "model_dump"):
        return _serialize_debug(value.model_dump())
    if hasattr(value, "__dict__"):
        return _serialize_debug(vars(value))
    return str(value)


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

# Use the global session store from analytics.core.clarify

# Initialize rate limiter on startup
@app.on_event("startup")
async def startup_event():
    await init_rate_limiter()
    await token_store.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    await token_store.shutdown()

# Allow CORS for local frontend dev
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "*"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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

class ResearchRequest(BaseModel):
    query: str
    chat_history: List[Tuple[str, str]] = []

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

# In-memory chat sessions storage
chat_sessions = {}


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


@app.get("/api/debug/session/{session_id}")
async def debug_session_state(session_id: str):
    repo = get_session_state_repository()
    try:
        snapshot = await repo.load(session_id)
    except Exception as exc:
        logger.warning("[DEBUG_SESSION] load failed session=%s error=%s", session_id, exc)
        raise HTTPException(status_code=500, detail="Failed to load session snapshot")
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Session not found")
    tool_cache = snapshot.tool_cache if isinstance(snapshot.tool_cache, dict) else {}
    analytics_cache = tool_cache.get("analytics") if isinstance(tool_cache, dict) else {}
    receipts_cache = tool_cache.get("tool_receipts") if isinstance(tool_cache, dict) else {}
    logger.info(
        "[DEBUG_SESSION] cache_keys session=%s tool_cache=%s analytics=%s receipts=%s",
        snapshot.session_id,
        sorted(tool_cache.keys()) if tool_cache else None,
        sorted(analytics_cache.keys()) if isinstance(analytics_cache, dict) else None,
        sorted(receipts_cache.keys()) if isinstance(receipts_cache, dict) else None,
    )
    payload: Dict[str, Any] = {
        "session_id": snapshot.session_id,
        "created_at": snapshot.created_at.isoformat(),
        "updated_at": snapshot.updated_at.isoformat(),
        "last_query": snapshot.last_query,
        "last_intent_key": snapshot.last_intent_key,
        "last_sql": snapshot.last_sql,
        "last_chart_spec": snapshot.last_chart_spec,
        "last_analysis": snapshot.last_analysis,
        "last_revision_directive": snapshot.last_revision_directive,
        "lane_timestamps": {lane: ts.isoformat() for lane, ts in snapshot.lane_timestamps.items()},
        "tool_cache": _serialize_debug(tool_cache),
        "routing": _serialize_debug(snapshot.routing),
        "messages": _serialize_debug(snapshot.messages),
    }
    return JSONResponse(_serialize_debug(payload))

class StreamingCallbackHandler(BaseCallbackHandler):
    def __init__(self):
        self.steps = []

    def on_tool_start(self, tool, input_str, **kwargs):
        step = f"?? Running {tool.name}..."
        self.steps.append(step)
        return step

    def on_tool_end(self, output, **kwargs):
        step = "? Tool completed"
        self.steps.append(step)
        return step

    def on_text(self, text, **kwargs):
        self.steps.append(text)
        return text

    def on_llm_start(self, serialized, prompts, **kwargs):
        step = "?? Thinking..."
        self.steps.append(step)
        return step

class StepCollectorCallbackHandler(BaseCallbackHandler):
    def __init__(self):
        self.steps = []

    def on_tool_start(self, tool, input_str, **kwargs):
        self.steps.append(f"Running tool: {tool.name} with input: {input_str}")

    def on_tool_end(self, output, **kwargs):
        self.steps.append(f"Tool output: {output}")

    def on_text(self, text, **kwargs):
        self.steps.append(f"Agent: {text}")

@app.post("/api/research")
def research_endpoint(request: ResearchRequest):
    result = run_research_agent(request.query)
    return result  # returns both 'answer' and 'steps'

@app.get("/api/research/stream")
async def research_stream_endpoint(query: str, request: Request):
    async def generate_stream():
        try:
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': '?? Starting research agent...', 'replace': False})}\n\n"
            await asyncio.sleep(0)  # Flush event loop
            
            # Run the research agent with streaming
            chunk_count = 0
            in_final_response = False
            final_response_message_sent = False
            for chunk in run_research_agent_stream(query):
                if chunk:
                    try:
                        # Handle special status replacement messages
                        if chunk.startswith("STATUS_REPLACE:"):
                            status_message = chunk[15:]  # Remove "STATUS_REPLACE:" prefix
                            yield f"data: {json.dumps({'type': 'status', 'message': status_message, 'replace': True})}\n\n"
                            await asyncio.sleep(0)  # Flush event loop
                            continue
                        
                        # Handle status update messages (append to status)
                        if chunk.startswith("STATUS_UPDATE:"):
                            status_message = chunk[14:]  # Remove "STATUS_UPDATE:" prefix
                            yield f"data: {json.dumps({'type': 'status', 'message': status_message, 'replace': False})}\n\n"
                            await asyncio.sleep(0)  # Flush event loop
                            continue
                        
                        # Handle final response marker
                        if chunk == "FINAL_RESPONSE_START":
                            in_final_response = True
                            # Only send the message once
                            if not final_response_message_sent:
                                yield f"data: {json.dumps({'type': 'status', 'message': '? Research complete, generating final response...', 'replace': True})}\n\n"
                                await asyncio.sleep(0)  # Flush event loop
                                final_response_message_sent = True
                            continue
                        
                        # (Optional) Previously truncated long chunks; keep full chunk to avoid losing data
                        
                        # Determine chunk type based on content and mode
                        chunk_type = 'response' if in_final_response else 'chunk'
                        yield f"data: {json.dumps({'type': chunk_type, 'text': chunk})}\n\n"
                        await asyncio.sleep(0)  # Flush event loop immediately after each chunk
                        chunk_count += 1
                        
                        # Removed heartbeat logic
                        
                        # Prevent too many chunks
                        if chunk_count > 5000:
                            yield f"data: {json.dumps({'type': 'status', 'message': '?? Response truncated due to length', 'replace': True})}\n\n"
                            await asyncio.sleep(0)
                            break
                            
                    except Exception as chunk_error:
                        # Handle individual chunk errors
                        yield f"data: {json.dumps({'type': 'error', 'message': f'Chunk error: {str(chunk_error)}'})}\n\n"
                        await asyncio.sleep(0)
                        break
            
            # Send completion signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            await asyncio.sleep(0)  # Final flush
            
        except GeneratorExit:
            # Client disconnected
            return
        except Exception as e:
            try:
                error_msg = f"Error during research: {str(e)}"
                yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                await asyncio.sleep(0)
            except:
                # If we can't even send the error, just return
                return
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )

@app.get("/api/resume-search/stream")
async def resume_search_stream_endpoint(query: str, request: Request, chat_history: str = "[]"):
    # Parse chat_history from JSON string
    try:
        parsed_history = json.loads(chat_history) if chat_history else []
    except json.JSONDecodeError:
        parsed_history = []
    
    async def generate_stream():
        try:
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': '?? Starting resume search...', 'replace': False})}\n\n"
            await asyncio.sleep(0)  # Flush event loop
            
            # Run the resume agent with streaming
            chunk_count = 0
            in_final_response = False
            # Removed heartbeat tracking
            
            for chunk in run_resume_agent_stream(query, parsed_history):
                if chunk:
                    try:
                        # Handle special status replacement messages
                        if chunk.startswith("STATUS_REPLACE:"):
                            status_message = chunk[15:]  # Remove "STATUS_REPLACE:" prefix
                            yield f"data: {json.dumps({'type': 'status', 'message': status_message, 'replace': True})}\n\n"
                            await asyncio.sleep(0)  # Flush event loop
                            continue
                        
                        # Handle status update messages (append to status)
                        if chunk.startswith("STATUS_UPDATE:"):
                            status_message = chunk[14:]  # Remove "STATUS_UPDATE:" prefix
                            yield f"data: {json.dumps({'type': 'status', 'message': status_message, 'replace': False})}\n\n"
                            await asyncio.sleep(0)  # Flush event loop
                            continue
                        
                        # Handle final response marker
                        if chunk == "FINAL_RESPONSE_START":
                            in_final_response = True
                            yield f"data: {json.dumps({'type': 'status', 'message': '? Resume search complete, generating final response...', 'replace': True})}\n\n"
                            await asyncio.sleep(0)  # Flush event loop
                            continue
                        
                        # Limit chunk size to prevent socket issues
                        if len(chunk) > 1000:
                            chunk = chunk[:1000] + "..."
                        
                        # Determine chunk type based on content and mode
                        chunk_type = 'response' if in_final_response else 'chunk'
                        yield f"data: {json.dumps({'type': chunk_type, 'text': chunk})}\n\n"
                        await asyncio.sleep(0)  # Flush event loop immediately after each chunk
                        chunk_count += 1
                        
                        # Removed heartbeat logic
                        
                        # Prevent too many chunks
                        if chunk_count > 1000:
                            yield f"data: {json.dumps({'type': 'status', 'message': '?? Response truncated due to length', 'replace': True})}\n\n"
                            await asyncio.sleep(0)
                            break
                            
                    except Exception as chunk_error:
                        # Handle individual chunk errors
                        yield f"data: {json.dumps({'type': 'error', 'message': f'Chunk error: {str(chunk_error)}'})}\n\n"
                        await asyncio.sleep(0)
                        break
            
            # Send completion signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            await asyncio.sleep(0)  # Final flush
            
        except GeneratorExit:
            # Client disconnected
            return
        except Exception as e:
            try:
                error_msg = f"Error during resume search: {str(e)}"
                yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                await asyncio.sleep(0)
            except:
                # If we can't even send the error, just return
                return
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


# -------------------- TTS Endpoint --------------------

@app.get("/api/test-stream")
async def test_stream_endpoint():
    """Simple test endpoint to verify SSE streaming works without buffering"""
    async def generate_test_stream():
        try:
            for i in range(10):
                yield f"data: {json.dumps({'type': 'test', 'message': f'Test chunk {i+1}/10', 'timestamp': asyncio.get_event_loop().time()})}\n\n"
                await asyncio.sleep(0)  # Flush event loop
                await asyncio.sleep(0.5)  # 500ms delay between chunks
            
            yield f"data: {json.dumps({'type': 'done', 'message': 'Test completed successfully!'})}\n\n"
            await asyncio.sleep(0)
            
        except GeneratorExit:
            return
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Test error: {str(e)}'})}\n\n"
            await asyncio.sleep(0)
    
    return StreamingResponse(
        generate_test_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",
        }
    )

@app.post("/api/tts")
async def tts_endpoint(request: TTSRequest):
    """Convert text to speech using ElevenLabs and return MP3 bytes."""
    try:
        audio_bytes = get_voice_bytes(request.text)
        return Response(content=audio_bytes, media_type="audio/mpeg", headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e:
        # Log full traceback on server for debugging
        import traceback, logging
        logging.error("TTS generation failed", exc_info=True)
        error_detail = {
            "error": str(e),
            "detail": traceback.format_exc(),
        }
        return JSONResponse(content=error_detail, status_code=500, headers={"Access-Control-Allow-Origin": "*"})

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
        import traceback, logging
        logging.error("TTS stream start failed", exc_info=True)
        error_detail = {
            "error": str(e),
            "detail": traceback.format_exc(),
        }
        return JSONResponse(content=error_detail, status_code=500, headers={"Access-Control-Allow-Origin": "*"})

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
        generate_audio_stream(),
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
        import traceback, logging
        logging.error("Gemini chat creation failed", exc_info=True)
        error_detail = {
            "error": str(e),
            "detail": traceback.format_exc(),
        }
        return JSONResponse(content=error_detail, status_code=500, headers={"Access-Control-Allow-Origin": "*"})

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
        generate_stream(),
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
        import traceback, logging
        logging.error("Gemini message failed", exc_info=True)
        error_detail = {
            "error": str(e),
            "detail": traceback.format_exc(),
        }
        return JSONResponse(content=error_detail, status_code=500, headers={"Access-Control-Allow-Origin": "*"})

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


# -------------------- Analytics Endpoints --------------------

@app.get("/api/analytics/stream")
async def analytics_stream_endpoint(query: str, request: Request, _: None = Depends(analytics_sql_rate_limit)):
    """Stream analytics results with LangGraph workflow visualization"""
    
    async def generate_analytics_stream():
        # Helper: recursively convert date/datetime to ISO strings for JSON serialization
        def _to_serializable(obj):
            if isinstance(obj, (_Date, _DateTime)):
                return obj.isoformat()
            if isinstance(obj, Decimal):
                return float(obj)
            if isinstance(obj, list):
                return [_to_serializable(x) for x in obj]
            if isinstance(obj, tuple):
                return tuple(_to_serializable(x) for x in obj)
            if isinstance(obj, dict):
                return {k: _to_serializable(v) for k, v in obj.items()}
            return obj
        try:
            print(f"[MAIN] Starting analytics stream for query: {query[:100]}...")
            
            # Create analytics workflow instance
            print("[MAIN] Creating analytics workflow...")
            analytics_workflow = await create_analytics_workflow()
            print("[MAIN] Analytics workflow created successfully")
            
            chunk_count = 0
            # Removed heartbeat tracking
            
            print("[MAIN] Starting workflow stream...")
            # Stream analytics workflow
            async for result in analytics_workflow.stream_analysis(query):
                try:
                    if result:
                        # Send the analytics update with proper event structure
                        yield f"data: {json.dumps(_to_serializable(result))}\n\n"
                        await asyncio.sleep(0)
                        chunk_count += 1
                        
                        # Removed heartbeat logic for analytics memory
                        
                        # Safety limit
                        if chunk_count > 1000:
                            print("[MAIN] Chunk limit reached, stopping...")
                            yield f"data: {json.dumps({'event': 'errors', 'data': {'errors': ['Response truncated due to length']}})}\n\n"
                            break
                            
                except Exception as chunk_error:
                    error_msg = f"Chunk error: {str(chunk_error)}"
                    print(f"[MAIN ERROR] {error_msg}")
                    yield f"data: {json.dumps({'event': 'errors', 'data': {'errors': [error_msg]}})}\n\n"
                    await asyncio.sleep(0)
                    break
            
            # Workflow handles its own completion signal
            await asyncio.sleep(0)
            
        except GeneratorExit:
            return
        except Exception as e:
            try:
                error_msg = f"Error during analytics: {str(e)}"
                print(f"[MAIN CRITICAL ERROR] {error_msg}")
                import traceback
                print(f"[MAIN CRITICAL ERROR] Traceback: {traceback.format_exc()}")
                yield f"data: {json.dumps({'event': 'errors', 'data': {'errors': [error_msg]}})}\n\n"
                await asyncio.sleep(0)
            except:
                return
    
    return StreamingResponse(
        generate_analytics_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive", 
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",
        }
    )

@app.get("/api/analytics/memory/stream")
async def analytics_memory_stream_endpoint(
    query: str,
    request: Request,
    session_id: Optional[str] = None,
    flow: Optional[str] = Query(default=None, description="Flow name (planner-executor | single-agent | multi-agent | single-agent-legacy | multi-agent-legacy)"),
    reset_session: bool = Query(default=False, description="Set true to clear cached agent state before running the workflow."),
    _: None = Depends(analytics_agent_rate_limit),
):
    """Stream analytics memory results with conversational clarifications"""
    legacy_mode = request.query_params.get('mode')
    requested_flow_raw = (flow or legacy_mode or '').strip() if (flow or legacy_mode) else ''

    # Respect explicit flow selection from the client while keeping single-agent as the default.
    allowed_flows = {
        "planner-executor",
        "single-agent",
        "multi-agent",
        "single-agent-legacy",
        "multi-agent-legacy",
    }
    if requested_flow_raw in allowed_flows:
        selected_flow = "single-agent" if requested_flow_raw.endswith("single-agent-legacy") else requested_flow_raw
        # Normalize legacy aliases to their modern equivalents
        if selected_flow == "single-agent-legacy":
            selected_flow = "single-agent"
        elif selected_flow == "multi-agent-legacy":
            selected_flow = "multi-agent"
    else:
        selected_flow = "single-agent"

    normalized_session = (session_id or "").strip()
    revision_requested = bool(infer_chart_patch_from_query(query)) or bool(is_analysis_revision_query(query))

    # Generate a session ID if not provided (revision flows must supply one)
    if not normalized_session:
        if revision_requested:
            raise HTTPException(status_code=400, detail="Revision follow-ups require an existing session_id.")
        normalized_session = str(uuid.uuid4())

    session_id = normalized_session
    
    async def generate_analytics_memory_stream():
        try:
            logger.info(f"[ANALYTICS_MEMORY] Starting stream - flow={selected_flow or 'default'} session={session_id}")

            # Run the analytics memory workflow 
            async for event in analytics_memory_workflow(
                query=query,
                session_id=session_id,
                flow=selected_flow,
                reset_session=reset_session,
            ):
                # Convert the event to SSE format
                event_data = json.dumps(event, default=str)
                
                # Yield the SSE event
                yield f"data: {event_data}\n\n"
                await asyncio.sleep(0)  # Allow other tasks to run
                
        except Exception as e:
            error_event = {
                "event": "error",
                "data": {
                    "error": str(e),
                    "ts": _DateTime.utcnow().isoformat()
                }
            }
            yield f"data: {json.dumps(error_event)}\n\n"
            await asyncio.sleep(0)
    
    
    return StreamingResponse(
        generate_analytics_memory_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*", 
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/analytics/memory/clarify")
async def analytics_memory_clarify_endpoint(answer: ClarifyAnswerModel, _: None = Depends(analytics_agent_rate_limit)):
    """Handle clarification responses for analytics flows."""
    try:
        logger.info(f"[ANALYTICS_MEMORY] Clarification answer received for session {answer.session_id}")
        await put_answer(answer)
        return {"status": "success", "message": "Clarification answer received"}
    except Exception as e:
        logger.error(f"[ANALYTICS_MEMORY] Clarification handling failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)










