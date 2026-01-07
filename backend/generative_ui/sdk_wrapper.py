# --- SDK Wrapper Function/Class Map ---
# Dataclass: SDKToolCall
#   Role: Normalize SDK tool-call payloads for agent consumers.
#   Called from: backend.generative_ui.sdk_wrapper.A2UISDKWrapper._query_sdk,
#   backend.generative_ui.sdk_wrapper.A2UISDKWrapper._stream_sdk
#   Invokes: n/a
#   Why: Standardizes tool call shape for downstream handling.
# Dataclass: SDKResponse
#   Role: Structured response container for SDK query/stream results.
#   Called from: backend.generative_ui.sdk_wrapper.A2UISDKWrapper.query,
#   backend.generative_ui.sdk_wrapper.A2UISDKWrapper._query_sdk,
#   backend.generative_ui.sdk_wrapper.A2UISDKWrapper._stream_sdk
#   Invokes: n/a
#   Why: Keeps SDK responses consistent across blocking/streaming modes.
# Dataclass: SDKMessage
#   Role: Reserve a message container for SDK conversations.
#   Called from: n/a (reserved for future SDK message handling)
#   Invokes: n/a
#   Why: Aligns with SDK message payload structure for future extensions.
# Class: PromptCache
#   Role: TTL-based cache for system prompts (Optimization #8).
#   Called from: A2UISDKWrapper.initialize
#   Invokes: n/a
#   Why: Reduces redundant prompt processing and improves cache hit rates.
# Class: A2UISDKWrapper
#   Role: SDK-only wrapper for initialization, query, and streaming hooks.
#   Called from: backend.generative_ui.agent_v2 (via get_sdk_wrapper)
#   Invokes: ClaudeSDKClient, ClaudeAgentOptions, create_sdk_mcp_server
#   Why: Centralizes SDK client lifecycle and MCP wiring for A2UI.
# Method: A2UISDKWrapper.__aenter__/__aexit__
#   Role: Async context manager for SDK sessions (Optimization #12).
#   Called from: with-statement in routes/runtime
#   Invokes: initialize, close
#   Why: Ensures proper lifecycle management and cleanup.
# --- End SDK Wrapper Function/Class Map ---
"""
Claude Agent SDK wrapper for FastAPI backend integration.

Module: sdk_wrapper.py
Role: Provides an adapter layer between Claude APIs and the A2UI dashboard runtime.
Called from: agent_v2.py
Invokes: anthropic (default) or claude_agent_sdk (experimental, use_sdk=True)
Why: Centralizes API/SDK initialization and query/stream handling for A2UI flows.

⚠️ NOTE: The Claude Agent SDK is EXPERIMENTAL and disabled by default.
Default mode uses the standard Anthropic API (use_sdk=False).
To experiment with SDK, set use_sdk=True in initialize() calls.
See docs/sdk-issues-and-fixes.md for details on SDK issues.

Implements optimizations:
- #8: Improved System Prompt Caching with TTL
- #12: Async Context Manager for SDK Sessions
- #23: Circuit Breaker Pattern for API Resilience
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

# Try importing Anthropic API (fallback when SDK unavailable)
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None  # type: ignore
    ANTHROPIC_AVAILABLE = False

# Try importing Claude Agent SDK
try:
    from claude_agent_sdk import (
        ClaudeSDKClient,
        ClaudeAgentOptions,
        create_sdk_mcp_server,
        AssistantMessage,
        TextBlock,
        ToolUseBlock,
        ToolResultBlock,  # Added for tool output handling
        ResultMessage,
        HookMatcher,  # Added for observability hooks
        HookContext,  # Added for hook callbacks
    )
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    # Provide stubs for type checking
    ClaudeSDKClient = None  # type: ignore
    ClaudeAgentOptions = None  # type: ignore
    create_sdk_mcp_server = None  # type: ignore
    AssistantMessage = None  # type: ignore
    TextBlock = None  # type: ignore
    ToolUseBlock = None  # type: ignore
    ToolResultBlock = None  # type: ignore
    ResultMessage = None  # type: ignore
    HookMatcher = None  # type: ignore
    HookContext = None  # type: ignore

from .config import get_settings

logger = logging.getLogger(__name__)


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
    Simple circuit breaker for SDK/API resilience.
    
    Class: CircuitBreaker
    Role: Prevents cascade failures by temporarily blocking calls to failing services.
    Called from: A2UISDKWrapper._query_sdk, A2UISDKWrapper._query_anthropic
    Why: Improves reliability when Claude API or SDK has transient failures.
    
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
        """Record a successful call - resets failure count."""
        self._failure_count = 0
        self._state = "CLOSED"
        logger.debug("circuit_breaker=success state=CLOSED")
    
    def record_failure(self) -> None:
        """Record a failed call - may open circuit."""
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
        Check if a call is allowed through the circuit breaker.
        
        Returns:
            True if call should proceed, False if circuit is open
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
        Check circuit state and raise if calls are blocked.
        
        Raises:
            CircuitBreakerError: If circuit is open and recovery timeout hasn't elapsed
        """
        if not self.can_execute():
            raise CircuitBreakerError(
                f"Circuit breaker OPEN: {self._failure_count} failures in the last "
                f"{self.recovery_timeout:.0f}s. Retry after recovery timeout."
            )
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Return circuit breaker statistics."""
        return {
            "state": self._state,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_ago": time.time() - self._last_failure_time if self._last_failure_time else None,
        }


# Global circuit breaker for SDK/API calls
_sdk_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)


def get_circuit_breaker() -> CircuitBreaker:
    """Get the global SDK circuit breaker instance."""
    return _sdk_circuit_breaker

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
        Initialize the prompt cache.
        
        Args:
            ttl_seconds: Time-to-live for cached prompts (default: 1 hour).
            max_size: Maximum number of prompts to cache.
        """
        self._cache: Dict[str, CachedPrompt] = {}
        self._ttl = ttl_seconds
        self._max_size = max_size
    
    @staticmethod
    def _hash_prompt(prompt: str | Dict[str, Any]) -> str:
        """Generate a hash key for the prompt."""
        if isinstance(prompt, dict):
            content = str(sorted(prompt.items()))
        else:
            content = prompt
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    
    def get(self, prompt: str | Dict[str, Any]) -> Optional[str]:
        """
        Get a cached prompt if valid.
        
        Returns:
            Cached prompt content if found and not expired, None otherwise.
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
        factory: Callable[[], str]
    ) -> str:
        """
        Get cached prompt or create new one.
        
        Args:
            prompt: Prompt to cache (used for key generation).
            factory: Function to call if cache miss.
            
        Returns:
            Cached or newly created prompt content.
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
        Cache a prompt.
        
        Evicts oldest entries if cache is full.
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
        Invalidate cached prompt(s).
        
        Args:
            prompt: Specific prompt to invalidate, or None to clear all.
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
        """Return cache statistics."""
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
    """Get the global prompt cache instance."""
    return _prompt_cache


# ============================================================================
# SDK Hooks for Observability (Optimization #2)
# See: https://platform.claude.com/docs/en/agent-sdk/hooks
# ============================================================================

async def _pre_tool_use_hook(
    input_data: Dict[str, Any],
    tool_use_id: Optional[str],
    context: Any,  # HookContext, but may be None if SDK not available
) -> Dict[str, Any]:
    """
    Hook called before SDK executes a tool.
    
    Logs tool invocation details for observability.
    
    Args:
        input_data: Contains tool_name, tool_input, session_id, etc.
        tool_use_id: ID to correlate with PostToolUse events.
        context: Reserved for future use (cancellation signal in TS).
    
    Returns:
        Empty dict to allow tool execution without modification.
    """
    tool_name = input_data.get("tool_name", "unknown")
    tool_input = input_data.get("tool_input", {})
    session_id = input_data.get("session_id", "unknown")
    
    logger.info(
        "SDK_HOOK PreToolUse: tool=%s session=%s id=%s",
        tool_name,
        session_id,
        tool_use_id,
    )
    logger.debug("SDK_HOOK PreToolUse input: %s", tool_input)
    
    # Return empty dict to allow tool execution
    return {}


async def _post_tool_use_hook(
    input_data: Dict[str, Any],
    tool_use_id: Optional[str],
    context: Any,
) -> Dict[str, Any]:
    """
    Hook called after SDK executes a tool.
    
    Logs tool completion for observability.
    
    Args:
        input_data: Contains tool_name, tool_response, session_id, etc.
        tool_use_id: ID to correlate with PreToolUse events.
        context: Reserved for future use.
    
    Returns:
        Empty dict - no modifications to response.
    """
    tool_name = input_data.get("tool_name", "unknown")
    tool_response = input_data.get("tool_response")
    session_id = input_data.get("session_id", "unknown")
    
    # Check if there was an error
    is_error = False
    if isinstance(tool_response, dict):
        is_error = tool_response.get("is_error", False)
    
    log_level = logging.WARNING if is_error else logging.INFO
    logger.log(
        log_level,
        "SDK_HOOK PostToolUse: tool=%s session=%s id=%s error=%s",
        tool_name,
        session_id,
        tool_use_id,
        is_error,
    )
    
    return {}


def create_sdk_hooks() -> Optional[Dict[str, List[Any]]]:
    """
    Create SDK hooks configuration for observability.
    
    Returns:
        Hook configuration dict for ClaudeAgentOptions, or None if SDK unavailable.
    
    Usage:
        options = ClaudeAgentOptions(
            hooks=create_sdk_hooks(),
            ...
        )
    """
    if not SDK_AVAILABLE or HookMatcher is None:
        logger.debug("SDK hooks unavailable - HookMatcher not imported")
        return None
    
    return {
        "PreToolUse": [
            HookMatcher(hooks=[_pre_tool_use_hook]),  # Applies to all tools
        ],
        "PostToolUse": [
            HookMatcher(hooks=[_post_tool_use_hook]),
        ],
    }


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class SDKToolCall:
    """Represents a tool call (ToolUseBlock) from SDK response."""
    id: str
    name: str
    input: Dict[str, Any]


@dataclass
class SDKToolResult:
    """
    Represents a tool result (ToolResultBlock) from SDK response.
    
    This captures the actual output after SDK executes MCP tools.
    See: https://platform.claude.com/docs/en/agent-sdk/python#toolresultblock
    """
    tool_use_id: str
    content: str | List[Dict[str, Any]] | None = None
    is_error: bool = False


@dataclass
class SDKResponse:
    """
    Structured response from SDK execution.
    
    Includes both tool calls (ToolUseBlock) and tool results (ToolResultBlock)
    to properly capture the full SDK tool execution cycle.
    """
    content: str = ""
    tool_calls: List[SDKToolCall] = field(default_factory=list)
    tool_results: List[SDKToolResult] = field(default_factory=list)  # Added for tool outputs
    is_complete: bool = False
    error: Optional[str] = None


@dataclass
class SDKMessage:
    """Message for SDK conversation."""
    role: str  # "user" or "assistant"
    content: str


# ============================================================================
# SDK Wrapper
# ============================================================================

class A2UISDKWrapper:
    """
    Wraps Claude Agent SDK for A2UI skill execution.

    Class: A2UISDKWrapper
    Role: Provides SDK-native execution for A2UI routing and future tool calls.
    Called from: A2UIAgent in agent_v2.py for skill selection.
    Why: Centralizes Claude Agent SDK initialization and response parsing for A2UI.
    
    Supports async context manager pattern (Optimization #12):
    ```python
    async with get_sdk_wrapper() as sdk:
        result = await sdk.query(prompt)
    ```
    """

    def __init__(
        self,
        cwd: Optional[Path] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the SDK wrapper.
        
        Args:
            cwd: Working directory for SDK operations (defaults to backend root).
            model: Claude model to use (defaults from settings).
            api_key: API key (defaults from settings).
        """
        self.cwd = cwd or Path(__file__).parent.parent
        self.settings = get_settings()
        self.model = model or self.settings.claude_model or "claude-haiku-4-5-20251001"
        self.api_key = api_key or self.settings.claude_api_key

        self._sdk_client: Optional[Any] = None
        self._anthropic_client: Optional[Any] = None  # Fallback client
        self._mcp_server: Optional[Any] = None
        self._initialized = False
        self._using_fallback = False  # Track if using fallback mode
        self._system_prompt: Optional[str] = None  # Store system prompt for fallback
        self._prompt_cache = get_prompt_cache()

    # ========================================================================
    # Async Context Manager (Optimization #12)
    # ========================================================================
    
    async def __aenter__(self) -> "A2UISDKWrapper":
        """Enter async context - initializes SDK if needed."""
        if not self._initialized:
            await self.initialize()
        return self
    
    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any]
    ) -> bool:
        """Exit async context - cleans up resources on error."""
        if exc_type is not None:
            logger.error(
                "SDK session error: %s: %s",
                exc_type.__name__,
                exc_val
            )
            # Don't fully close on error - let the singleton be reused
            # But we should reinitialize on next use
            self._initialized = False
        return False  # Don't suppress exceptions

    # ========================================================================
    # Properties
    # ========================================================================
    
    @property
    def is_sdk_available(self) -> bool:
        """Check if Claude Agent SDK is available."""
        return SDK_AVAILABLE

    @property
    def is_initialized(self) -> bool:
        """Check if SDK client is initialized."""
        return self._initialized and self._sdk_client is not None

    # ========================================================================
    
    async def initialize(
        self,
        system_prompt: Optional[str | Dict[str, Any]] = None,
        allowed_tools: Optional[List[str]] = None,
        mcp_tools: Optional[List[Any]] = None,
        use_sdk: bool = False,  # EXPERIMENTAL: SDK disabled by default, use Anthropic API
    ) -> bool:
        """
        Initialize the client for A2UI execution.

        Args:
            system_prompt: System prompt for the agent.
            allowed_tools: List of allowed tool names (SDK only).
            mcp_tools: List of MCP tools (SDK only, created with @tool decorator).
            use_sdk: EXPERIMENTAL - If True, use Claude Agent SDK (has issues on Windows/Render).
                     If False, use standard Anthropic API (default, stable).

        Returns:
            True if client is ready after initialization.
        """
        if self._initialized:
            return self._sdk_client is not None or self._anthropic_client is not None

        # Store system prompt for use in queries
        if system_prompt is not None:
            self._system_prompt = system_prompt if isinstance(system_prompt, str) else str(system_prompt)

        # Decide which client to use
        if not use_sdk:
            # Use Anthropic API directly (default, stable path)
            if not ANTHROPIC_AVAILABLE:
                raise RuntimeError(
                    "Anthropic API not available; install anthropic package."
                )
            logger.info(
                "Using Anthropic API (stable mode): model=%s",
                self.model,
            )
            self._anthropic_client = anthropic.AsyncAnthropic(api_key=self.api_key)
            self._using_fallback = True  # This flag indicates non-SDK mode
            self._initialized = True
            return True

        # EXPERIMENTAL: Use Claude Agent SDK
        if not SDK_AVAILABLE:
            if not ANTHROPIC_AVAILABLE:
                raise RuntimeError(
                    "Neither Claude Agent SDK nor Anthropic API available; "
                    "install claude-agent-sdk or anthropic."
                )
            # Fall back to Anthropic API
            logger.warning(
                "Claude Agent SDK not available (use_sdk=True), falling back to Anthropic API"
            )
            self._anthropic_client = anthropic.AsyncAnthropic(api_key=self.api_key)
            self._using_fallback = True
            self._initialized = True
            logger.info(
                "Anthropic API fallback initialized: model=%s",
                self.model,
            )
            return True

        # SDK is available - use it
        mcp_servers: Dict[str, Any] = {}
        if mcp_tools:
            self._mcp_server = create_sdk_mcp_server(
                name="a2ui_tools",
                version="1.0.0",
                tools=mcp_tools,
            )
            mcp_servers["a2ui"] = self._mcp_server

        # Use prompt cache for system prompt (Optimization #8)
        cached_prompt = None
        if system_prompt is not None:
            cache_key = self._prompt_cache._hash_prompt(system_prompt)
            cached_prompt = self._prompt_cache.get(system_prompt)
            if cached_prompt:
                logger.debug("Using cached system prompt: %s", cache_key)
            else:
                # Cache the prompt for future use
                prompt_content = system_prompt if isinstance(system_prompt, str) else str(system_prompt)
                self._prompt_cache.set(system_prompt, prompt_content)
                logger.debug("Cached new system prompt: %s", cache_key)

        options_kwargs: Dict[str, Any] = {
            "permission_mode": "default",
            "setting_sources": ["user", "project"],
            "cwd": str(self.cwd),
        }
        if system_prompt is not None:
            options_kwargs["system_prompt"] = system_prompt
        if allowed_tools:
            options_kwargs["allowed_tools"] = allowed_tools
        if mcp_servers:
            options_kwargs["mcp_servers"] = mcp_servers
        
        # Add observability hooks (Optimization #2)
        hooks = create_sdk_hooks()
        if hooks:
            options_kwargs["hooks"] = hooks
            logger.debug("SDK hooks enabled for observability")

        # Windows fix: Prefer user-installed Claude CLI locations before bundled binary
        # The bundled CLI often fails on Windows with "Failed to start Claude Code"
        # See: https://github.com/anthropics/claude-agent-sdk/issues
        import os
        import shutil
        cli_path = None
        
        if os.name == 'nt':
            # Windows: Check for npm-installed Claude CLI (Roaming\npm) and user-local bin
            npm_claude = os.path.expandvars(r'%APPDATA%\\npm\\claude.cmd')
            home_local_bin = Path.home() / ".local" / "bin"
            home_local_candidates = [
                home_local_bin / "claude.exe",
                home_local_bin / "claude.cmd",
                home_local_bin / "claude",
            ]
            if os.path.exists(npm_claude):
                cli_path = npm_claude
                logger.info("Using npm-installed Claude CLI (Windows): %s", cli_path)
            elif any(p.exists() for p in home_local_candidates):
                cli_path = str(next(p for p in home_local_candidates if p.exists()))
                logger.info("Using user-local Claude CLI (Windows): %s", cli_path)
            else:
                # Try to find claude.cmd in PATH
                claude_cmd = shutil.which('claude.cmd')
                if claude_cmd:
                    cli_path = claude_cmd
                    logger.info("Using Claude CLI from PATH (Windows): %s", cli_path)
        else:
            # Linux/Mac (Render.com, Docker, etc.): Check for npm global install
            linux_paths = [
                str(Path.home() / ".local" / "bin" / "claude"),  # user-local install
                '/usr/local/bin/claude',  # npm global install location
                '/opt/render/project/src/.render/claude',  # Render-specific
                shutil.which('claude'),  # In PATH
            ]
            for path in linux_paths:
                if path and os.path.exists(path):
                    cli_path = path
                    logger.info("Using npm-installed Claude CLI (Linux/Mac): %s", cli_path)
                    break
        
        if cli_path:
            options_kwargs["cli_path"] = cli_path

        options = ClaudeAgentOptions(**options_kwargs)
        self._sdk_client = ClaudeSDKClient(options=options)
        self._initialized = True
        
        # Pre-initialize Anthropic client as fallback (in case SDK fails at runtime)
        if ANTHROPIC_AVAILABLE and self.api_key and not self._anthropic_client:
            try:
                self._anthropic_client = anthropic.AsyncAnthropic(api_key=self.api_key)
                logger.debug("Anthropic API fallback pre-initialized as backup")
            except Exception as e:
                logger.warning("Failed to pre-initialize Anthropic fallback: %s", e)
        
        logger.info(
            "Claude Agent SDK initialized: hooks=%s mcp_servers=%s tools=%s",
            hooks is not None,
            list(mcp_servers.keys()) if mcp_servers else [],
            allowed_tools[:3] if allowed_tools else [],  # Log first 3 tools
        )
        return True

    # ========================================================================
    # Query Methods
    # ========================================================================
    
    async def query(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> SDKResponse:
        """
        Execute a query using the Claude Agent SDK.

        Method: query
        Role: Unified interface for executing Claude queries via SDK.
        Called from: A2UIAgent.select_skill
        Why: Keeps SDK usage centralized and easy to swap for streaming later.

        Args:
            prompt: User prompt to send.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.

        Returns:
            SDKResponse with content, tool calls, and completion status.
        """
        if self._using_fallback:
            return await self._query_anthropic(prompt, max_tokens, temperature)
        if not self._sdk_client:
            raise RuntimeError("SDK client not initialized")
        
        # Try SDK first, fall back to Anthropic API on runtime errors
        result = await self._query_sdk(prompt)
        
        # If SDK failed with a subprocess/CLI error, switch to fallback and retry
        if result.error and self._is_cli_runtime_error(result.error):
            logger.warning(
                "SDK runtime error detected, switching to Anthropic API fallback: %s",
                result.error
            )
            # Initialize fallback client if not already done
            if not self._anthropic_client and ANTHROPIC_AVAILABLE:
                self._anthropic_client = anthropic.AsyncAnthropic(api_key=self.api_key)
                self._using_fallback = True
                logger.info("Anthropic API fallback initialized after SDK failure")
            
            if self._anthropic_client:
                return await self._query_anthropic(prompt, max_tokens, temperature)
        
        return result

    @staticmethod
    def _is_cli_runtime_error(error_text: Optional[str]) -> bool:
        """
        Function: _is_cli_runtime_error
        Called from: query
        Invokes: n/a
        Why: Detects broad SDK CLI/runtime failures so we can fall back to Anthropic.
        """
        if not error_text:
            return False
        
        lowered = error_text.lower()
        cli_error_tokens = [
            "failed to start claude code",
            "subprocess",
            "clinotfound",
            "cli not found",
            "processerror",
            "winerror",
            "enoent",
            "no such file or directory",
            "not recognized as an internal or external command",
            "exec format error",
            "permission denied",
            "failed to spawn process",
            "cannot execute binary file",
            "circuit breaker",  # Circuit breaker is open - SDK repeatedly failing
            "connection refused",
            "timeout",
        ]
        return any(token in lowered for token in cli_error_tokens)

    async def _query_sdk(self, prompt: str) -> SDKResponse:
        """
        Execute query using Claude Agent SDK with circuit breaker protection.
        
        Correctly handles both ToolUseBlock (tool invocation request) and 
        ToolResultBlock (tool execution output) per SDK documentation.
        
        Includes circuit breaker pattern (Optimization #23) to prevent cascade
        failures when SDK service is unavailable.
        
        See: https://platform.claude.com/docs/en/agent-sdk/python#content-block-types
        """
        if not self._sdk_client:
            raise RuntimeError("SDK client not initialized")
        
        # Check circuit breaker before making the call
        circuit = get_circuit_breaker()
        try:
            circuit.check_or_raise()
        except CircuitBreakerError as e:
            logger.warning("SDK query blocked by circuit breaker: %s", e)
            return SDKResponse(error=str(e), is_complete=True)

        try:
            content_parts = []
            tool_calls = []
            tool_results = []

            async with self._sdk_client as client:
                await client.query(prompt)
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                content_parts.append(block.text)
                            elif isinstance(block, ToolUseBlock):
                                # SDK is requesting a tool call
                                tool_calls.append(SDKToolCall(
                                    id=block.id,
                                    name=block.name,
                                    input=block.input,
                                ))
                            elif ToolResultBlock is not None and isinstance(block, ToolResultBlock):
                                # SDK has executed an MCP tool and returned the result
                                tool_results.append(SDKToolResult(
                                    tool_use_id=block.tool_use_id,
                                    content=block.content,
                                    is_error=block.is_error or False,
                                ))
                    elif isinstance(message, ResultMessage):
                        # Conversation complete
                        pass
            
            # Record success to close circuit if in HALF_OPEN state
            circuit.record_success()

            return SDKResponse(
                content="".join(content_parts),
                tool_calls=tool_calls,
                tool_results=tool_results,
                is_complete=True,
            )

        except Exception as e:
            # Record failure for circuit breaker
            circuit.record_failure()
            logger.error(f"SDK query failed: {e}")
            return SDKResponse(error=str(e), is_complete=True)

    async def _query_anthropic(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> SDKResponse:
        """
        Execute query using Anthropic API directly (fallback mode) with circuit breaker.
        
        Used when Claude Agent SDK is not available. Provides basic
        message completion without MCP tool support.
        
        Includes circuit breaker pattern (Optimization #23) to prevent cascade
        failures when API service is unavailable.
        
        Args:
            prompt: User prompt to send.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
        
        Returns:
            SDKResponse with content from direct API call.
        """
        if not self._anthropic_client:
            raise RuntimeError("Anthropic client not initialized")
        
        # Check circuit breaker before making the call
        circuit = get_circuit_breaker()
        try:
            circuit.check_or_raise()
        except CircuitBreakerError as e:
            logger.warning("Anthropic API query blocked by circuit breaker: %s", e)
            return SDKResponse(error=str(e), is_complete=True)

        try:
            messages = [{"role": "user", "content": prompt}]
            
            # Build request kwargs
            request_kwargs: Dict[str, Any] = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": messages,
            }
            
            # Add system prompt if available
            if self._system_prompt:
                request_kwargs["system"] = self._system_prompt
            
            response = await self._anthropic_client.messages.create(**request_kwargs)
            
            # Extract text content
            content_parts = []
            for block in response.content:
                if hasattr(block, 'text'):
                    content_parts.append(block.text)
            
            # Record success to close circuit if in HALF_OPEN state
            circuit.record_success()
            
            return SDKResponse(
                content="".join(content_parts),
                tool_calls=[],
                tool_results=[],
                is_complete=True,
            )

        except Exception as e:
            # Record failure for circuit breaker
            circuit.record_failure()
            logger.error(f"Anthropic API query failed: {e}")
            return SDKResponse(error=str(e), is_complete=True)

    # ========================================================================
    # Streaming Methods
    # ========================================================================
    
    async def stream_query(
        self,
        prompt: str,
    ) -> AsyncIterator[SDKResponse]:
        """
        Stream responses from the SDK.

        Method: stream_query
        Role: Streaming interface for real-time response handling.
        Called from: n/a (reserved for streaming integrations).
        Why: Enables progressive UI updates during long-running SDK queries.

        Yields:
            SDKResponse chunks as they arrive.
        """
        if not self._sdk_client:
            raise RuntimeError("SDK client not initialized")
        async for chunk in self._stream_sdk(prompt):
            yield chunk

    async def _stream_sdk(self, prompt: str) -> AsyncIterator[SDKResponse]:
        """Stream from Claude Agent SDK."""
        if not self._sdk_client:
            raise RuntimeError("SDK client not initialized")

        try:
            async with self._sdk_client as client:
                await client.query(prompt)
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        content = ""
                        tool_calls = []
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                content = block.text
                            elif isinstance(block, ToolUseBlock):
                                tool_calls.append(SDKToolCall(
                                    id=block.id,
                                    name=block.name,
                                    input=block.input,
                                ))
                        yield SDKResponse(
                            content=content,
                            tool_calls=tool_calls,
                            is_complete=False,
                        )
                    elif isinstance(message, ResultMessage):
                        yield SDKResponse(is_complete=True)
        except Exception as e:
            logger.error(f"SDK streaming failed: {e}")
            yield SDKResponse(error=str(e), is_complete=True)

    # ========================================================================
    # Session Continuity (Optimization #3)
    # See: https://platform.claude.com/docs/en/agent-sdk/python#claudesdkclient
    # ========================================================================
    
    async def start_session(self, initial_prompt: Optional[str] = None) -> None:
        """
        Start a persistent session for multi-turn conversations.
        
        Unlike single-shot query(), this maintains conversation context
        across multiple follow_up() calls. Use for clarification flows.
        
        Args:
            initial_prompt: Optional initial prompt to start the session.
        
        Raises:
            RuntimeError: If SDK client not initialized.
        """
        if not self._sdk_client:
            raise RuntimeError("SDK client not initialized - call initialize() first")
        
        # Connect without entering context manager (we manage lifecycle manually)
        if initial_prompt:
            await self._sdk_client.connect(prompt=initial_prompt)
            logger.info("SDK session started with initial prompt")
        else:
            await self._sdk_client.connect()
            logger.info("SDK session started (no initial prompt)")
    
    async def follow_up(self, prompt: str, session_id: str = "default") -> SDKResponse:
        """
        Continue a conversation with context from previous turns.
        
        Must call start_session() first. Claude remembers previous
        messages in the session, reducing token usage for multi-turn flows.
        
        Args:
            prompt: Follow-up prompt to send.
            session_id: Session identifier (default: "default").
        
        Returns:
            SDKResponse with content and tool results.
        
        Raises:
            RuntimeError: If session not started.
        """
        if not self._sdk_client:
            raise RuntimeError("No active session - call start_session() first")
        
        try:
            content_parts = []
            tool_calls = []
            tool_results = []
            
            # Query within existing session (maintains context)
            await self._sdk_client.query(prompt, session_id=session_id)
            
            async for message in self._sdk_client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            content_parts.append(block.text)
                        elif isinstance(block, ToolUseBlock):
                            tool_calls.append(SDKToolCall(
                                id=block.id,
                                name=block.name,
                                input=block.input,
                            ))
                        elif ToolResultBlock is not None and isinstance(block, ToolResultBlock):
                            tool_results.append(SDKToolResult(
                                tool_use_id=block.tool_use_id,
                                content=block.content,
                                is_error=block.is_error or False,
                            ))
                elif isinstance(message, ResultMessage):
                    pass  # Conversation turn complete
            
            return SDKResponse(
                content="".join(content_parts),
                tool_calls=tool_calls,
                tool_results=tool_results,
                is_complete=True,
            )
        
        except Exception as e:
            logger.error(f"SDK follow_up failed: {e}")
            return SDKResponse(error=str(e), is_complete=True)
    
    async def end_session(self) -> None:
        """
        End the current session and disconnect.
        
        After calling, you must call start_session() again for new conversations.
        """
        if self._sdk_client and hasattr(self._sdk_client, 'disconnect'):
            try:
                await self._sdk_client.disconnect()
                logger.info("SDK session ended")
            except Exception as e:
                logger.warning("Error ending SDK session: %s", e)

    # ========================================================================
    # Lifecycle Management
    # ========================================================================
    
    async def close(self) -> None:
        """
        Clean up SDK resources.
        
        Method: close
        Role: Release SDK client and MCP server resources.
        Called from: async context manager __aexit__, shutdown hooks
        Why: Ensures clean teardown of SDK state.
        """
        if self._sdk_client:
            # SDK client cleanup if it has a close method
            if hasattr(self._sdk_client, 'close'):
                try:
                    await self._sdk_client.close()
                except Exception as e:
                    logger.warning("Error closing SDK client: %s", e)
        
        self._sdk_client = None
        self._mcp_server = None
        self._initialized = False
        logger.debug("SDK wrapper closed")


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
    Get or create the SDK wrapper singleton.
    
    Function: get_sdk_wrapper
    Role: Provide a singleton SDK wrapper instance.
    Called from: backend.generative_ui.agent_v2.get_a2ui_agent
    Why: Avoids reinitializing SDK client on every request.
    
    Usage with async context manager (Optimization #12):
    ```python
    async with get_sdk_wrapper() as sdk:
        result = await sdk.query(prompt)
    ```
    """
    global _sdk_wrapper
    if _sdk_wrapper is None:
        _sdk_wrapper = A2UISDKWrapper(cwd=cwd, model=model, api_key=api_key)
    return _sdk_wrapper


async def close_sdk_wrapper() -> None:
    """
    Close the SDK wrapper singleton.
    
    Call during application shutdown to clean up resources.
    """
    global _sdk_wrapper
    if _sdk_wrapper is not None:
        await _sdk_wrapper.close()
        _sdk_wrapper = None


__all__ = [
    "SDK_AVAILABLE",
    "SDKToolCall",
    "SDKToolResult",  # New: for tool output handling
    "SDKResponse",
    "SDKMessage",
    "A2UISDKWrapper",
    "get_sdk_wrapper",
    "close_sdk_wrapper",
    "PromptCache",
    "get_prompt_cache",
    "create_sdk_hooks",  # New: for observability
    "CircuitBreaker",  # New: for resilience (Optimization #23)
    "CircuitBreakerError",  # New: for resilience (Optimization #23)
    "get_circuit_breaker",  # New: for resilience (Optimization #23)
]
