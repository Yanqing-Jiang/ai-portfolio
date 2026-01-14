# --- API Wrapper Function/Class Map ---
# Dataclass: SDKToolCall
#   Role: Normalize tool-call payloads for agent consumers.
#   Called from: backend.generative_ui.sdk_wrapper.A2UISDKWrapper._query_api
#   Why: Standardizes tool call shape for downstream handling.
# Dataclass: SDKResponse
#   Role: Structured response container for API query results.
#   Called from: backend.generative_ui.sdk_wrapper.A2UISDKWrapper.query
#   Why: Keeps responses consistent across query modes.
# Class: PromptCache
#   Role: TTL-based cache for system prompts (Optimization #8).
#   Called from: A2UISDKWrapper.initialize
#   Why: Reduces redundant prompt processing and improves cache hit rates.
# Class: A2UISDKWrapper
#   Role: API wrapper for initialization and query handling.
#   Called from: backend.generative_ui.agent_v2 (via get_sdk_wrapper)
#   Invokes: anthropic.Anthropic.messages.create
#   Why: Centralizes Anthropic API client lifecycle for A2UI.
# --- End API Wrapper Function/Class Map ---
"""
Anthropic API wrapper for FastAPI backend integration.

Module: sdk_wrapper.py
Role: Provides an adapter layer between Anthropic API and the A2UI dashboard runtime.
Called from: agent_v2.py
Invokes: anthropic Messages API
Why: Centralizes API initialization and query handling for A2UI flows.

Note: This version uses the direct Anthropic Messages API instead of Claude Agent SDK
to avoid cold-boot overhead (~2-12s) that causes timeouts on resource-constrained
backends like Render.com.

Implements optimizations:
- #8: Improved System Prompt Caching with TTL
- #23: Circuit Breaker Pattern for API Resilience
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Try importing anthropic
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic = None  # type: ignore

from .config import get_settings

logger = logging.getLogger(__name__)

# Alias for backwards compatibility
SDK_AVAILABLE = ANTHROPIC_AVAILABLE


# ============================================================================
# Circuit Breaker Pattern (Optimization #23)
# Prevents cascade failures when external services are unavailable
# ============================================================================

class CircuitBreakerError(Exception):
    """Raised when circuit is open and calls are rejected."""
    pass


@dataclass
class CircuitBreaker:
    """
    Simple circuit breaker for API resilience.
    
    Class: CircuitBreaker
    Role: Prevents cascade failures by temporarily blocking calls to failing services.
    Called from: A2UISDKWrapper._query_api
    Why: Improves reliability when Anthropic API calls fail intermittently.
    
    States:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Failures exceeded threshold, calls are rejected immediately
    - HALF_OPEN: Recovery period, allows one test call through
    """
    failure_threshold: int = 5
    recovery_timeout: float = 60.0  # seconds
    
    _failure_count: int = field(default=0, repr=False)
    _last_failure_time: float = field(default=0.0, repr=False)
    _state: str = field(default="CLOSED", repr=False)
    
    def record_success(self) -> None:
        """
        Method: CircuitBreaker.record_success - reset failure counters after a success.
        Called from: backend.generative_ui.sdk_wrapper.A2UISDKWrapper._query_api.
        Why: Keeps API failure tracking accurate for future calls.
        """
        self._failure_count = 0
        self._state = "CLOSED"
        logger.debug("circuit_breaker=success state=CLOSED")
    
    def record_failure(self) -> None:
        """
        Method: CircuitBreaker.record_failure - record a failed API call and open the circuit if needed.
        Called from: backend.generative_ui.sdk_wrapper.A2UISDKWrapper._query_api.
        Why: Tracks API instability and prevents repeated failing calls.
        """
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._failure_count >= self.failure_threshold:
            self._state = "OPEN"
            logger.warning(
                "circuit_breaker=OPEN failures=%d threshold=%d timeout=%.0fs",
                self._failure_count,
                self.failure_threshold,
                self.recovery_timeout,
            )
        else:
            logger.debug(
                "circuit_breaker=failure count=%d/%d",
                self._failure_count,
                self.failure_threshold,
            )
    
    def can_execute(self) -> bool:
        """
        Method: CircuitBreaker.can_execute - check if the circuit allows a call.
        Called from: backend.generative_ui.sdk_wrapper.CircuitBreaker.check_or_raise.
        Why: Gates API calls during error bursts.
        """
        if self._state == "CLOSED":
            return True
        
        if self._state == "OPEN":
            # Check if recovery timeout has elapsed
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = "HALF_OPEN"
                logger.info(
                    "circuit_breaker=HALF_OPEN elapsed=%.1fs attempting_recovery",
                    elapsed,
                )
                return True
            return False
        
        # HALF_OPEN - allow one test call
        return True
    
    def check_or_raise(self) -> None:
        """
        Method: CircuitBreaker.check_or_raise - enforce circuit state with an error.
        Called from: backend.generative_ui.sdk_wrapper.A2UISDKWrapper._query_api.
        Why: Fails fast when the API is in a blocked state.
        """
        if not self.can_execute():
            raise CircuitBreakerError(
                f"Circuit breaker OPEN: {self._failure_count} failures in the last "
                f"{self.recovery_timeout:.0f}s. Retry after recovery timeout."
            )
    
    @property
    def stats(self) -> Dict[str, Any]:
        """
        Method: CircuitBreaker.stats - expose current breaker stats for diagnostics.
        Called from: backend.generative_ui.sdk_wrapper diagnostics/tests.
        Why: Surfaces state for troubleshooting API reliability.
        """
        return {
            "state": self._state,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_ago": time.time() - self._last_failure_time if self._last_failure_time else None,
        }


# Global circuit breaker for API calls
_api_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)


def get_circuit_breaker() -> CircuitBreaker:
    """
    Function: get_circuit_breaker - return the global API circuit breaker.
    Called from: backend.generative_ui.sdk_wrapper.A2UISDKWrapper._query_api.
    Why: Centralizes circuit breaker access for API calls.
    """
    return _api_circuit_breaker

# ============================================================================
# Prompt Cache (Optimization #8)
# ============================================================================

@dataclass
class CachedPrompt:
    """Cached prompt with metadata."""
    content: str
    hash_key: str
    created_at: float
    hit_count: int = 0


class PromptCache:
    """
    TTL-based cache for system prompts.
    
    Class: PromptCache
    Role: Caches compiled system prompts to avoid redundant processing.
    Called from: A2UISDKWrapper.initialize
    Why: Improves performance for repeated skill selections with same prompts.
    
    Implements Optimization #8 from optimization-recommendations.md
    """
    
    def __init__(self, ttl_seconds: int = 3600, max_size: int = 10):
        """
        Method: PromptCache.__init__ - initialize prompt cache storage.
        Called from: backend.generative_ui.sdk_wrapper.get_prompt_cache.
        Why: Keeps system prompts reusable without recomputation.
        """
        self._cache: Dict[str, CachedPrompt] = {}
        self._ttl = ttl_seconds
        self._max_size = max_size
    
    @staticmethod
    def _hash_prompt(prompt: str | Dict[str, Any]) -> str:
        """
        Method: PromptCache._hash_prompt - hash prompt content for cache keys.
        Called from: backend.generative_ui.sdk_wrapper.PromptCache.get, backend.generative_ui.sdk_wrapper.PromptCache.set.
        Why: Uses stable keys for prompt caching.
        """
        if isinstance(prompt, dict):
            content = str(sorted(prompt.items()))
        else:
            content = prompt
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    
    def get(self, prompt: str | Dict[str, Any]) -> Optional[str]:
        """
        Method: PromptCache.get - fetch a cached prompt when still valid.
        Called from: backend.generative_ui.sdk_wrapper.PromptCache.get_or_create.
        Why: Reuses system prompts to reduce API setup overhead.
        """
        hash_key = self._hash_prompt(prompt)
        cached = self._cache.get(hash_key)
        
        if cached is None:
            return None
        
        # Check TTL
        if time.time() - cached.created_at > self._ttl:
            del self._cache[hash_key]
            logger.debug("prompt_cache=expired key=%s", hash_key)
            return None
        
        cached.hit_count += 1
        logger.debug("prompt_cache=hit key=%s hits=%d", hash_key, cached.hit_count)
        return cached.content
    
    def get_or_create(
        self,
        prompt: str | Dict[str, Any],
        factory: "Callable[[], str]"
    ) -> str:
        """
        Method: PromptCache.get_or_create - return cached prompt or create it.
        Called from: backend.generative_ui.sdk_wrapper.A2UISDKWrapper.initialize.
        Why: Avoids recomputing system prompts between requests.
        """
        cached = self.get(prompt)
        if cached is not None:
            return cached
        
        # Create new prompt
        content = factory()
        self.set(prompt, content)
        return content
    
    def set(self, prompt: str | Dict[str, Any], content: str) -> None:
        """
        Method: PromptCache.set - store a prompt in the cache with eviction.
        Called from: backend.generative_ui.sdk_wrapper.PromptCache.get_or_create.
        Why: Keeps prompt cache bounded while retaining recent prompts.
        """
        hash_key = self._hash_prompt(prompt)
        
        # Evict oldest if full
        if len(self._cache) >= self._max_size:
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].created_at
            )
            del self._cache[oldest_key]
            logger.debug("prompt_cache=evicted key=%s", oldest_key)
        
        self._cache[hash_key] = CachedPrompt(
            content=content,
            hash_key=hash_key,
            created_at=time.time(),
        )
        logger.debug("prompt_cache=set key=%s", hash_key)
    
    def invalidate(self, prompt: Optional[str | Dict[str, Any]] = None) -> None:
        """
        Method: PromptCache.invalidate - remove cached prompts by key or all.
        Called from: backend.generative_ui.sdk_wrapper cache maintenance/debug.
        Why: Allows manual cache clearing during prompt changes.
        """
        if prompt is None:
            self._cache.clear()
            logger.debug("prompt_cache=cleared")
        else:
            hash_key = self._hash_prompt(prompt)
            if hash_key in self._cache:
                del self._cache[hash_key]
                logger.debug("prompt_cache=invalidated key=%s", hash_key)
    
    @property
    def stats(self) -> Dict[str, Any]:
        """
        Method: PromptCache.stats - return cache usage stats.
        Called from: backend.generative_ui.sdk_wrapper diagnostics/tests.
        Why: Exposes cache health to diagnostics.
        """
        total_hits = sum(p.hit_count for p in self._cache.values())
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "ttl_seconds": self._ttl,
            "total_hits": total_hits,
        }


# Global prompt cache instance
_prompt_cache = PromptCache(ttl_seconds=300, max_size=10)  # 5 min TTL


def get_prompt_cache() -> PromptCache:
    """
    Function: get_prompt_cache - return the global prompt cache instance.
    Called from: backend.generative_ui.sdk_wrapper.A2UISDKWrapper.__init__.
    Why: Keeps prompt cache shared across wrapper instances.
    """
    return _prompt_cache


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class SDKToolCall:
    """Represents a tool call from API response (for compatibility)."""
    id: str
    name: str
    input: Dict[str, Any]


@dataclass
class SDKToolResult:
    """
    Represents a tool result (for compatibility).
    """
    tool_use_id: str
    content: str | List[Dict[str, Any]] | None = None
    is_error: bool = False


@dataclass
class SDKResponse:
    """
    Structured response from API execution.
    """
    content: str = ""
    tool_calls: List[SDKToolCall] = field(default_factory=list)
    tool_results: List[SDKToolResult] = field(default_factory=list)
    is_complete: bool = False
    error: Optional[str] = None


@dataclass
class SDKMessage:
    """Message for API conversation."""
    role: str  # "user" or "assistant"
    content: str


# ============================================================================
# API Wrapper
# ============================================================================

class A2UISDKWrapper:
    """
    Wraps Anthropic API for A2UI skill execution.

    Class: A2UISDKWrapper
    Role: Provides API-native execution for A2UI routing.
    Called from: A2UIAgent in agent_v2.py for skill selection.
    Invokes: anthropic.Anthropic.messages.create
    Why: Centralizes Anthropic API initialization and response parsing for A2UI.
    
    Note: Uses direct Anthropic Messages API instead of Claude Agent SDK to avoid
    cold-boot overhead (2-12s) that causes timeouts on Render.com.
    """

    def __init__(
        self,
        cwd: Optional[Path] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Method: A2UISDKWrapper.__init__ - configure API wrapper state.
        Called from: backend.generative_ui.sdk_wrapper.get_sdk_wrapper.
        Invokes: backend.generative_ui.config.get_settings, get_prompt_cache.
        Why: Stores API config for reuse across A2UI requests.
        """
        self.cwd = cwd or Path(__file__).parent.parent
        self.settings = get_settings()
        self.model = model or self.settings.claude_model or "claude-haiku-4-5-20251001"
        self.api_key = api_key or self.settings.claude_api_key

        self._client: Optional[Any] = None
        self._system_prompt: Optional[str] = None
        self._tools: Optional[List[Dict[str, Any]]] = None
        self._initialized = False
        self._prompt_cache = get_prompt_cache()

    # ========================================================================
    # Async Context Manager
    # ========================================================================
    
    async def __aenter__(self) -> "A2UISDKWrapper":
        """
        Method: A2UISDKWrapper.__aenter__ - ensure API initialization on context entry.
        Called from: backend.generative_ui.sdk_wrapper.get_sdk_wrapper context usage.
        Invokes: A2UISDKWrapper.initialize.
        Why: Guarantees the API client is ready before queries.
        """
        if not self._initialized:
            await self.initialize()
        return self
    
    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any]
    ) -> bool:
        """
        Method: A2UISDKWrapper.__aexit__ - mark API state dirty on errors.
        Called from: backend.generative_ui.sdk_wrapper.get_sdk_wrapper context usage.
        Invokes: logger.error.
        Why: Forces re-init after errors without suppressing exceptions.
        """
        if exc_type is not None:
            logger.error(
                "API session error: %s: %s",
                exc_type.__name__,
                exc_val
            )
            self._initialized = False
        return False  # Don't suppress exceptions

    # ========================================================================
    # Properties
    # ========================================================================
    
    @property
    def is_sdk_available(self) -> bool:
        """
        Property: A2UISDKWrapper.is_sdk_available - report Anthropic import availability.
        Called from: backend.generative_ui.sdk_wrapper diagnostics/tests.
        Why: Exposes API availability for guard checks.
        """
        return ANTHROPIC_AVAILABLE

    @property
    def is_initialized(self) -> bool:
        """
        Property: A2UISDKWrapper.is_initialized - report API client readiness.
        Called from: backend.generative_ui.sdk_wrapper diagnostics/runtime checks.
        Why: Prevents queries before initialization.
        """
        return self._initialized and self._client is not None

    # ========================================================================
    
    async def initialize(
        self,
        system_prompt: Optional[str | Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        allowed_tools: Optional[List[str]] = None,
        mcp_tools: Optional[List[Any]] = None,
        use_sdk: Optional[bool] = None,
    ) -> bool:
        """
        Method: A2UISDKWrapper.initialize - initialize Anthropic API client for A2UI.
        Called from: backend.generative_ui.agent_v2.A2UIAgent._ensure_sdk_initialized.
        Invokes: anthropic.Anthropic.
        Why: Prepares the API client with system prompts and tools.
        
        Args:
            system_prompt: Optional system prompt for the conversation
            tools: Optional list of tool definitions for Claude to use
            allowed_tools, mcp_tools, use_sdk: Ignored (API mode only)
        """
        if not ANTHROPIC_AVAILABLE or anthropic is None:
            raise RuntimeError(
                "Anthropic package not available; install anthropic>=0.40.0"
            )

        # Store system prompt for queries
        if system_prompt is not None:
            if isinstance(system_prompt, dict):
                self._system_prompt = str(system_prompt)
            else:
                self._system_prompt = system_prompt
            
            # Cache the prompt (Optimization #8)
            cache_key = self._prompt_cache._hash_prompt(system_prompt)
            cached_prompt = self._prompt_cache.get(system_prompt)
            if cached_prompt:
                logger.debug("Using cached system prompt: %s", cache_key)
            else:
                self._prompt_cache.set(system_prompt, self._system_prompt)
                logger.debug("Cached new system prompt: %s", cache_key)

        # Store tools for queries
        if tools is not None:
            self._tools = tools
            logger.debug("Configured %d tools for API calls", len(tools))

        # Initialize Anthropic client (or reinitialize with new config)
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self.api_key)
            logger.info(
                "Anthropic API initialized: model=%s has_system_prompt=%s tools=%d",
                self.model,
                self._system_prompt is not None,
                len(self._tools) if self._tools else 0,
            )
        
        self._initialized = True
        return True

    # ========================================================================
    # Query Methods
    # ========================================================================
    
    async def query(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
    ) -> SDKResponse:
        """
        Method: A2UISDKWrapper.query - run an API query and return a parsed response.
        Called from: backend.generative_ui.agent_v2.A2UIAgent.select_skill, CommandRouter.classify_intent.
        Invokes: A2UISDKWrapper._query_api.
        Why: Centralizes API query handling for skill routing and intent classification.
        
        Args:
            prompt: User message to send
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            tools: Optional tool definitions (overrides instance tools if provided)
            messages: Optional message list for multi-turn context
            tool_choice: Optional Anthropic tool_choice override
        """
        if not self._client:
            raise RuntimeError("API client not initialized")

        return await self._query_api(
            prompt=prompt,
            max_tokens=max_tokens or 1024,
            temperature=temperature or 0.7,
            tools=tools or self._tools,
            messages=messages,
            tool_choice=tool_choice,
        )

    def _log_rate_limit_status(self, headers: Any) -> None:
        """
        Method: _log_rate_limit_status - monitor rate limit headers proactively.
        Called from: _query_api after API response.
        Why: Warns before hitting rate limits, per Anthropic best practices.
        """
        try:
            remaining_requests = headers.get("x-ratelimit-remaining-requests")
            remaining_tokens = headers.get("x-ratelimit-remaining-tokens")

            if remaining_requests is not None:
                remaining_req = int(remaining_requests)
                if remaining_req <= 5:
                    logger.warning(
                        "rate_limit_warning: requests remaining=%d (critical)",
                        remaining_req,
                    )
                elif remaining_req <= 20:
                    logger.info(
                        "rate_limit_status: requests remaining=%d",
                        remaining_req,
                    )

            if remaining_tokens is not None:
                remaining_tok = int(remaining_tokens)
                if remaining_tok <= 10000:
                    logger.warning(
                        "rate_limit_warning: tokens remaining=%d (critical)",
                        remaining_tok,
                    )
                elif remaining_tok <= 50000:
                    logger.info(
                        "rate_limit_status: tokens remaining=%d",
                        remaining_tok,
                    )
        except (TypeError, ValueError, AttributeError) as e:
            # Headers not available or malformed - skip monitoring
            logger.debug("rate_limit_headers not available: %s", e)

    async def _query_api(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
    ) -> SDKResponse:
        """
        Method: A2UISDKWrapper._query_api - execute an Anthropic API query.
        Called from: backend.generative_ui.sdk_wrapper.A2UISDKWrapper.query.
        Invokes: anthropic.Anthropic.messages.create, get_circuit_breaker.
        Why: Centralizes API response handling with resilience.
        
        Args:
            prompt: User message
            max_tokens: Maximum response tokens
            temperature: Sampling temperature
            tools: Optional tool definitions for tool-calling queries
            messages: Optional message list for multi-turn context
            tool_choice: Optional Anthropic tool_choice override
        """
        if not self._client:
            raise RuntimeError("API client not initialized")
        
        # Check circuit breaker before making the call
        circuit = get_circuit_breaker()
        try:
            circuit.check_or_raise()
        except CircuitBreakerError as e:
            logger.warning("API query blocked by circuit breaker: %s", e)
            return SDKResponse(error=str(e), is_complete=True)

        try:
            # Build request kwargs
            request_kwargs: Dict[str, Any] = {
                "model": self.model,
                "max_tokens": max_tokens,
            }
            
            # Build messages
            if messages:
                request_kwargs["messages"] = messages
            else:
                request_kwargs["messages"] = [{"role": "user", "content": prompt}]

            # Add system prompt with native cache_control for 1-hour Anthropic cache
            if self._system_prompt:
                request_kwargs["system"] = [
                    {
                        "type": "text",
                        "text": self._system_prompt,
                        "cache_control": {"type": "ephemeral"}
                    }
                ]

            # Add temperature if provided
            if temperature is not None:
                request_kwargs["temperature"] = temperature
            
            # Add tools if provided (for tool-calling queries)
            if tools:
                request_kwargs["tools"] = tools
                request_kwargs["tool_choice"] = tool_choice or {"type": "auto"}
                logger.debug("API call with %d tools", len(tools))
            
            # Make the API call with raw response to access rate limit headers
            raw_response = self._client.messages.with_raw_response.create(**request_kwargs)
            response = raw_response.parse()

            # Monitor rate limit headers (proactive warning before hitting limits)
            self._log_rate_limit_status(raw_response.headers)

            # Extract content from response
            content_parts = []
            tool_calls = []
            
            for block in response.content:
                if hasattr(block, 'text'):
                    content_parts.append(block.text)
                elif hasattr(block, 'type') and block.type == 'tool_use':
                    tool_calls.append(SDKToolCall(
                        id=block.id,
                        name=block.name,
                        input=block.input,
                    ))
            
            # Record success to close circuit if in HALF_OPEN state
            circuit.record_success()

            return SDKResponse(
                content="".join(content_parts),
                tool_calls=tool_calls,
                is_complete=True,
            )

        except anthropic.RateLimitError as e:
            # Handle 429 rate limit errors with retry-after header
            circuit.record_failure()
            retry_after = None
            try:
                if hasattr(e, "response") and e.response is not None:
                    retry_after = e.response.headers.get("retry-after")
            except Exception:
                pass

            if retry_after:
                logger.warning(
                    "rate_limit_exceeded: retry-after=%s seconds",
                    retry_after,
                )
                return SDKResponse(
                    error=f"Rate limit exceeded. Retry after {retry_after} seconds.",
                    is_complete=True,
                )
            else:
                logger.warning("rate_limit_exceeded: no retry-after header")
                return SDKResponse(error=str(e), is_complete=True)

        except Exception as e:
            # Record failure for circuit breaker
            circuit.record_failure()
            logger.error(f"API query failed: {e}")
            return SDKResponse(error=str(e), is_complete=True)

    # ========================================================================
    # Streaming Tool Use (Phase 5 - Fine-Grained Tool Streaming)
    # ========================================================================
    
    async def stream_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ):
        """
        Stream LLM response with fine-grained tool parameter streaming.
        
        Method: stream_with_tools - enables streaming tool use for component selection.
        Called from: ComponentSelector.stream_components
        Invokes: anthropic.messages.stream with fine-grained-tool-streaming beta
        Why: Allows progressive widget rendering as LLM generates selections.
        
        Args:
            prompt: User message to send
            tools: Tool definitions for component selection
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (lower for more deterministic)
            
        Yields:
            Dict events: {"type": "partial_json" | "block_complete" | "done", ...}
        """
        if not self._client:
            raise RuntimeError("API client not initialized")
        
        # Check circuit breaker
        circuit = get_circuit_breaker()
        try:
            circuit.check_or_raise()
        except CircuitBreakerError as e:
            logger.warning("Streaming blocked by circuit breaker: %s", e)
            yield {"type": "error", "error": str(e)}
            return
        
        try:
            # Build request kwargs
            request_kwargs: Dict[str, Any] = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "tools": tools,
                "tool_choice": {"type": "any"},  # Force tool use
            }

            # Add system prompt with native cache_control for 1-hour Anthropic cache
            if self._system_prompt:
                request_kwargs["system"] = [
                    {
                        "type": "text",
                        "text": self._system_prompt,
                        "cache_control": {"type": "ephemeral"}
                    }
                ]
            
            if temperature is not None:
                request_kwargs["temperature"] = temperature
            
            logger.debug(
                "Starting fine-grained tool streaming: tools=%d, max_tokens=%d",
                len(tools), max_tokens
            )
            
            # Use streaming with fine-grained tool streaming beta
            # Beta header enables input_json_delta events for partial JSON
            with self._client.messages.stream(
                **request_kwargs,
                extra_headers={"anthropic-beta": "fine-grained-tool-streaming-2025-05-14"},
            ) as stream:
                for event in stream:
                    # content_block_delta with input_json_delta contains partial JSON
                    if event.type == "content_block_delta":
                        if hasattr(event.delta, "partial_json"):
                            yield {
                                "type": "partial_json",
                                "content": event.delta.partial_json,
                            }
                        elif hasattr(event.delta, "text"):
                            # Text delta (if any text output)
                            yield {
                                "type": "text_delta",
                                "content": event.delta.text,
                            }
                    
                    # content_block_stop indicates a complete content block
                    elif event.type == "content_block_stop":
                        yield {"type": "block_complete"}
                    
                    # message_stop indicates end of response
                    elif event.type == "message_stop":
                        yield {"type": "done"}
            
            # Record success
            circuit.record_success()
            logger.debug("Fine-grained tool streaming completed successfully")
            
        except anthropic.RateLimitError as e:
            # Handle 429 rate limit errors with retry-after header
            circuit.record_failure()
            retry_after = None
            try:
                if hasattr(e, "response") and e.response is not None:
                    retry_after = e.response.headers.get("retry-after")
            except Exception:
                pass

            if retry_after:
                logger.warning(
                    "streaming_rate_limit_exceeded: retry-after=%s seconds",
                    retry_after,
                )
                yield {
                    "type": "error",
                    "error": f"Rate limit exceeded. Retry after {retry_after} seconds.",
                    "retry_after": retry_after,
                }
            else:
                logger.warning("streaming_rate_limit_exceeded: no retry-after header")
                yield {"type": "error", "error": str(e)}

        except Exception as e:
            circuit.record_failure()
            logger.error("Streaming failed: %s", e)
            yield {"type": "error", "error": str(e)}

    # ========================================================================
    # Lifecycle Management
    # ========================================================================
    
    async def close(self) -> None:
        """
        Method: A2UISDKWrapper.close - release API client resources.
        Called from: backend.generative_ui.sdk_wrapper.close_sdk_wrapper and shutdown hooks.
        Why: Ensures clean teardown of API state.
        """
        self._client = None
        self._system_prompt = None
        self._initialized = False
        logger.debug("API wrapper closed")


# ============================================================================
# Singleton Management
# ============================================================================

_sdk_wrapper: Optional[A2UISDKWrapper] = None


def get_sdk_wrapper(
    cwd: Optional[Path] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> A2UISDKWrapper:
    """
    Function: get_sdk_wrapper - return the API wrapper singleton.
    Called from: backend.generative_ui.agent_v2.get_a2ui_agent.
    Invokes: backend.generative_ui.sdk_wrapper.A2UISDKWrapper.
    Why: Reuses API client state across requests to reduce overhead.
    
    Usage with async context manager:
    ```python
    async with get_sdk_wrapper() as api:
        result = await api.query(prompt)
    ```
    """
    global _sdk_wrapper
    if _sdk_wrapper is None:
        _sdk_wrapper = A2UISDKWrapper(cwd=cwd, model=model, api_key=api_key)
    return _sdk_wrapper


async def close_sdk_wrapper() -> None:
    """
    Function: close_sdk_wrapper - close and clear the API wrapper singleton.
    Called from: backend.generative_ui.sdk_wrapper shutdown hooks.
    Invokes: backend.generative_ui.sdk_wrapper.A2UISDKWrapper.close.
    Why: Ensures API resources are released on shutdown.
    """
    global _sdk_wrapper
    if _sdk_wrapper is not None:
        await _sdk_wrapper.close()
        _sdk_wrapper = None


# Stub for backwards compatibility with SDK hooks
def create_sdk_hooks() -> None:
    """No-op stub for backwards compatibility. SDK hooks are not used in API mode."""
    return None


__all__ = [
    "SDK_AVAILABLE",
    "ANTHROPIC_AVAILABLE",
    "SDKToolCall",
    "SDKToolResult",
    "SDKResponse",
    "SDKMessage",
    "A2UISDKWrapper",
    "get_sdk_wrapper",
    "close_sdk_wrapper",
    "PromptCache",
    "get_prompt_cache",
    "create_sdk_hooks",
    "CircuitBreaker",
    "CircuitBreakerError",
    "get_circuit_breaker",
]
