import redis.asyncio as redis
from fastapi import Request, HTTPException, status
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from jose import jwt, JWTError
from math import ceil
import os
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)

# Redis connection - with error handling
try:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_pool = redis.from_url(
        redis_url, 
        encoding="utf-8", 
        decode_responses=True
    )
except Exception as e:
    print(f"Warning: Redis connection failed: {e}")
    redis_pool = None

# Supabase JWT secret - get this from your Supabase dashboard
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
if not SUPABASE_JWT_SECRET or SUPABASE_JWT_SECRET == "your-jwt-secret-here":
    print("Warning: SUPABASE_JWT_SECRET not properly configured in .env file")
    SUPABASE_JWT_SECRET = "fallback-secret-key"

def parse_user_id(token: str) -> Optional[str]:
    """Extract user ID from Supabase JWT token"""
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith("Bearer "):
            token = token[7:]
        
        # Decode the JWT token
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"])
        return payload.get("sub")  # 'sub' contains the user ID in Supabase
    except JWTError:
        return None

async def who_am_i(request: Request) -> str:
    """Identifier function that switches between IP and user_id based on authentication"""
    # Check for Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header:
        user_id = parse_user_id(auth_header)
        if user_id:
            return f"user:{user_id}"
    
    # Fallback to IP for guests
    forwarded = request.headers.get("X-Forwarded-For")
    client_ip = forwarded.split(',')[0] if forwarded else request.client.host
    return f"ip:{client_ip}"

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

async def init_rate_limiter():
    """Initialize the rate limiter with Redis"""
    if redis_pool is None:
        print("Warning: Redis not available, rate limiting disabled")
        return False
    
    try:
        await FastAPILimiter.init(redis_pool)
        print("Rate limiter initialized successfully")
        return True
    except Exception as e:
        print(f"Warning: Failed to initialize rate limiter: {e}")
        return False

# Rate limiters for different user types - with error handling
try:
    guest_limiter = RateLimiter(
        times=5, 
        seconds=86400,  # 24 hours
        identifier=who_am_i
    )

    authenticated_limiter = RateLimiter(
        times=20, 
        seconds=86400,  # 24 hours  
        identifier=who_am_i
    )
except Exception as e:
    print(f"Warning: Failed to create rate limiters: {e}")
    guest_limiter = None
    authenticated_limiter = None

async def smart_rate_limit(request: Request):
    """Smart rate limiter that applies different limits based on authentication status"""
    # If rate limiters are not available, skip rate limiting
    if guest_limiter is None or authenticated_limiter is None:
        print("Warning: Rate limiting disabled - limiters not available")
        return
    
    # Check if user is authenticated
    auth_header = request.headers.get("Authorization")
    is_authenticated = False
    
    if auth_header:
        user_id = parse_user_id(auth_header)
        is_authenticated = user_id is not None
    
    try:
        if is_authenticated:
            # Use higher limit for authenticated users
            await authenticated_limiter(request)
        else:
            # Use lower limit for guests and return 401 when exceeded
            await guest_limiter(request)
    except HTTPException as e:
        if e.status_code == 429:
            if is_authenticated:
                await rate_limit_callback(request, None, 0)
            else:
                await auth_required_callback(request, None, 0)
        else:
            # Re-raise other HTTP exceptions
            raise e
    except Exception as e:
        print(f"Warning: Rate limiting error: {e}")
        # Continue without rate limiting if there's an error
        return