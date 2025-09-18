from __future__ import annotations
import logging
import os
import sys
import time
from typing import Dict, Any, List, Optional, AsyncGenerator, Type, TypeVar
from pydantic import BaseModel
from openai import AsyncOpenAI

# Add parent directory to path for unified client import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unified_responses_client import get_unified_client
from analytics_memory.openai_client import get_openai_client

logger = logging.getLogger(__name__)

# Debug configuration
SUPERVISOR_DEBUG = os.getenv('SUPERVISOR_DEBUG', 'false').lower() == 'true'

# Reasoning effort configuration
_ALLOWED_REASONING = {"low", "medium", "high"}
_SUPERVISOR_REASONING_ENV = os.getenv('SUPERVISOR_REASONING_EFFORT', 'medium').lower() if os.getenv('SUPERVISOR_REASONING_EFFORT') else 'medium'
if _SUPERVISOR_REASONING_ENV not in _ALLOWED_REASONING:
    logger.warning('Invalid SUPERVISOR_REASONING_EFFORT=%s, falling back to medium', _SUPERVISOR_REASONING_ENV)
    _SUPERVISOR_REASONING_ENV = 'medium'
SUPERVISOR_REASONING_EFFORT = _SUPERVISOR_REASONING_ENV

T = TypeVar('T', bound=BaseModel)


class SupervisorResponsesClient:
    """Specialized client for OpenAI Responses API with Claude Code-style supervision."""

    def __init__(self):
        # Use unified client for Responses API
        self.unified_client = get_unified_client()

        # Keep base client for direct API access
        self.base_client = get_openai_client()
        if not self.base_client and not self.unified_client:
            raise ValueError("OpenAI client not available - check API key")

        # Direct async client for responses API (fallback path)
        self.async_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

    def _get_model_name(self, model: Optional[str] = None) -> str:
        if model:
            return model
        return "gpt-5-mini-2025-08-07"  # Default supervisor reasoning model

    def _format_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted: List[Dict[str, Any]] = []
        for message in messages or []:
            role = message.get("role")
            raw_content = message.get("content")
            if isinstance(raw_content, list):
                segments: List[Dict[str, Any]] = []
                for item in raw_content:
                    if isinstance(item, dict) and item.get("type"):
                        segment = dict(item)
                        if segment.get("type") == "text" and "text" not in segment and "value" in segment:
                            segment["text"] = segment.pop("value")
                        # Convert legacy "text" type to "input_text" for Responses API
                        if segment.get("type") == "text":
                            segment["type"] = "input_text"
                        segments.append(segment)
                    else:
                        segments.append({"type": "input_text", "text": str(item)})
            else:
                text_value = "" if raw_content is None else str(raw_content)
                segments = [{"type": "input_text", "text": text_value}]

            formatted.append({"role": role, "content": segments})
        return formatted

    def _apply_reasoning(self, params: Dict[str, Any], effort: Optional[str]) -> None:
        if effort:
            params["reasoning"] = {"effort": effort}

    def _extract_output_text(self, response: Any) -> str:
        if response is None:
            return ""
        text = getattr(response, "output_text", None)
        if text:
            return text
        if hasattr(response, "model_dump"):
            try:
                data = response.model_dump()
            except Exception:
                data = None
        else:
            data = None
        if not data:
            content_attr = getattr(response, "content", None)
            return content_attr if isinstance(content_attr, str) else ""
        blocks = data.get("output") or []
        parts: List[str] = []
        for block in blocks:
            block_data = block if isinstance(block, dict) else getattr(block, "model_dump", lambda: {})()
            for segment in block_data.get("content", []) or []:
                segment_dict = segment if isinstance(segment, dict) else getattr(segment, "model_dump", lambda: {})()
                if segment_dict.get("type") in ("text", "output_text"):
                    text_value = segment_dict.get("text") or segment_dict.get("value")
                    if text_value:
                        parts.append(text_value)
        return "".join(parts)

    def _extract_parsed_model(self, response: Any) -> Any:
        if response is None:
            return None

        parsed_attr = getattr(response, 'parsed', None)
        if parsed_attr is not None:
            return parsed_attr

        output_items = getattr(response, 'output', None) or []
        for item in output_items:
            contents = getattr(item, 'content', None) or []
            for content in contents:
                parsed_value = getattr(content, 'parsed', None)
                if parsed_value is not None:
                    return parsed_value

        raise ValueError('Parsed content not found in Responses payload')

    async def planning_turn(
        self,
        messages: List[Dict[str, Any]],
        response_format: Type[T],
        session_id: Optional[str] = None,
        reasoning_effort: str = SUPERVISOR_REASONING_EFFORT
    ) -> T:
        planning_start = time.time()
        logger.info(f"[SUPERVISOR_CLIENT] Starting planning turn for session {session_id or 'no-session'}")
        logger.info(f"[SUPERVISOR_CLIENT] Model: {self._get_model_name()}, reasoning effort: {reasoning_effort}")
        logger.info(f"[SUPERVISOR_CLIENT] Message count: {len(messages)}, response format: {response_format.__name__}")

        if SUPERVISOR_DEBUG:
            total_chars = sum(len(str(m)) for m in messages)
            logger.debug(f"[SUPERVISOR_CLIENT] Total message chars: {total_chars}")

        try:
            if self.unified_client:
                api_start = time.time()
                logger.info(f"[SUPERVISOR_CLIENT] Calling unified client for session {session_id or 'no-session'}")

                result, response_id = await self.unified_client.create_structured(
                    response_model=response_format,
                    messages=messages,
                    reasoning_effort=reasoning_effort,
                    session_id=session_id,
                    model=self._get_model_name()
                )

                api_duration = time.time() - api_start
                total_duration = time.time() - planning_start
                logger.info(f"[SUPERVISOR_CLIENT] Unified client call completed in {api_duration:.2f}s, total: {total_duration:.2f}s for session {session_id or 'no-session'}")
                logger.info(f"[SUPERVISOR_CLIENT] Response ID: {response_id}")

                return result

            if not self.async_client:
                raise RuntimeError("Async OpenAI client unavailable")

            params: Dict[str, Any] = {
                "model": self._get_model_name(),
                "input": self._format_messages(messages),
                "text_format": response_format,
            }
            self._apply_reasoning(params, reasoning_effort)
            response = await self.async_client.responses.parse(**params)
            return self._extract_parsed_model(response)

        except Exception as exc:
            total_duration = time.time() - planning_start
            logger.error(f"[SUPERVISOR_CLIENT] Planning turn failed after {total_duration:.2f}s for session {session_id or 'no-session'}: {exc}")
            logger.error(f"[SUPERVISOR_CLIENT] Error type: {type(exc).__name__}")

            if SUPERVISOR_DEBUG:
                logger.debug(f"[SUPERVISOR_CLIENT] Full error details: {repr(exc)}")

            raise

    async def tool_calling_turn(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        tool_choice: str = "auto",
        session_id: Optional[str] = None,
        reasoning_effort: str = "medium"
    ) -> Dict[str, Any]:
        tool_call_start = time.time()
        logger.info(f"[SUPERVISOR_CLIENT] Starting tool calling turn for session {session_id or 'no-session'}")
        logger.info(f"[SUPERVISOR_CLIENT] Model: {self._get_model_name()}, reasoning effort: {reasoning_effort}")
        logger.info(f"[SUPERVISOR_CLIENT] Tool choice: {tool_choice}, available tools: {len(tools)}")

        if SUPERVISOR_DEBUG:
            tool_names = [tool.get('function', {}).get('name', 'unknown') for tool in tools]
            logger.debug(f"[SUPERVISOR_CLIENT] Tool names: {tool_names}")

        try:
            if self.unified_client:
                api_start = time.time()
                logger.info(f"[SUPERVISOR_CLIENT] Calling unified client for tool calling for session {session_id or 'no-session'}")

                response = await self.unified_client.tool_calling_turn(
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    reasoning_effort=reasoning_effort,
                    session_id=session_id,
                    model=self._get_model_name()
                )

                api_duration = time.time() - api_start
                total_duration = time.time() - tool_call_start
                tool_calls_count = len(response.tool_calls) if hasattr(response, 'tool_calls') and response.tool_calls else 0
                logger.info(f"[SUPERVISOR_CLIENT] Tool calling completed in {api_duration:.2f}s, total: {total_duration:.2f}s for session {session_id or 'no-session'}")
                logger.info(f"[SUPERVISOR_CLIENT] Response contains {tool_calls_count} tool calls")

                return {"content": response.content, "tool_calls": response.tool_calls}

            if not self.async_client:
                raise RuntimeError("Async OpenAI client unavailable")

            params: Dict[str, Any] = {
                "model": self._get_model_name(),
                "input": self._format_messages(messages),
                "tools": tools,
                "tool_choice": tool_choice,
            }
            self._apply_reasoning(params, reasoning_effort)
            response = await self.async_client.responses.create(**params)
            return {
                "content": self._extract_output_text(response),
                "tool_calls": getattr(response, "tool_calls", [])
            }

        except Exception as exc:
            total_duration = time.time() - tool_call_start
            logger.error(f"[SUPERVISOR_CLIENT] Tool calling turn failed after {total_duration:.2f}s for session {session_id or 'no-session'}: {exc}")
            logger.error(f"[SUPERVISOR_CLIENT] Error type: {type(exc).__name__}")

            if SUPERVISOR_DEBUG:
                logger.debug(f"[SUPERVISOR_CLIENT] Full error details: {repr(exc)}")

            raise

    async def finalization_turn(
        self,
        messages: List[Dict[str, Any]],
        response_format: Optional[Type[T]] = None,
        session_id: Optional[str] = None,
        reasoning_effort: str = "low"
    ) -> T:
        try:
            if self.unified_client and response_format:
                result, _ = await self.unified_client.create_structured(
                    response_model=response_format,
                    messages=messages,
                    reasoning_effort=reasoning_effort,
                    session_id=session_id,
                    model=self._get_model_name()
                )
                return result
            if self.unified_client:
                content, _ = await self.unified_client.simple_completion(
                    messages=messages,
                    reasoning_effort=reasoning_effort,
                    session_id=session_id,
                    model=self._get_model_name()
                )
                return content

            if not self.async_client:
                raise RuntimeError("Async OpenAI client unavailable")

            params: Dict[str, Any] = {
                "model": self._get_model_name(),
                "input": self._format_messages(messages),
            }
            self._apply_reasoning(params, reasoning_effort)

            if response_format:
                params['text_format'] = response_format
                response = await self.async_client.responses.parse(**params)
                return self._extract_parsed_model(response)

            response = await self.async_client.responses.create(**params)
            return self._extract_output_text(response)

        except Exception as exc:
            logger.error("Finalization turn failed: %s", exc)
            raise

    async def stream_analysis(
        self,
        messages: List[Dict[str, Any]],
        session_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        stream_start = time.time()
        logger.info(f"[SUPERVISOR_CLIENT] Starting analysis streaming for session {session_id or 'no-session'}")
        logger.info(f"[SUPERVISOR_CLIENT] Message count: {len(messages)}")

        chunk_count = 0
        total_chars = 0

        try:
            if self.unified_client:
                logger.info(f"[SUPERVISOR_CLIENT] Starting unified client stream for session {session_id or 'no-session'}")

                async for delta in self.unified_client.stream_response(
                    messages=messages,
                    reasoning_effort="low",
                    session_id=session_id,
                    model=self._get_model_name()
                ):
                    if delta.content:
                        chunk_count += 1
                        total_chars += len(delta.content)
                        if chunk_count % 10 == 0:  # Log every 10th chunk
                            logger.debug(f"[SUPERVISOR_CLIENT] Streamed {chunk_count} chunks, {total_chars} chars for session {session_id or 'no-session'}")
                        yield delta.content

                stream_duration = time.time() - stream_start
                logger.info(f"[SUPERVISOR_CLIENT] Analysis streaming completed in {stream_duration:.2f}s, {chunk_count} chunks, {total_chars} chars for session {session_id or 'no-session'}")
                return

            if not self.async_client:
                raise RuntimeError("Async OpenAI client unavailable")

            params: Dict[str, Any] = {
                "model": self._get_model_name(),
                "input": self._format_messages(messages),
            }
            async with self.async_client.responses.stream(**params) as stream:
                async for event in stream:
                    if getattr(event, "type", None) == "response.output_text.delta":
                        delta_text = getattr(event, "delta", None)
                        if delta_text:
                            yield delta_text
        except Exception as exc:
            stream_duration = time.time() - stream_start
            logger.error(f"[SUPERVISOR_CLIENT] Analysis streaming failed after {stream_duration:.2f}s for session {session_id or 'no-session'}: {exc}")
            logger.error(f"[SUPERVISOR_CLIENT] Error type: {type(exc).__name__}, chunks processed: {chunk_count}")

            if SUPERVISOR_DEBUG:
                logger.debug(f"[SUPERVISOR_CLIENT] Full error details: {repr(exc)}")

            yield f"Analysis error: {exc}"


# Global supervisor client instance
_supervisor_client: Optional[SupervisorResponsesClient] = None

def get_supervisor_client() -> SupervisorResponsesClient:
    """Get or create global supervisor client instance"""
    global _supervisor_client
    if _supervisor_client is None:
        try:
            _supervisor_client = SupervisorResponsesClient()
        except ValueError:
            raise ValueError("OpenAI API key required for supervisor functionality")
    return _supervisor_client
