"""
Unified OpenAI Responses API client for the entire application.

This client provides a single interface for all OpenAI API interactions,
using the new Responses API with reasoning support for o1/o3 models.
"""

from __future__ import annotations
import os
import logging
from typing import Any, Dict, List, Optional, AsyncGenerator, TypeVar, Type, Tuple
from pydantic import BaseModel
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class ResponseDelta:
    """Represents a streaming delta from the Responses API"""

    def __init__(self, content: Optional[str] = None, reasoning: Optional[str] = None, tool_calls: Optional[List[Dict[str, Any]]] = None):
        self.content = content
        self.reasoning = reasoning
        self.tool_calls = tool_calls or []


class ResponseMessage:
    """Represents a complete response message"""

    def __init__(self, content: Optional[str] = None, tool_calls: Optional[List[Dict[str, Any]]] = None, response_id: Optional[str] = None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.response_id = response_id


class UnifiedResponsesClient:
    """Central client for OpenAI Responses API with reasoning support."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not found")

        # Initialize async client for Responses API
        self.client = AsyncOpenAI(api_key=self.api_key)

        # Session management
        self.previous_response_id: Optional[str] = None
        self.session_contexts: Dict[str, str] = {}  # session_id -> previous_response_id

    def _get_model_name(self, model: Optional[str] = None) -> str:
        if model:
            return model

        env_model = os.getenv("OPENAI_MODEL")
        if env_model:
            return env_model

        # Default to GPT-5 mini as documented in CLAUDE.md
        return "gpt-5-mini-2025-08-07"

    def _get_previous_response_id(self, session_id: Optional[str] = None) -> Optional[str]:
        if session_id:
            return self.session_contexts.get(session_id)
        return self.previous_response_id

    def _set_previous_response_id(self, response_id: Optional[str], session_id: Optional[str] = None) -> None:
        if not response_id:
            return
        if session_id:
            self.session_contexts[session_id] = response_id
        else:
            self.previous_response_id = response_id

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

    def _apply_reasoning(self, params: Dict[str, Any], reasoning_effort: Optional[str]) -> None:
        if reasoning_effort:
            params["reasoning"] = {"effort": reasoning_effort}

    def _as_dict(self, obj: Any) -> Optional[Dict[str, Any]]:
        if obj is None:
            return None
        if isinstance(obj, dict):
            return obj
        for attr in ("model_dump", "to_dict"):
            if hasattr(obj, attr):
                try:
                    return getattr(obj, attr)()
                except Exception:
                    continue
        return None

    def _extract_output_text(self, response: Any) -> str:
        if response is None:
            return ""
        text = getattr(response, "output_text", None)
        if text:
            return text

        data = self._as_dict(response)
        if not data:
            content_attr = getattr(response, "content", None)
            return content_attr if isinstance(content_attr, str) else ""

        parts: List[str] = []
        output_blocks = data.get("output") or []
        for block in output_blocks:
            block_dict = block if isinstance(block, dict) else self._as_dict(block) or {}
            for segment in block_dict.get("content", []) or []:
                segment_dict = segment if isinstance(segment, dict) else self._as_dict(segment) or {}
                segment_type = segment_dict.get("type")
                if segment_type in ("output_text", "text"):
                    text_value = segment_dict.get("text") or segment_dict.get("value")
                    if text_value:
                        parts.append(text_value)
        if parts:
            return "".join(parts)

        content_attr = data.get("content")
        if isinstance(content_attr, str):
            return content_attr
        return ""

    def _extract_tool_calls(self, response: Any) -> List[Dict[str, Any]]:
        calls: List[Dict[str, Any]] = []
        if response is None:
            return calls

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


        attr_calls = getattr(response, "tool_calls", None)
        if attr_calls:
            for call in attr_calls:
                call_dict = call if isinstance(call, dict) else self._as_dict(call)
                if call_dict:
                    calls.append(call_dict)

        data = self._as_dict(response)
        if not data:
            return calls

        if isinstance(data.get("tool_calls"), list):
            for call in data["tool_calls"]:
                call_dict = call if isinstance(call, dict) else self._as_dict(call)
                if call_dict:
                    calls.append(call_dict)

        for block in data.get("output", []) or []:
            block_dict = block if isinstance(block, dict) else self._as_dict(block) or {}
            for segment in block_dict.get("content", []) or []:
                segment_dict = segment if isinstance(segment, dict) else self._as_dict(segment) or {}
                if segment_dict.get("type") == "tool_calls":
                    for call in segment_dict.get("tool_calls", []) or []:
                        call_dict = call if isinstance(call, dict) else self._as_dict(call)
                        if call_dict:
                            calls.append(call_dict)
        return calls

    def _inject_context(self, params: Dict[str, Any], session_id: Optional[str]) -> None:
        prev_id = self._get_previous_response_id(session_id)
        if prev_id:
            params["previous_response_id"] = prev_id

    async def create_structured(
        self,
        response_model: Type[T],
        messages: List[Dict[str, Any]],
        reasoning_effort: str = "medium",
        session_id: Optional[str] = None,
        model: Optional[str] = None
    ) -> Tuple[T, Optional[str]]:
        params: Dict[str, Any] = {
            "model": self._get_model_name(model),
            "input": self._format_messages(messages),
            "text_format": response_model,
        }
        self._apply_reasoning(params, reasoning_effort)
        self._inject_context(params, session_id)

        try:
            response = await self.client.responses.parse(**params)
            response_id = getattr(response, "id", None)
            self._set_previous_response_id(response_id, session_id)
            parsed_model = self._extract_parsed_model(response)
            if parsed_model is None:
                raise ValueError('Responses API did not return parsed content')
            return parsed_model, response_id
        except Exception as exc:
            logger.error("Responses API structured request failed: %s", exc)
            raise

    async def tool_calling_turn(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        tool_choice: str = "auto",
        reasoning_effort: str = "medium",
        session_id: Optional[str] = None,
        model: Optional[str] = None
    ) -> ResponseMessage:
        params: Dict[str, Any] = {
            "model": self._get_model_name(model),
            "input": self._format_messages(messages),
            "tools": tools,
            "tool_choice": tool_choice,
        }
        self._apply_reasoning(params, reasoning_effort)
        self._inject_context(params, session_id)

        try:
            response = await self.client.responses.create(**params)
            response_id = getattr(response, "id", None)
            self._set_previous_response_id(response_id, session_id)

            content = self._extract_output_text(response)
            tool_calls = self._extract_tool_calls(response)
            return ResponseMessage(content=content, tool_calls=tool_calls, response_id=response_id)
        except Exception as exc:
            logger.error("Responses API tool calling failed: %s", exc)
            raise

    async def stream_response(
        self,
        messages: List[Dict[str, Any]],
        reasoning_effort: str = "low",
        session_id: Optional[str] = None,
        model: Optional[str] = None
    ) -> AsyncGenerator[ResponseDelta, None]:
        params: Dict[str, Any] = {
            "model": self._get_model_name(model),
            "input": self._format_messages(messages),
        }
        self._apply_reasoning(params, reasoning_effort)
        self._inject_context(params, session_id)

        try:
            async with self.client.responses.stream(**params) as stream:
                async for event in stream:
                    event_type = getattr(event, "type", None)
                    if event_type == "response.output_text.delta":
                        delta_text = getattr(event, "delta", None)
                        if delta_text:
                            yield ResponseDelta(content=delta_text)
                    elif event_type == "response.reasoning.delta":
                        reasoning_delta = getattr(event, "delta", None)
                        if reasoning_delta:
                            yield ResponseDelta(reasoning=reasoning_delta)
                    elif event_type == "response.tool_call.delta":
                        event_dict = self._as_dict(event) or {}
                        tool_calls = event_dict.get("tool_calls") or []
                        if tool_calls:
                            yield ResponseDelta(tool_calls=tool_calls)
                    elif event_type == "response.error":
                        error_info = getattr(event, "error", None) or getattr(event, "message", None)
                        logger.error("Responses streaming error: %s", error_info)

                final_response = await stream.get_final_response()
                response_id = getattr(final_response, "id", None) if final_response else None
                self._set_previous_response_id(response_id, session_id)
        except Exception as exc:
            logger.error("Responses API streaming failed: %s", exc)
            raise

    async def simple_completion(
        self,
        messages: List[Dict[str, Any]],
        reasoning_effort: str = "low",
        session_id: Optional[str] = None,
        model: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        params: Dict[str, Any] = {
            "model": self._get_model_name(model),
            "input": self._format_messages(messages),
        }
        self._apply_reasoning(params, reasoning_effort)
        self._inject_context(params, session_id)

        try:
            response = await self.client.responses.create(**params)
            response_id = getattr(response, "id", None)
            self._set_previous_response_id(response_id, session_id)
            content = self._extract_output_text(response)
            return content, response_id
        except Exception as exc:
            logger.error("Responses API simple completion failed: %s", exc)
            raise


# Global client instance
_unified_client: Optional[UnifiedResponsesClient] = None

def get_unified_client() -> Optional[UnifiedResponsesClient]:
    """Get or create global unified client instance"""
    global _unified_client
    if _unified_client is None:
        try:
            _unified_client = UnifiedResponsesClient()
        except ValueError:
            return None
    return _unified_client
