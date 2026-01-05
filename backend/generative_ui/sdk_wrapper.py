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
# Class: A2UISDKWrapper
#   Role: SDK-only wrapper for initialization, query, and streaming hooks.
#   Called from: backend.generative_ui.agent_v2 (via get_sdk_wrapper)
#   Invokes: ClaudeSDKClient, ClaudeAgentOptions, create_sdk_mcp_server
#   Why: Centralizes SDK client lifecycle and MCP wiring for A2UI.
# Method: A2UISDKWrapper.__init__
#   Role: Configure SDK wrapper state and settings.
#   Called from: backend.generative_ui.sdk_wrapper.get_sdk_wrapper
#   Invokes: backend.generative_ui.config.get_settings
#   Why: Binds model/API key/cwd defaults for SDK usage.
# Method: A2UISDKWrapper.is_sdk_available
#   Role: Report if claude-agent-sdk is installed.
#   Called from: diagnostics or tests (not used in runtime flow).
#   Invokes: n/a
#   Why: Supports readiness checks for the SDK-only path.
# Method: A2UISDKWrapper.initialize
#   Role: Initialize Claude Agent SDK client with MCP servers/tools.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent._ensure_sdk_initialized
#   Invokes: ClaudeAgentOptions, ClaudeSDKClient, create_sdk_mcp_server
#   Why: Ensures SDK client is ready for routing and future tool calls.
# Method: A2UISDKWrapper.query
#   Role: Execute a single SDK query and return the normalized response.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.select_skill
#   Invokes: A2UISDKWrapper._query_sdk
#   Why: Provides a clean async interface for non-streaming queries.
# Method: A2UISDKWrapper._query_sdk
#   Role: Run the SDK query loop and collect tool/text blocks.
#   Called from: backend.generative_ui.sdk_wrapper.A2UISDKWrapper.query
#   Invokes: ClaudeSDKClient.query, ClaudeSDKClient.receive_response
#   Why: Adapts SDK streaming messages into a single response payload.
# Method: A2UISDKWrapper.stream_query
#   Role: Yield SDK response chunks as they arrive.
#   Called from: n/a (reserved for streaming hooks)
#   Invokes: A2UISDKWrapper._stream_sdk
#   Why: Enables future streaming integrations without rewrites.
# Method: A2UISDKWrapper._stream_sdk
#   Role: Stream SDK messages and emit incremental SDKResponse chunks.
#   Called from: backend.generative_ui.sdk_wrapper.A2UISDKWrapper.stream_query
#   Invokes: ClaudeSDKClient.query, ClaudeSDKClient.receive_response
#   Why: Supports progressive UI updates for long-running SDK calls.
# Method: A2UISDKWrapper.close
#   Role: Clear SDK client resources for shutdown or reset.
#   Called from: n/a (reserved for lifecycle management)
#   Invokes: n/a
#   Why: Ensures clean teardown of SDK state.
# Function: get_sdk_wrapper
#   Role: Return the singleton SDK wrapper instance.
#   Called from: backend.generative_ui.agent_v2.get_a2ui_agent
#   Invokes: backend.generative_ui.sdk_wrapper.A2UISDKWrapper
#   Why: Reuses the SDK wrapper across requests.
# --- End SDK Wrapper Function/Class Map ---
"""
Claude Agent SDK wrapper for FastAPI backend integration.

Module: sdk_wrapper.py
Role: Provides an adapter layer between the Claude Agent SDK and the A2UI dashboard runtime.
Called from: agent_v2.py
Invokes: claude_agent_sdk (ClaudeSDKClient, ClaudeAgentOptions, create_sdk_mcp_server)
Why: Centralizes SDK initialization and query/stream handling for A2UI flows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

# Try importing Claude Agent SDK
try:
    from claude_agent_sdk import (
        ClaudeSDKClient,
        ClaudeAgentOptions,
        create_sdk_mcp_server,
        AssistantMessage,
        TextBlock,
        ToolUseBlock,
        ResultMessage,
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
    ResultMessage = None  # type: ignore

from .config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class SDKToolCall:
    """Represents a tool call from SDK response."""
    id: str
    name: str
    input: Dict[str, Any]


@dataclass
class SDKResponse:
    """Structured response from SDK execution."""
    content: str = ""
    tool_calls: List[SDKToolCall] = field(default_factory=list)
    is_complete: bool = False
    error: Optional[str] = None


@dataclass
class SDKMessage:
    """Message for SDK conversation."""
    role: str  # "user" or "assistant"
    content: str


class A2UISDKWrapper:
    """
    Wraps Claude Agent SDK for A2UI skill execution.

    Class: A2UISDKWrapper
    Role: Provides SDK-native execution for A2UI routing and future tool calls.
    Called from: A2UIAgent in agent_v2.py for skill selection.
    Why: Centralizes Claude Agent SDK initialization and response parsing for A2UI.
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
        self._mcp_server: Optional[Any] = None
        self._initialized = False

    @property
    def is_sdk_available(self) -> bool:
        """Check if Claude Agent SDK is available."""
        return SDK_AVAILABLE

    async def initialize(
        self,
        system_prompt: Optional[str | Dict[str, Any]] = None,
        allowed_tools: Optional[List[str]] = None,
        mcp_tools: Optional[List[Any]] = None,
        use_sdk: bool = True,
    ) -> bool:
        """
        Initialize the SDK client.

        Args:
            system_prompt: System prompt for the agent.
            allowed_tools: List of allowed tool names.
            mcp_tools: List of MCP tools (created with @tool decorator).
            use_sdk: Must be True (SDK-only runtime).

        Returns:
            True if SDK client is ready after initialization check.
        """
        if self._initialized:
            return self._sdk_client is not None

        if not use_sdk:
            raise RuntimeError("SDK-only runtime: use_sdk=False is not supported.")

        if not SDK_AVAILABLE:
            raise RuntimeError("Claude Agent SDK not available; install claude-agent-sdk.")

        mcp_servers: Dict[str, Any] = {}
        if mcp_tools:
            self._mcp_server = create_sdk_mcp_server(
                name="a2ui_tools",
                version="1.0.0",
                tools=mcp_tools,
            )
            mcp_servers["a2ui"] = self._mcp_server

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

        options = ClaudeAgentOptions(**options_kwargs)
        self._sdk_client = ClaudeSDKClient(options=options)
        self._initialized = True
        logger.info("Claude Agent SDK initialized successfully")
        return True

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
        if not self._sdk_client:
            raise RuntimeError("SDK client not initialized")
        return await self._query_sdk(prompt)

    async def _query_sdk(self, prompt: str) -> SDKResponse:
        """Execute query using Claude Agent SDK."""
        if not self._sdk_client:
            raise RuntimeError("SDK client not initialized")

        try:
            content_parts = []
            tool_calls = []

            async with self._sdk_client as client:
                await client.query(prompt)
                async for message in client.receive_response():
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
                    elif isinstance(message, ResultMessage):
                        # Conversation complete
                        pass

            return SDKResponse(
                content="".join(content_parts),
                tool_calls=tool_calls,
                is_complete=True,
            )

        except Exception as e:
            logger.error(f"SDK query failed: {e}")
            return SDKResponse(error=str(e), is_complete=True)

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

    async def close(self) -> None:
        """Clean up resources."""
        self._sdk_client = None
        self._mcp_server = None
        self._initialized = False


# Singleton instance
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
    """
    global _sdk_wrapper
    if _sdk_wrapper is None:
        _sdk_wrapper = A2UISDKWrapper(cwd=cwd, model=model, api_key=api_key)
    return _sdk_wrapper


__all__ = [
    "SDK_AVAILABLE",
    "SDKToolCall",
    "SDKResponse",
    "SDKMessage",
    "A2UISDKWrapper",
    "get_sdk_wrapper",
]
