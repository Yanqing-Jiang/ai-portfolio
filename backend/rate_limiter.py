import logging
import redis.asyncio as redis
from enum import Enum
from fastapi import Request, HTTPException, status, Depends
try:
    from fastapi_limiter import FastAPILimiter
    from fastapi_limiter.depends import RateLimiter
except ImportError:
    FastAPILimiter = None  # type: ignore
    RateLimiter = None  # type: ignore
from jose import jwt, JWTError
from math import ceil
import os
from typing import Optional, Dict, Tuple, Any
from dotenv import load_dotenv
from pathlib import Path
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

try:
    from .token_store import token_store
except ImportError:  # pragma: no cover - allow execution as script
    from token_store import token_store  # type: ignore

# --- Function/Class Map ---
# Function: who_am_i — called from rate limiter dependencies and /api usage endpoints; chooses user:<id> or ip:<addr>.
# Function: smart_rate_limit — main guard used by API routes (chat, analytics, linkedin photo) to enforce per-scope limits and token fallback.
# Function: resolve_limits/resolve_scope — maps scopes to configured guest/member quotas.
# Function: manual_increment_counter/get_user_usage — shared helpers that read/write Redis (or in-memory fallback) and annotate request.state.
# Class: UsageSnapshot — lightweight struct for current usage, limit, and reset epoch.
# Purpose: Centralized rate limiting and identifier resolution for all backend endpoints.

# Load environment variables from .env file
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)

# Redis connection - with error handling
redis_pool = None

# Check if rate limiting is disabled first
disable_rate_limit = os.getenv("DISABLE_RATE_LIMIT", "false").lower() == "true"

if disable_rate_limit:
    logger.info("Rate limiting disabled via DISABLE_RATE_LIMIT=true")
    redis_pool = None
else:
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_pool = redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info(f"Redis configured with URL: {redis_url}")
    except Exception as e:
        logger.warning(f"Redis not available: {e}")
        logger.info("Rate limiting will use in-memory fallback (development mode)")
        redis_pool = None

# In-memory fallback for development
in_memory_usage = {}

# Supabase JWT secret - get this from your Supabase dashboard
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
_SUPABASE_JWT_CONFIGURED = bool(SUPABASE_JWT_SECRET and SUPABASE_JWT_SECRET != "your-jwt-secret-here")
if not _SUPABASE_JWT_CONFIGURED:
    logger.warning("SUPABASE_JWT_SECRET not properly configured — JWT auth disabled")
    SUPABASE_JWT_SECRET = None

SUPERUSER_EMAILS: set = set(
    e.strip().lower()
    for e in os.getenv("SUPERUSER_EMAILS", "").split(",")
    if e.strip()
)

# Rate limiting constants (prompt units)
GUEST_LIMIT = 5  # default guest limit for non-chat scopes
MEMBER_LIMIT = 20  # default member limit for non-chat scopes
CHAT_GUEST_LIMIT = 5
CHAT_MEMBER_LIMIT = 10
LIMIT_WINDOW = 86400  # legacy fallback; real TTL is until midnight UTC

class RateLimitScope(str, Enum):
    GLOBAL = "global"
    ANALYTICS_AGENT = "next-gen-analytics-agent"
    ANALYTICS_SQL = "next-gen-analytics-sql"
    CONVERSATIONAL_ANALYTICS = "conversational-analytics"
    CHAT = "chat"
    # FORTUNE kept as a coarse catch-all for legacy callers. Each fortune
    # workflow step also has its own scope so quotas match cost shape.
    FORTUNE = "fortune"
    FORTUNE_CREATE = "fortune-create"
    FORTUNE_STREAM = "fortune-stream"
    FORTUNE_ACTION = "fortune-action"
    FORTUNE_CORRECTION = "fortune-correction"
    FORTUNE_REPLAY = "fortune-replay"
    FORTUNE_ASK = "fortune-ask"
    FORTUNE_SIMULATE = "fortune-simulate"

# (guest_limit, member_limit)
SCOPE_LIMITS: Dict[RateLimitScope, Tuple[int, int]] = {
    RateLimitScope.GLOBAL: (GUEST_LIMIT, MEMBER_LIMIT),
    RateLimitScope.ANALYTICS_AGENT: (GUEST_LIMIT, MEMBER_LIMIT),
    RateLimitScope.ANALYTICS_SQL: (GUEST_LIMIT, MEMBER_LIMIT),
    RateLimitScope.CONVERSATIONAL_ANALYTICS: (GUEST_LIMIT, MEMBER_LIMIT),
    RateLimitScope.CHAT: (CHAT_GUEST_LIMIT, CHAT_MEMBER_LIMIT),
    RateLimitScope.FORTUNE: (GUEST_LIMIT, MEMBER_LIMIT),
    # /create spawns a whole pipeline — tighter guest cap.
    RateLimitScope.FORTUNE_CREATE: (3, MEMBER_LIMIT),
    # /stream is keyed off the same create run; loose because each create
    # only triggers one stream but the client may reconnect.
    RateLimitScope.FORTUNE_STREAM: (10, 40),
    RateLimitScope.FORTUNE_ACTION: (GUEST_LIMIT, MEMBER_LIMIT),
    RateLimitScope.FORTUNE_CORRECTION: (GUEST_LIMIT, MEMBER_LIMIT),
    RateLimitScope.FORTUNE_REPLAY: (GUEST_LIMIT, MEMBER_LIMIT),
    RateLimitScope.FORTUNE_ASK: (GUEST_LIMIT, MEMBER_LIMIT),
    RateLimitScope.FORTUNE_SIMULATE: (GUEST_LIMIT, MEMBER_LIMIT),
}

SCOPE_ALIAS_MAP: Dict[str, RateLimitScope] = {
    "global": RateLimitScope.GLOBAL,
    RateLimitScope.GLOBAL.value: RateLimitScope.GLOBAL,
    "analytics_agent": RateLimitScope.ANALYTICS_AGENT,
    "next-gen-analytics-agent": RateLimitScope.ANALYTICS_AGENT,
    "analytics_sql": RateLimitScope.ANALYTICS_SQL,
    "next-gen-analytics-sql": RateLimitScope.ANALYTICS_SQL,
    "conversational_analytics": RateLimitScope.CONVERSATIONAL_ANALYTICS,
    RateLimitScope.CONVERSATIONAL_ANALYTICS.value: RateLimitScope.CONVERSATIONAL_ANALYTICS,
    "chat": RateLimitScope.CHAT,
    RateLimitScope.CHAT.value: RateLimitScope.CHAT,
    "fortune": RateLimitScope.FORTUNE,
    RateLimitScope.FORTUNE.value: RateLimitScope.FORTUNE,
    "fortune_create": RateLimitScope.FORTUNE_CREATE,
    RateLimitScope.FORTUNE_CREATE.value: RateLimitScope.FORTUNE_CREATE,
    "fortune_stream": RateLimitScope.FORTUNE_STREAM,
    RateLimitScope.FORTUNE_STREAM.value: RateLimitScope.FORTUNE_STREAM,
    "fortune_action": RateLimitScope.FORTUNE_ACTION,
    RateLimitScope.FORTUNE_ACTION.value: RateLimitScope.FORTUNE_ACTION,
    "fortune_correction": RateLimitScope.FORTUNE_CORRECTION,
    RateLimitScope.FORTUNE_CORRECTION.value: RateLimitScope.FORTUNE_CORRECTION,
    "fortune_replay": RateLimitScope.FORTUNE_REPLAY,
    RateLimitScope.FORTUNE_REPLAY.value: RateLimitScope.FORTUNE_REPLAY,
    "fortune_ask": RateLimitScope.FORTUNE_ASK,
    RateLimitScope.FORTUNE_ASK.value: RateLimitScope.FORTUNE_ASK,
    "fortune_simulate": RateLimitScope.FORTUNE_SIMULATE,
    RateLimitScope.FORTUNE_SIMULATE.value: RateLimitScope.FORTUNE_SIMULATE,
}

@dataclass(slots=True)
class UsageSnapshot:
    """Represents current usage information for a scoped identifier."""

    count: int
    limit: int
    reset_epoch: int


@dataclass(slots=True)
class ParsedToken:
    user_id: str
    email: Optional[str] = None


def _redis_key(scoped_identifier: str) -> str:
    return f"prompt-limit:{scoped_identifier}"


def _next_midnight_utc(now: Optional[datetime] = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight


def seconds_until_midnight_utc(now: Optional[datetime] = None) -> int:
    now = now or datetime.now(timezone.utc)
    midnight = _next_midnight_utc(now)
    delta = midnight - now
    seconds = int(delta.total_seconds())
    return max(1, seconds)


def _touch_in_memory_usage(scoped_identifier: str) -> Dict[str, Any]:
    """Ensure an in-memory usage bucket exists and is within the current UTC day."""
    bucket = in_memory_usage.get(scoped_identifier)
    now = datetime.now(timezone.utc)
    if not bucket or now >= bucket.get("expires_at", now):
        expires_at = _next_midnight_utc(now)
        bucket = {"count": 0, "expires_at": expires_at}
        in_memory_usage[scoped_identifier] = bucket
    return bucket


def _in_memory_reset_epoch(bucket: Dict[str, Any]) -> int:
    expires_at: datetime = bucket.get("expires_at", _next_midnight_utc())
    return int(expires_at.timestamp())


def build_scoped_identifier(identifier: str, scope: RateLimitScope) -> str:
    """Append scope information to the identifier so quotas track per-workflow usage."""
    if scope == RateLimitScope.GLOBAL:
        return identifier
    return f"{identifier}|{scope.value}"

def resolve_limits(scope: RateLimitScope, is_authenticated: bool) -> int:
    """Return the effective limit for the scope and auth state."""
    guest_limit, member_limit = SCOPE_LIMITS.get(scope, (GUEST_LIMIT, MEMBER_LIMIT))
    return member_limit if is_authenticated else guest_limit

def resolve_scope(value: Optional[str]) -> RateLimitScope:
    """Resolve a string value into a RateLimitScope enum."""
    if not value:
        return RateLimitScope.GLOBAL
    normalized = value.strip().lower()
    return SCOPE_ALIAS_MAP.get(normalized, RateLimitScope.GLOBAL)

def parse_user_id(token: str) -> Optional[ParsedToken]:
    """Extract user ID and email from Supabase JWT token"""
    if not _SUPABASE_JWT_CONFIGURED:
        logger.debug("SUPABASE_JWT_SECRET not configured, refusing to verify tokens")
        return None
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith("Bearer "):
            token = token[7:]

        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )

        user_id = payload.get("sub")
        email = payload.get("email")
        if isinstance(email, str):
            email = email.strip().lower() or None
        else:
            email = None
        logger.debug("JWT parsed: user_id=%s", user_id)
        if not user_id:
            return None
        return ParsedToken(user_id=user_id, email=email)
    except JWTError as e:
        logger.debug("JWT decode error: %s", e)
        return None
    except Exception as e:
        logger.debug("JWT unexpected error: %s", e)
        return None

TRUST_FORWARDED_IP = os.getenv("TRUST_FORWARDED_IP", "false").lower() == "true"


def _guest_ip(request: Request) -> str:
    """Resolve the guest IP that the limiter will key against.

    In production the backend sits behind a Cloudflare Tunnel, so
    ``request.client.host`` is the tunnel's local endpoint — useless for
    per-caller rate limiting. The CF Pages BFF forwards the real caller on
    ``cf-connecting-ip`` (and mirrors it into ``x-forwarded-for``), but we
    must only trust those headers when we know the request came through our
    proxy — otherwise anyone can forge them. ``TRUST_FORWARDED_IP`` is set in
    ``.env.production`` and unset in local dev.
    """
    if TRUST_FORWARDED_IP:
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip:
            return cf_ip.strip()
        xff = request.headers.get("x-forwarded-for")
        if xff:
            # XFF may be a list "client, proxy1, proxy2" — leftmost is the
            # original client.
            first = xff.split(",", 1)[0].strip()
            if first:
                return first
    return request.client.host if request.client else "unknown"


async def who_am_i(request: Request) -> str:
    """
    Identifier function that switches between IP and user_id based on authentication.

    Function: who_am_i — extracts user identity from auth header or query param.
    Called from: smart_rate_limit
    Invokes: parse_user_id
    Why: Supports both header auth (fetch) and query param auth (EventSource/SSE).
    """
    # Check for Authorization header first
    auth_header = request.headers.get("Authorization")

    # Fallback to query param for EventSource (SSE doesn't support headers)
    if not auth_header:
        token = request.query_params.get("token")
        if token:
            auth_header = f"Bearer {token}"

    if auth_header:
        parsed = parse_user_id(auth_header)
        if parsed:
            request.state.user_email = parsed.email
            return f"user:{parsed.user_id}"

    # Fallback to IP for guests — use the trusted-proxy anchor if configured.
    return f"ip:{_guest_ip(request)}"

async def auth_required_callback(request: Request, response, pexpire: int):
    """Custom callback that returns 401 instead of 429 when rate limit is exceeded"""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sign-in required after free quota",
        headers={"Retry-After": str(ceil(pexpire/1000))}
    )

async def rate_limit_callback(request: Request, response, pexpire: int):
    """Standard rate limit callback for authenticated users"""
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded",
        headers={"Retry-After": str(ceil(pexpire/1000))}
    )


def is_superuser(request: Request) -> bool:
    """Check if the current request is from a superuser (unlimited access)."""
    email = getattr(request.state, "user_email", None)
    return bool(email and SUPERUSER_EMAILS and email in SUPERUSER_EMAILS)


async def manual_increment_counter(
    identifier: str,
    is_authenticated: bool,
    scope: RateLimitScope = RateLimitScope.GLOBAL,
    weight: int = 1,
) -> None:
    """Manually increment the Redis counter for the user"""
    scoped_identifier = build_scoped_identifier(identifier, scope)
    limit = resolve_limits(scope, is_authenticated)

    if weight <= 0:
        logger.debug(f"Ignoring non-positive weight={weight} for {scoped_identifier}")
        return

    if redis_pool is None:
        # Use in-memory fallback for development
        logger.debug(f"Using in-memory increment for identifier: {scoped_identifier}")
        bucket = _touch_in_memory_usage(scoped_identifier)
        bucket["count"] += weight
        logger.debug(
            f"In-memory count incremented: {scoped_identifier} -> "
            f"{bucket['count']} (limit {limit}, weight {weight})"
        )
        return
    
    try:
        key = _redis_key(scoped_identifier)
        new_count = await redis_pool.incrby(key, weight)
        ttl = await redis_pool.ttl(key)
        if ttl is None or ttl <= 0:
            await redis_pool.expire(key, seconds_until_midnight_utc())
        logger.debug(
            f"REDIS INCREMENT - Key: {key}, New count: {new_count}, "
            f"Limit: {limit}, Weight: {weight}"
        )
    except Exception as e:
        logger.error(f"Failed to manually increment counter for {scoped_identifier}: {e}")
        # Fall back to in-memory tracking
        bucket = _touch_in_memory_usage(scoped_identifier)
        bucket["count"] += weight
        logger.debug(
            f"Fallback increment: {scoped_identifier} -> {bucket['count']} "
            f"(limit {limit}, weight {weight})"
        )

async def get_user_usage(
    identifier: str,
    scope: RateLimitScope = RateLimitScope.GLOBAL,
) -> UsageSnapshot:
    """Get current usage count for a user identifier within a scope."""
    scoped_identifier = build_scoped_identifier(identifier, scope)
    is_guest = identifier.startswith("ip:")
    limit = resolve_limits(scope, not is_guest)

    if redis_pool is None:
        bucket = _touch_in_memory_usage(scoped_identifier)
        current_count = bucket["count"]
        reset_epoch = _in_memory_reset_epoch(bucket)
        logger.debug(
            f"FALLBACK RESULT - Identifier: {scoped_identifier}, Count: {current_count}, "
            f"Limit: {limit}, Is Guest: {is_guest}"
        )
        return UsageSnapshot(current_count, limit, reset_epoch)

    try:
        key = _redis_key(scoped_identifier)
        raw_count = await redis_pool.get(key)
        current_count = int(raw_count) if raw_count is not None else 0
        ttl = await redis_pool.ttl(key)

        if ttl is None or ttl < 0:
            reset_epoch = int(_next_midnight_utc().timestamp())
            if current_count > 0:
                await redis_pool.expire(key, seconds_until_midnight_utc())
        else:
            reset_epoch = int((datetime.now(timezone.utc) + timedelta(seconds=ttl)).timestamp())

        logger.debug(
            f"REDIS RESULT - Identifier: {scoped_identifier}, Key: {key}, "
            f"Count: {current_count}, Limit: {limit}, Is Guest: {is_guest}"
        )
        return UsageSnapshot(current_count, limit, reset_epoch)
    except Exception as e:
        logger.error(f"Failed to get usage count for {scoped_identifier}: {e}")
        bucket = _touch_in_memory_usage(scoped_identifier)
        current_count = bucket["count"]
        reset_epoch = _in_memory_reset_epoch(bucket)
        logger.debug(
            f"FALLBACK RESULT - Identifier: {scoped_identifier}, Count: {current_count}, "
            f"Limit: {limit}, Is Guest: {is_guest}"
        )
        return UsageSnapshot(current_count, limit, reset_epoch)

async def init_rate_limiter():
    """Initialize the rate limiter with Redis"""
    if redis_pool is None:
        logger.info("Redis not available, using in-memory rate limiting for development")
        return False

    try:
        await FastAPILimiter.init(redis_pool)
        logger.info("Rate limiter initialized successfully with Redis")
        return True
    except Exception as e:
        logger.warning(f"Failed to initialize rate limiter: {e}")
        logger.info("Falling back to in-memory rate limiting")
        return False

# Create a unified rate limiter
def create_unified_rate_limiter():
    """Create a single rate limiter that we'll use for all users"""
    # Use the higher limit (20) and we'll manually check the appropriate limit in smart_rate_limit
    return RateLimiter(times=MEMBER_LIMIT, seconds=LIMIT_WINDOW, identifier=who_am_i)

# Initialize unified limiter with error handling
try:
    unified_rate_limiter = create_unified_rate_limiter()
    logger.info("Unified rate limiter created successfully")
except Exception as e:
    logger.warning(f"Failed to create rate limiter: {e}")
    logger.info("Rate limiting will use fallback mechanisms")
    unified_rate_limiter = None

async def smart_rate_limit(
    request: Request,
    scope: RateLimitScope = RateLimitScope.GLOBAL,
    weight: int = 1,
):
    """Smart rate limiter based on authentication status and workflow scope"""
    # Check if rate limiting is disabled for local development
    disable_rate_limit = os.getenv("DISABLE_RATE_LIMIT", "false").lower()
    if disable_rate_limit == "true":
        # Use request.client.host only (not spoofable X-Forwarded-For)
        client_ip = request.client.host if request.client else "unknown"

        # RFC1918 + Docker Desktop's vmnetkit forwarding range (172.66.x on
        # modern Docker Desktop for Mac — outside the standard private
        # range but still purely a host→container forwarding IP, so it's
        # safe to treat as local for dev-bypass purposes).
        try:
            second = int(client_ip.split(".")[1])
        except (ValueError, IndexError):
            second = -1
        is_local = (
            client_ip in ("127.0.0.1", "::1")
            or client_ip.startswith("192.168.")
            or client_ip.startswith("10.")
            or (client_ip.startswith("172.") and 16 <= second <= 31)
            or (client_ip.startswith("172.") and second in (66, 67))
        )

        if is_local:
            logger.debug("Rate limit bypass for local dev (IP: %s)", client_ip)
            return
        else:
            logger.warning("Rate limit bypass denied — not local IP: %s", client_ip)

    if weight <= 0:
        logger.debug(f"RATE LIMIT - Ignoring non-positive weight={weight}")
        return

    # Get user identifier and check authentication
    identifier = await who_am_i(request)

    if is_superuser(request):
        logger.debug(f"SUPERUSER BYPASS - {identifier} skipping rate limit (scope={scope.value})")
        request.state.rate_limit_snapshot = UsageSnapshot(count=0, limit=999999, reset_epoch=0)
        request.state.rate_limit_weight = weight
        request.state.token_fallback_used = False
        return

    is_authenticated = not identifier.startswith("ip:")
    scoped_identifier = build_scoped_identifier(identifier, scope)
    limit = resolve_limits(scope, is_authenticated)

    logger.debug(
        f"RATE LIMIT CHECK - Identifier: {identifier}, Scope: {scope.value}, "
        f"Scoped ID: {scoped_identifier}, Limit: {limit}, Weight: {weight}, "
        f"Is Authenticated: {is_authenticated}"
    )

    usage_snapshot = await get_user_usage(identifier, scope)
    projected_total = usage_snapshot.count + weight
    retry_after_seconds = str(seconds_until_midnight_utc())

    token_fallback_used = False
    token_fallback_error: Optional[str] = None

    if projected_total > limit:
        logger.debug(
            f"RATE LIMIT THRESHOLD - {scoped_identifier} projected {projected_total}/{limit} "
            f"(weight {weight})"
        )
        if is_authenticated:
            user_id = identifier.split("user:", 1)[-1] if ":" in identifier else None
            if user_id and token_store.is_available:
                try:
                    token_fallback_used = await token_store.consume(user_id, weight)
                    if token_fallback_used:
                        logger.debug(
                            f"TOKEN FALLBACK - Consumed {weight} tokens for {user_id}; "
                            f"continuing request"
                        )
                except Exception as token_error:
                    token_fallback_error = str(token_error)
                    logger.debug(f"TOKEN FALLBACK ERROR - {token_fallback_error}")
            if not token_fallback_used:
                detail = "Rate limit exceeded. Please try again later."
                if token_fallback_error:
                    detail += f" ({token_fallback_error})"
                raise HTTPException(
                    status_code=429,
                    detail=detail,
                    headers={"Retry-After": retry_after_seconds},
                )
        else:
            logger.debug(f"GUEST RATE LIMIT - Guest {scoped_identifier} exceeded free quota")
            raise HTTPException(
                status_code=401,
                detail="Sign-in required after free quota",
                headers={"Retry-After": retry_after_seconds},
            )

    # Increment usage counter
    try:
        await manual_increment_counter(identifier, is_authenticated, scope, weight=weight)
        updated_snapshot = await get_user_usage(identifier, scope)
        logger.debug(
            f"Rate limit check passed for {scoped_identifier}. "
            f"Usage now {updated_snapshot.count}/{updated_snapshot.limit}"
        )
        request.state.rate_limit_snapshot = updated_snapshot
        request.state.rate_limit_weight = weight
        request.state.token_fallback_used = token_fallback_used
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rate limiting error for {scoped_identifier}: {e}")
        raise


async def analytics_agent_rate_limit(request: Request):
    """Rate limiter dedicated to the analytics memory workflows."""
    await smart_rate_limit(request, scope=RateLimitScope.ANALYTICS_AGENT)


async def analytics_sql_rate_limit(request: Request):
    """Rate limiter dedicated to the analytics SQL workflows."""
    await smart_rate_limit(request, scope=RateLimitScope.ANALYTICS_SQL)


async def conversational_analytics_rate_limit(request: Request):
    """Rate limiter for conversational analytics agent endpoints."""
    # Dev bypass: when CONV_ANALYTICS_SKIP_JWT is truthy, skip JWT enforcement for local development.
    if os.getenv("CONV_ANALYTICS_SKIP_JWT", "").lower() in {"1", "true", "yes"}:
        return

    # Share quota with general chat so usage is unified across projects
    await smart_rate_limit(request, scope=RateLimitScope.CHAT)
    # Allow unauthenticated guests up to the CHAT guest limit (5/day today); JWT users keep higher member limits.
    # smart_rate_limit already increments usage and enforces quotas; no extra JWT gate needed here.
    return
