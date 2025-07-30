import redis.asyncio as redis
from fastapi import Request, HTTPException, status, Depends
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from jose import jwt, JWTError
from math import ceil
import os
from typing import Optional, Dict, Tuple
from dotenv import load_dotenv
from pathlib import Path
import time

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

# Rate limiting constants
GUEST_LIMIT = 5
MEMBER_LIMIT = 20
LIMIT_WINDOW = 86400  # 24 hours in seconds

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

async def get_user_usage(identifier: str) -> Tuple[int, int]:
    """Get current usage count for a user identifier"""
    if redis_pool is None:
        return 0, GUEST_LIMIT if identifier.startswith("ip:") else MEMBER_LIMIT
    
    try:
        # Create Redis key for the identifier
        key = f"fastapi-limiter:{identifier}:86400"
        
        # Get current count from Redis
        current_count = await redis_pool.get(key)
        current_count = int(current_count) if current_count else 0
        
        # Determine limit based on identifier type
        is_guest = identifier.startswith("ip:")
        limit = GUEST_LIMIT if is_guest else MEMBER_LIMIT
        
        return current_count, limit
    except Exception as e:
        print(f"Warning: Failed to get usage count: {e}")
        is_guest = identifier.startswith("ip:")
        limit = GUEST_LIMIT if is_guest else MEMBER_LIMIT
        return 0, limit

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

# Create individual rate limiter dependencies
def create_guest_limiter():
    """Create rate limiter for guest users (5/day)"""
    return RateLimiter(times=GUEST_LIMIT, seconds=LIMIT_WINDOW, identifier=who_am_i)

def create_member_limiter():
    """Create rate limiter for authenticated users (20/day)"""  
    return RateLimiter(times=MEMBER_LIMIT, seconds=LIMIT_WINDOW, identifier=who_am_i)

# Initialize limiters with error handling
try:
    guest_rate_limiter = create_guest_limiter()
    member_rate_limiter = create_member_limiter()
    print("Rate limiters created successfully")
except Exception as e:
    print(f"Warning: Failed to create rate limiters: {e}")
    guest_rate_limiter = None
    member_rate_limiter = None

async def smart_rate_limit(request: Request):
    """Smart rate limiter based on authentication status"""
    if guest_rate_limiter is None or member_rate_limiter is None:
        print("Warning: Rate limiting disabled - limiters not available")
        return
    
    # Get user identifier and check authentication
    identifier = await who_am_i(request)
    is_authenticated = not identifier.startswith("ip:")
    
    try:
        if is_authenticated:
            # Use member rate limiter
            await member_rate_limiter(request, None)
        else:
            # Use guest rate limiter
            await guest_rate_limiter(request, None)
    except HTTPException as e:
        if e.status_code == 429:
            if is_authenticated:
                # Standard rate limit for members
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Please try again later.",
                    headers={"Retry-After": "3600"}
                )
            else:
                # Require auth for guests
                raise HTTPException(
                    status_code=401,
                    detail="Sign-in required after free quota",
                    headers={"Retry-After": "3600"}
                )
        else:
            raise e
    except Exception as e:
        print(f"Warning: Rate limiting error: {e}")
        return