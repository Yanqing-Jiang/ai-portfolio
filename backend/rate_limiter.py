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
    print(f"Redis not available: {e}")
    print("INFO: Rate limiting will use in-memory fallback (development mode)")
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
        
        # Decode the JWT token with proper audience validation
        # Supabase JWTs use 'authenticated' as the audience
        payload = jwt.decode(
            token, 
            SUPABASE_JWT_SECRET, 
            algorithms=["HS256"],
            audience="authenticated"
        )
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

async def manual_increment_counter(identifier: str, is_authenticated: bool) -> None:
    """Manually increment the Redis counter for the user"""
    if redis_pool is None:
        # Use in-memory fallback for development
        print(f"Using in-memory increment for identifier: {identifier}")
        current_count = in_memory_usage.get(identifier, 0)
        in_memory_usage[identifier] = current_count + 1
        print(f"In-memory count incremented: {identifier} -> {in_memory_usage[identifier]}")
        return
    
    try:
        # Find the existing Redis key for this identifier
        all_keys = await redis_pool.keys("*")
        target_key = None
        
        # Look for existing keys
        for key in all_keys:
            if identifier in key and (':5:' in key or ':20:' in key):
                target_key = key
                break
        
        if target_key:
            # Increment existing key
            new_count = await redis_pool.incr(target_key)
            print(f"REDIS INCREMENT - Key: {target_key}, New count: {new_count}")
        else:
            # Create new key with appropriate limit
            limit = GUEST_LIMIT if not is_authenticated else MEMBER_LIMIT
            new_key = f"fastapi-limiter:{identifier}:{limit}:0"
            await redis_pool.setex(new_key, LIMIT_WINDOW, 1)
            print(f"REDIS CREATE - New key: {new_key}, Count: 1")
            
    except Exception as e:
        print(f"ERROR: Failed to manually increment counter for {identifier}: {e}")
        # Fall back to in-memory tracking
        current_count = in_memory_usage.get(identifier, 0)
        in_memory_usage[identifier] = current_count + 1
        print(f"Fallback increment: {identifier} -> {in_memory_usage[identifier]}")

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
        # The actual pattern is fastapi-limiter:{identifier}:{limit}:{window_slot}
        possible_keys = [
            f"fastapi-limiter:{identifier}:{LIMIT_WINDOW}",
            f"fastapi-limiter:{identifier}:86400", 
            f"{identifier}:{LIMIT_WINDOW}",
            f"{identifier}:86400",
            f"fastapi-limiter:{identifier}",
            f"{identifier}"
        ]
        
        # Add keys with limit patterns (fastapi-limiter uses limit:window format)
        # Since we're using unified limiter with MEMBER_LIMIT (20), all keys will have :20:
        possible_keys.extend([
            f"fastapi-limiter:{identifier}:{MEMBER_LIMIT}:0",
            f"fastapi-limiter:{identifier}:{MEMBER_LIMIT}:1", 
            f"fastapi-limiter:{identifier}:{MEMBER_LIMIT}:2",
            f"fastapi-limiter:{identifier}:{MEMBER_LIMIT}:3",
            f"fastapi-limiter:{identifier}:{MEMBER_LIMIT}:4",
            f"fastapi-limiter:{identifier}:{MEMBER_LIMIT}:5",
        ])
        
        # Also check legacy keys with the old limits for backward compatibility
        possible_keys.extend([
            f"fastapi-limiter:{identifier}:{limit}:0",
            f"fastapi-limiter:{identifier}:{limit}:1", 
            f"fastapi-limiter:{identifier}:{limit}:2",
            f"fastapi-limiter:{identifier}:{limit}:3",
            f"fastapi-limiter:{identifier}:{limit}:4",
            f"fastapi-limiter:{identifier}:{limit}:5",
        ])
        
        # Also check for any keys that contain the identifier (wildcard search)
        for key in all_keys:
            if identifier in key:
                possible_keys.append(key)
        
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
        print("INFO: Redis not available, using in-memory rate limiting for development")
        return False

    try:
        await FastAPILimiter.init(redis_pool)
        print("Rate limiter initialized successfully with Redis")
        return True
    except Exception as e:
        print(f"WARNING: Failed to initialize rate limiter: {e}")
        print("INFO: Falling back to in-memory rate limiting")
        return False

# Create a unified rate limiter
def create_unified_rate_limiter():
    """Create a single rate limiter that we'll use for all users"""
    # Use the higher limit (20) and we'll manually check the appropriate limit in smart_rate_limit
    return RateLimiter(times=MEMBER_LIMIT, seconds=LIMIT_WINDOW, identifier=who_am_i)

# Initialize unified limiter with error handling
try:
    unified_rate_limiter = create_unified_rate_limiter()
    print("Unified rate limiter created successfully")
except Exception as e:
    print(f"WARNING: Failed to create rate limiter: {e}")
    print("INFO: Rate limiting will use fallback mechanisms")
    unified_rate_limiter = None

async def smart_rate_limit(request: Request):
    """Smart rate limiter based on authentication status"""
    # Check if rate limiting is disabled for local development
    disable_rate_limit = os.getenv("DISABLE_RATE_LIMIT", "false").lower()
    if disable_rate_limit == "true":
        # Double check that this is a local request for extra security
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")
        actual_ip = forwarded.split(',')[0] if forwarded else client_ip
        
        is_local = actual_ip in ["127.0.0.1", "localhost", "::1"] or actual_ip.startswith("192.168.") or actual_ip.startswith("10.") or actual_ip.startswith("172.")
        
        if is_local:
            print(f"RATE LIMIT BYPASS - Rate limiting disabled for local development (IP: {actual_ip})")
            return
        else:
            print(f"RATE LIMIT BYPASS DENIED - DISABLE_RATE_LIMIT=true but request not from local IP (IP: {actual_ip})")
    
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
    if unified_rate_limiter is None:
        print("Warning: Rate limiting disabled - limiter not available")
        return
    
    try:
        # Get current usage and manually increment
        current_usage, user_limit = await get_user_usage(identifier)
        limit = MEMBER_LIMIT if is_authenticated else GUEST_LIMIT
        
        print(f"MANUAL CHECK - {identifier}: {current_usage}/{limit}")
        
        # Check rate limits
        if not is_authenticated and current_usage >= GUEST_LIMIT:
            print(f"MANUAL RATE LIMIT - Guest {identifier} exceeded {GUEST_LIMIT}/day limit")
            raise HTTPException(
                status_code=401,
                detail="Sign-in required after free quota",
                headers={"Retry-After": "3600"}
            )
        elif is_authenticated and current_usage >= MEMBER_LIMIT:
            print(f"MANUAL RATE LIMIT - Member {identifier} exceeded {MEMBER_LIMIT}/day limit")
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": "3600"}
            )
        
        # Manually increment the counter in Redis
        await manual_increment_counter(identifier, is_authenticated)
        
        print(f"Rate limit check passed and counter incremented for {identifier}")
        
        # Debug: Check Redis count immediately after incrementing
        try:
            updated_usage, updated_limit = await get_user_usage(identifier)
            print(f"DEBUG - After manual increment: {identifier}, Count: {updated_usage}/{updated_limit}")
        except Exception as debug_error:
            print(f"DEBUG - Error checking updated usage: {debug_error}")
        
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