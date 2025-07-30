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
redis_pool = None
try:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_pool = redis.from_url(
        redis_url, 
        encoding="utf-8", 
        decode_responses=True
    )
    print(f"Redis configured with URL: {redis_url}")
except Exception as e:
    print(f"Warning: Redis connection failed: {e}")
    print("Rate limiting will use in-memory fallback (development mode)")
    redis_pool = None

# In-memory fallback for development
in_memory_usage = {}

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
        print(f"JWT DEBUG - Raw token (first 50 chars): {token[:50]}...")
        
        # Remove 'Bearer ' prefix if present
        if token.startswith("Bearer "):
            token = token[7:]
            print(f"JWT DEBUG - After removing Bearer prefix: {token[:50]}...")
        
        # Decode the JWT token
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"])
        print(f"JWT DEBUG - Decoded payload: {payload}")
        
        user_id = payload.get("sub")
        print(f"JWT DEBUG - Extracted user ID: {user_id}")
        return user_id
    except JWTError as e:
        print(f"JWT DEBUG - JWT decode error: {e}")
        return None
    except Exception as e:
        print(f"JWT DEBUG - Unexpected error: {e}")
        return None

async def who_am_i(request: Request) -> str:
    """Identifier function that switches between IP and user_id based on authentication"""
    # Check for Authorization header
    auth_header = request.headers.get("Authorization")
    print(f"AUTH DEBUG - Authorization header: {auth_header}")
    
    if auth_header:
        user_id = parse_user_id(auth_header)
        print(f"AUTH DEBUG - Parsed user ID: {user_id}")
        if user_id:
            result = f"user:{user_id}"
            print(f"AUTH DEBUG - Returning authenticated identifier: {result}")
            return result
    
    # Fallback to IP for guests
    forwarded = request.headers.get("X-Forwarded-For")
    client_ip = forwarded.split(',')[0] if forwarded else request.client.host
    result = f"ip:{client_ip}"
    print(f"AUTH DEBUG - Returning guest identifier: {result}")
    return result

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
    # Determine limit based on identifier type
    is_guest = identifier.startswith("ip:")
    limit = GUEST_LIMIT if is_guest else MEMBER_LIMIT
    
    if redis_pool is None:
        # Use in-memory fallback for development
        print(f"Using in-memory fallback for identifier: {identifier}")
        current_count = in_memory_usage.get(identifier, 0)
        print(f"FALLBACK RESULT - Identifier: {identifier}, Count: {current_count}, Limit: {limit}, Is Guest: {is_guest}")
        return current_count, limit
    
    try:
        # First, let's see what keys exist in Redis
        all_keys = await redis_pool.keys("*")
        print(f"All Redis keys: {all_keys}")
        
        # Try multiple possible Redis key formats used by fastapi-limiter
        possible_keys = [
            f"fastapi-limiter:{identifier}:{LIMIT_WINDOW}",
            f"fastapi-limiter:{identifier}:86400", 
            f"{identifier}:{LIMIT_WINDOW}",
            f"{identifier}:86400",
            f"fastapi-limiter:{identifier}",
            f"{identifier}"
        ]
        
        current_count = 0
        key_found = None
        
        for key in possible_keys:
            count = await redis_pool.get(key)
            print(f"Checking key '{key}': {count}")
            if count is not None:
                current_count = int(count)
                key_found = key
                break
        
        print(f"REDIS RESULT - Identifier: {identifier}, Key: {key_found}, Count: {current_count}, Limit: {limit}, Is Guest: {is_guest}")
        
        return current_count, limit
    except Exception as e:
        print(f"ERROR: Failed to get usage count for {identifier}: {e}")
        # Fall back to in-memory tracking
        current_count = in_memory_usage.get(identifier, 0)
        print(f"FALLBACK RESULT - Identifier: {identifier}, Count: {current_count}, Limit: {limit}, Is Guest: {is_guest}")
        return current_count, limit

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
    # Get user identifier and check authentication
    identifier = await who_am_i(request)
    is_authenticated = not identifier.startswith("ip:")
    
    print(f"RATE LIMIT CHECK - Identifier: {identifier}, Is Authenticated: {is_authenticated}")
    
    # If Redis is not available, use simple in-memory rate limiting
    if redis_pool is None:
        print(f"Using in-memory rate limiting for {identifier}")
        
        # Simple in-memory rate limiting (resets on server restart)
        limit = MEMBER_LIMIT if is_authenticated else GUEST_LIMIT
        current_count = in_memory_usage.get(identifier, 0)
        
        if current_count >= limit:
            print(f"In-memory rate limit exceeded for {identifier}: {current_count}/{limit}")
            if is_authenticated:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Please try again later.",
                    headers={"Retry-After": "3600"}
                )
            else:
                raise HTTPException(
                    status_code=401,
                    detail="Sign-in required after free quota",
                    headers={"Retry-After": "3600"}
                )
        
        # Increment usage count
        in_memory_usage[identifier] = current_count + 1
        print(f"In-memory usage updated for {identifier}: {in_memory_usage[identifier]}/{limit}")
        return
    
    # Redis-based rate limiting
    if guest_rate_limiter is None or member_rate_limiter is None:
        print("Warning: Rate limiting disabled - limiters not available")
        return
    
    try:
        if is_authenticated:
            # Use member rate limiter
            print(f"Using member rate limiter for {identifier}")
            await member_rate_limiter(request, None)
        else:
            # Use guest rate limiter
            print(f"Using guest rate limiter for {identifier}")
            await guest_rate_limiter(request, None)
        
        print(f"Rate limit check passed for {identifier}")
        
    except HTTPException as e:
        print(f"Rate limit exceeded for {identifier}: {e.status_code} {e.detail}")
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
        print(f"ERROR: Rate limiting error for {identifier}: {e}")
        # Fall back to in-memory rate limiting on Redis errors
        print(f"Falling back to in-memory rate limiting for {identifier}")
        
        limit = MEMBER_LIMIT if is_authenticated else GUEST_LIMIT
        current_count = in_memory_usage.get(identifier, 0)
        
        if current_count >= limit:
            print(f"In-memory fallback rate limit exceeded for {identifier}: {current_count}/{limit}")
            if is_authenticated:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Please try again later.",
                    headers={"Retry-After": "3600"}
                )
            else:
                raise HTTPException(
                    status_code=401,
                    detail="Sign-in required after free quota",
                    headers={"Retry-After": "3600"}
                )
        
        # Increment usage count
        in_memory_usage[identifier] = current_count + 1
        print(f"Fallback usage updated for {identifier}: {in_memory_usage[identifier]}/{limit}")
        return