"""
Claude Agent SDK wrapper for FastAPI backend integration.

Module: sdk_wrapper.py
Role: Provides an adapter layer between the Claude Agent SDK and the A2UI dashboard runtime.
Called from: agent_v2.py, runtime.py
Invokes: claude_agent_sdk (ClaudeSDKClient, query, tool), anthropic.Anthropic (fallback)
Why: Enables SDK-native execution while maintaining backward compatibility for environments
     without the SDK CLI installed.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, TYPE_CHECKING

# Try importing Claude Agent SDK
try:
    from claude_agent_sdk import (
        ClaudeSDKClient,
        ClaudeAgentOptions,
        query as sdk_query,
        tool,
        create_sdk_mcp_server,
        AssistantMessage,
        TextBlock,
        ToolUseBlock,
        ResultMessage,
        PermissionMode,
    )
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    # Provide stubs for type checking
    ClaudeSDKClient = None  # type: ignore
    ClaudeAgentOptions = None  # type: ignore
    sdk_query = None  # type: ignore
    tool = None  # type: ignore
    create_sdk_mcp_server = None  # type: ignore
    AssistantMessage = None  # type: ignore
    TextBlock = None  # type: ignore
    ToolUseBlock = None  # type: ignore
    ResultMessage = None  # type: ignore
    PermissionMode = None  # type: ignore

# Fallback to anthropic Messages API
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None  # type: ignore
    ANTHROPIC_AVAILABLE = False

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
    Role: Provides SDK-native execution with fallback to anthropic Messages API.
    Called from: A2UIAgent in agent_v2.py for skill selection and tool execution.
    Why: The Claude Agent SDK provides richer agentic capabilities (skills, hooks, 
         permissions) but requires the Claude Code CLI. This wrapper enables SDK 
         usage when available while falling back gracefully.
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
        self._anthropic_client: Optional[Any] = None
        self._mcp_server: Optional[Any] = None
        self._initialized = False

    @property
    def is_sdk_available(self) -> bool:
        """Check if Claude Agent SDK is available."""
        return SDK_AVAILABLE

    @property
    def is_anthropic_available(self) -> bool:
        """Check if anthropic fallback is available."""
        return ANTHROPIC_AVAILABLE

    def _ensure_anthropic_client(self) -> Any:
        """Lazily initialize anthropic client for fallback."""
        if self._anthropic_client is None:
            if not ANTHROPIC_AVAILABLE:
                raise RuntimeError("Neither claude-agent-sdk nor anthropic package available")
            self._anthropic_client = anthropic.Anthropic(api_key=self.api_key)
        return self._anthropic_client

    async def initialize(
        self,
        system_prompt: Optional[str] = None,
        allowed_tools: Optional[List[str]] = None,
        mcp_tools: Optional[List[Any]] = None,
        use_sdk: bool = True,
    ) -> bool:
        """
        Initialize the SDK client or fallback.
        
        Args:
            system_prompt: System prompt for the agent.
            allowed_tools: List of allowed tool names.
            mcp_tools: List of MCP tools (created with @tool decorator).
            use_sdk: Whether to prefer SDK over fallback.
            
        Returns:
            True if SDK was initialized, False if using fallback.
        """
        if self._initialized:
            return self._sdk_client is not None

        if use_sdk:
            if not SDK_AVAILABLE:
                raise RuntimeError("Claude Agent SDK not available; install claude-agent-sdk.")
            mcp_servers = {}
            if mcp_tools:
                self._mcp_server = create_sdk_mcp_server(
                    name="a2ui_tools",
                    version="1.0.0",
                    tools=mcp_tools,
                )
                mcp_servers["a2ui"] = self._mcp_server

            options = ClaudeAgentOptions(
                system_prompt=system_prompt,
                allowed_tools=allowed_tools or [],
                mcp_servers=mcp_servers,
                permission_mode="default",
                setting_sources=["user", "project"],
                cwd=str(self.cwd),
            )

            self._sdk_client = ClaudeSDKClient(options=options)
            self._initialized = True
            logger.info("Claude Agent SDK initialized successfully")
            return True

        # Explicit fallback path (only when use_sdk is False)
        self._ensure_anthropic_client()
        self._initialized = True
        logger.info("Using anthropic Messages API (fallback path explicitly requested)")
        return False

    async def query(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> SDKResponse:
        """
        Execute a query using SDK or fallback.
        
        Method: query
        Role: Unified interface for executing Claude queries.
        Called from: A2UIAgent.select_skill, A2UIAgent._execute_narrative
        Why: Abstracts away SDK vs Messages API differences.
        
        Args:
            prompt: User prompt to send.
            system_prompt: Optional system prompt (used for fallback).
            tools: Optional list of tool definitions (used for fallback).
            tool_choice: Optional tool choice config (used for fallback).
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
            
        Returns:
            SDKResponse with content, tool calls, and completion status.
        """
        if self._sdk_client and SDK_AVAILABLE:
            return await self._query_sdk(prompt)
        else:
            return await self._query_fallback(
                prompt=prompt,
                system_prompt=system_prompt,
                tools=tools,
                tool_choice=tool_choice,
                max_tokens=max_tokens,
                temperature=temperature,
            )

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

    async def _query_fallback(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> SDKResponse:
        """Execute query using anthropic Messages API (fallback)."""
        client = self._ensure_anthropic_client()

        try:
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            
            if system_prompt:
                kwargs["system"] = system_prompt
            if tools:
                kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice

            response = client.messages.create(**kwargs)

            content_parts = []
            tool_calls = []

            for block in getattr(response, "content", []):
                block_type = getattr(block, "type", None)
                if block_type == "text":
                    content_parts.append(getattr(block, "text", ""))
                elif block_type == "tool_use":
                    tool_calls.append(SDKToolCall(
                        id=getattr(block, "id", ""),
                        name=getattr(block, "name", ""),
                        input=getattr(block, "input", {}),
                    ))

            return SDKResponse(
                content="".join(content_parts),
                tool_calls=tool_calls,
                is_complete=True,
            )

        except Exception as e:
            logger.error(f"Fallback query failed: {e}")
            return SDKResponse(error=str(e), is_complete=True)

    async def stream_query(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> AsyncIterator[SDKResponse]:
        """
        Stream responses from SDK or fallback.
        
        Method: stream_query
        Role: Streaming interface for real-time response handling.
        Called from: A2UIAgent for streaming skill execution.
        Why: Enables progressive UI updates during long-running queries.
        
        Yields:
            SDKResponse chunks as they arrive.
        """
        if self._sdk_client and SDK_AVAILABLE:
            async for chunk in self._stream_sdk(prompt):
                yield chunk
        else:
            # Fallback doesn't support true streaming, yield single response
            response = await self._query_fallback(prompt, system_prompt)
            yield response

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
        self._anthropic_client = None
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
    Called from: A2UIAgent, routes/dashboard.py
    Why: Avoids reinitializing SDK client on every request.
    """
    global _sdk_wrapper
    if _sdk_wrapper is None:
        _sdk_wrapper = A2UISDKWrapper(cwd=cwd, model=model, api_key=api_key)
    return _sdk_wrapper


__all__ = [
    "SDK_AVAILABLE",
    "ANTHROPIC_AVAILABLE",
    "SDKToolCall",
    "SDKResponse",
    "SDKMessage",
    "A2UISDKWrapper",
    "get_sdk_wrapper",
]
