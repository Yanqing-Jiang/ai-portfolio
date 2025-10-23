"""
Unified OpenAI Responses API Client (Foundation Layer)

This client provides a single, application-wide interface for all OpenAI API interactions,
using the new Responses API with reasoning support for GPT-5 and other reasoning models.

ARCHITECTURE ROLE:
┌─────────────────────────────────────────┐
│   Application Components (Supervisor,   │  ← All modules import this
│   Analytics Agent, RAG Service, etc.)   │     as their OpenAI foundation
└─────────────┬───────────────────────────┘
              ↓ all use
┌─────────────────────────────────────────┐
│      unified_responses_client.py        │  ← Central OpenAI API gateway
│   (Session mgmt, embeddings, responses) │     Single source of truth
└─────────────────────────────────────────┘

Key Features:
- Central OpenAI API access point for entire application
- Session management with response ID continuity
- Embeddings API support for vector search operations
- Message formatting standardization for Responses API
- Error handling and fallback mechanisms
- Thread-safe singleton pattern

Usage:
    client = get_unified_client()  # Global instance
    response = await client.create_response(messages, model="gpt-5-mini-2025-08-07")
    embeddings = await client.create_embeddings(["text to embed"])
"""

from __future__ import annotations
import copy
import os
import logging
import time
from typing import Any, Dict, List, Optional, AsyncGenerator, TypeVar, Type, Tuple
from types import SimpleNamespace
from pydantic import BaseModel
from openai import AsyncOpenAI
from analytics.core.telemetry import responses_call

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


def _should_require_property(prop_schema: Any) -> bool:
    if not isinstance(prop_schema, dict):
        return True
    schema_type = prop_schema.get("type")
    if schema_type == "object":
        nested_props = prop_schema.get("properties")
        if isinstance(nested_props, dict) and nested_props:
            return True
        # Dictionary-style objects (only additionalProperties) cannot be marked required.
        return False
    return True


def _normalize_schema_for_responses(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure every object schema declares a required list containing all properties and
    defaults additionalProperties to False, per Responses API contract.
    """

    def _visit(node: Dict[str, Any]) -> None:
        if not isinstance(node, dict):
            return

        if "default" in node:
            node.pop("default", None)

        properties = node.get("properties")
        if isinstance(properties, dict) and properties:
            required_fields: List[str] = []
            for prop_name, prop_schema in properties.items():
                if isinstance(prop_schema, dict):
                    prop_schema.pop("default", None)
                if _should_require_property(prop_schema):
                    required_fields.append(prop_name)
                if isinstance(prop_schema, dict):
                    _visit(prop_schema)
            node["required"] = required_fields
            node.setdefault("additionalProperties", False)

        for key in ("$defs", "definitions"):
            subdefs = node.get(key)
            if isinstance(subdefs, dict):
                for sub_schema in subdefs.values():
                    if isinstance(sub_schema, dict):
                        _visit(sub_schema)

        items = node.get("items")
        if isinstance(items, dict):
            _visit(items)
        elif isinstance(items, list):
            for entry in items:
                if isinstance(entry, dict):
                    _visit(entry)

        for key in ("anyOf", "allOf", "oneOf"):
            variants = node.get(key)
            if isinstance(variants, list):
                for variant in variants:
                    if isinstance(variant, dict):
                        _visit(variant)

        for key in ("if", "then", "else", "not"):
            conditional = node.get(key)
            if isinstance(conditional, dict):
                _visit(conditional)

        additional_props = node.get("additionalProperties")
        if isinstance(additional_props, dict):
            _visit(additional_props)

    normalized = copy.deepcopy(schema)
    _visit(normalized)
    return normalized


def _wrap_response_model(response_model: Type[T]) -> Type[T]:
    """
    Create a subclass that emits a Responses-compliant JSON schema.
    Re-wrapping is avoided by marking the class with a sentinel attribute.
    """
    if getattr(response_model, "__responses_schema_normalized__", False):
        return response_model

    class ResponsesModel(response_model):  # type: ignore[misc, valid-type]
        __responses_schema_normalized__ = True

        @classmethod
        def model_json_schema(cls, *args, **kwargs):
            schema = super().model_json_schema(*args, **kwargs)
            return _normalize_schema_for_responses(schema)

    ResponsesModel.__name__ = f"Responses{response_model.__name__}"
    ResponsesModel.__qualname__ = ResponsesModel.__name__
    ResponsesModel.__module__ = response_model.__module__
    return ResponsesModel  # type: ignore[return-value]

# Supervisor reasoning effort configuration (consolidated from responses_client)
_ALLOWED_REASONING = {"low", "medium", "high"}
_SUPERVISOR_REASONING_ENV = os.getenv('SUPERVISOR_REASONING_EFFORT', 'low').lower() if os.getenv('SUPERVISOR_REASONING_EFFORT') else 'low'
if _SUPERVISOR_REASONING_ENV not in _ALLOWED_REASONING:
    logger.warning('Invalid SUPERVISOR_REASONING_EFFORT=%s, falling back to low', _SUPERVISOR_REASONING_ENV)
    _SUPERVISOR_REASONING_ENV = 'low'
SUPERVISOR_REASONING_EFFORT = _SUPERVISOR_REASONING_ENV


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

    def _supports_reasoning(self, model: Optional[str]) -> bool:
        """Return True if the selected model supports the Responses reasoning parameter.

        Uses an overrideable env var OPENAI_REASONING_MODELS (comma-separated list),
        otherwise defaults to GPT-5 and other reasoning-capable models. This prevents API errors
        like 'reasoning.effort not supported with current model'.
        """
        override = os.getenv("OPENAI_REASONING_MODELS")
        if override:
            allowed = {m.strip() for m in override.split(',') if m.strip()}
            return model in allowed
        # Heuristic: allow models that start with 'gpt-5' (GPT-5 Mini and variants)
        # Keep legacy 'o' prefix support for backward compatibility
        # Avoid sending reasoning to other gpt-* or non-reasoning models.
        return bool(model and (model.lower().startswith('o') or model.lower().startswith('gpt-5')))

    def _apply_reasoning(self, params: Dict[str, Any], reasoning_effort: Optional[str]) -> None:
        model_name = params.get("model") if isinstance(params, dict) else None
        if reasoning_effort and self._supports_reasoning(model_name):
            params["reasoning"] = {"effort": reasoning_effort}
        # else: do not include reasoning for unsupported models

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


    def _extract_tool_calls(self, response: Any) -> List[Any]:
        calls: List[Any] = []
        if response is None:
            return calls

        seen_ids = set()

        def _normalize(call_obj: Any):
            if call_obj is None:
                return None
            if hasattr(call_obj, 'function') and getattr(call_obj.function, 'name', None):
                return call_obj

            call_dict = call_obj if isinstance(call_obj, dict) else self._as_dict(call_obj) or {}
            if not call_dict:
                return None

            function_payload = call_dict.get('function')
            function_dict = function_payload if isinstance(function_payload, dict) else self._as_dict(function_payload) or {}

            arguments = function_dict.get('arguments')
            if arguments is None and 'args' in function_dict:
                arguments = function_dict.get('args')
            arguments = '' if arguments is None else str(arguments)

            function_obj = function_payload if hasattr(function_payload, 'name') else SimpleNamespace(
                name=function_dict.get('name'),
                arguments=arguments
            )

            return SimpleNamespace(
                id=call_dict.get('id'),
                type=call_dict.get('type', 'function'),
                function=function_obj
            )

        def _append(call_obj: Any):
            normalized = _normalize(call_obj)
            if not normalized:
                return
            call_id = getattr(normalized, 'id', None)
            if call_id and call_id in seen_ids:
                return
            if call_id:
                seen_ids.add(call_id)
            calls.append(normalized)

        attr_calls = getattr(response, 'tool_calls', None)
        if attr_calls:
            for call in attr_calls:
                _append(call)

        data = self._as_dict(response)
        if not data:
            return calls

        for call in data.get('tool_calls') or []:
            _append(call)

        required_action = data.get('required_action') or {}
        submit = required_action.get('submit_tool_outputs') or {}
        for call in submit.get('tool_calls', []) or []:
            _append(call)

        for block in data.get('output', []) or []:
            block_dict = block if isinstance(block, dict) else self._as_dict(block) or {}
            for segment in block_dict.get('content', []) or []:
                segment_dict = segment if isinstance(segment, dict) else self._as_dict(segment) or {}
                if segment_dict.get('type') == 'tool_calls':
                    for call in segment_dict.get('tool_calls', []) or []:
                        _append(call)

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
        wrapped_model = _wrap_response_model(response_model)
        # Force schema build so any validation issues surface before the request.
        _ = wrapped_model.model_json_schema()
        model_name = self._get_model_name(model)
        formatted_messages = self._format_messages(messages)
        params: Dict[str, Any] = {
            "model": model_name,
            "input": formatted_messages,
            "text_format": wrapped_model,
        }
        self._apply_reasoning(params, reasoning_effort)
        self._inject_context(params, session_id)

        call_start = time.time()

        try:
            response = await self.client.responses.parse(**params)
            response_id = getattr(response, "id", None)
            self._set_previous_response_id(response_id, session_id)
            parsed_model = self._extract_parsed_model(response)
            if parsed_model is None:
                raise ValueError('Responses API did not return parsed content')
            elapsed_ms = int((time.time() - call_start) * 1000)
            responses_call(
                call_type="create_structured",
                model=params.get("model"),
                reasoning_effort=reasoning_effort,
                duration_ms=elapsed_ms,
                status="success",
                session_id=session_id,
                metadata={"response_id": response_id, "response_model": getattr(response_model, '__name__', str(response_model))},
            )
            return parsed_model, response_id
        except Exception as exc:
            elapsed_ms = int((time.time() - call_start) * 1000)
            responses_call(
                call_type="create_structured",
                model=params.get("model"),
                reasoning_effort=reasoning_effort,
                duration_ms=elapsed_ms,
                status="error",
                session_id=session_id,
                error=str(exc),
            )
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

        call_start = time.time()

        try:
            response = await self.client.responses.create(**params)
            response_id = getattr(response, "id", None)
            self._set_previous_response_id(response_id, session_id)

            content = self._extract_output_text(response)
            tool_calls = self._extract_tool_calls(response)
            elapsed_ms = int((time.time() - call_start) * 1000)
            responses_call(
                call_type="tool_calling_turn",
                model=params.get("model"),
                reasoning_effort=reasoning_effort,
                duration_ms=elapsed_ms,
                status="success",
                session_id=session_id,
                metadata={"response_id": response_id, "tool_call_count": len(tool_calls or [])},
            )
            return ResponseMessage(content=content, tool_calls=tool_calls, response_id=response_id)
        except Exception as exc:
            elapsed_ms = int((time.time() - call_start) * 1000)
            responses_call(
                call_type="tool_calling_turn",
                model=params.get("model"),
                reasoning_effort=reasoning_effort,
                duration_ms=elapsed_ms,
                status="error",
                session_id=session_id,
                error=str(exc),
            )
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

        call_start = time.time()
        delta_count = 0

        try:
            async with self.client.responses.stream(**params) as stream:
                async for event in stream:
                    event_type = getattr(event, "type", None)
                    if event_type == "response.output_text.delta":
                        delta_text = getattr(event, "delta", None)
                        if delta_text:
                            delta_count += 1
                            yield ResponseDelta(content=delta_text)
                    elif event_type == "response.reasoning.delta":
                        reasoning_delta = getattr(event, "delta", None)
                        if reasoning_delta:
                            delta_count += 1
                            yield ResponseDelta(reasoning=reasoning_delta)
                    elif event_type == "response.tool_call.delta":
                        event_dict = self._as_dict(event) or {}
                        tool_calls = event_dict.get("tool_calls") or []
                        if tool_calls:
                            delta_count += 1
                            yield ResponseDelta(tool_calls=tool_calls)
                    elif event_type == "response.error":
                        error_info = getattr(event, "error", None) or getattr(event, "message", None)
                        logger.error("Responses streaming error: %s", error_info)

                final_response = await stream.get_final_response()
                response_id = getattr(final_response, "id", None) if final_response else None
                self._set_previous_response_id(response_id, session_id)
                elapsed_ms = int((time.time() - call_start) * 1000)
                responses_call(
                    call_type="stream_response",
                    model=params.get("model"),
                    reasoning_effort=reasoning_effort,
                    duration_ms=elapsed_ms,
                    status="success",
                    session_id=session_id,
                    metadata={"response_id": response_id, "delta_count": delta_count},
                )
        except Exception as exc:
            elapsed_ms = int((time.time() - call_start) * 1000)
            responses_call(
                call_type="stream_response",
                model=params.get("model"),
                reasoning_effort=reasoning_effort,
                duration_ms=elapsed_ms,
                status="error",
                session_id=session_id,
                error=str(exc),
            )
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

        call_start = time.time()

        try:
            response = await self.client.responses.create(**params)
            response_id = getattr(response, "id", None)
            self._set_previous_response_id(response_id, session_id)
            content = self._extract_output_text(response)
            elapsed_ms = int((time.time() - call_start) * 1000)
            responses_call(
                call_type="simple_completion",
                model=params.get("model"),
                reasoning_effort=reasoning_effort,
                duration_ms=elapsed_ms,
                status="success",
                session_id=session_id,
                metadata={"response_id": response_id},
            )
            return content, response_id
        except Exception as exc:
            elapsed_ms = int((time.time() - call_start) * 1000)
            responses_call(
                call_type="simple_completion",
                model=params.get("model"),
                reasoning_effort=reasoning_effort,
                duration_ms=elapsed_ms,
                status="error",
                session_id=session_id,
                error=str(exc),
            )
            logger.error("Responses API simple completion failed: %s", exc)
            raise

    async def create_embeddings(
        self,
        texts: List[str],
        model: str = "text-embedding-3-small"
    ) -> List[List[float]]:
        """Create embeddings for text using OpenAI embeddings API"""
        call_start = time.time()
        try:
            response = await self.client.embeddings.create(
                input=texts,
                model=model
            )
            elapsed_ms = int((time.time() - call_start) * 1000)
            responses_call(
                call_type="create_embeddings",
                model=model,
                reasoning_effort=None,
                duration_ms=elapsed_ms,
                status="success",
                session_id=None,
                metadata={"vector_count": len(response.data)},
            )
            return [embedding.embedding for embedding in response.data]
        except Exception as exc:
            elapsed_ms = int((time.time() - call_start) * 1000)
            responses_call(
                call_type="create_embeddings",
                model=model,
                reasoning_effort=None,
                duration_ms=elapsed_ms,
                status="error",
                session_id=None,
                error=str(exc),
            )
            logger.error("Embeddings API request failed: %s", exc)
            raise

    def create_embeddings_sync(
        self,
        texts: List[str],
        model: str = "text-embedding-3-small"
    ) -> List[List[float]]:
        """Sync wrapper for embeddings using thread pool"""
        import asyncio
        import concurrent.futures

        async def _create_embeddings():
            return await self.create_embeddings(texts, model)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, _create_embeddings())
            return future.result()

    # =============== SUPERVISOR-SPECIFIC METHODS ===============

    async def finalization_turn(
        self,
        messages: List[Dict[str, Any]],
        response_format: Optional[Type[T]] = None,
        session_id: Optional[str] = None,
        reasoning_effort: str = "low",
        model: Optional[str] = None
    ) -> T:
        """Supervisor-specific finalization turn with structured output"""
        if response_format:
            result, _ = await self.create_structured(
                response_model=response_format,
                messages=messages,
                reasoning_effort=reasoning_effort,
                session_id=session_id,
                model=model or self._get_model_name()
            )
            return result
        else:
            content, _ = await self.simple_completion(
                messages=messages,
                reasoning_effort=reasoning_effort,
                session_id=session_id,
                model=model or self._get_model_name()
            )
            return content

    async def stream_analysis(
        self,
        messages: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        reasoning_effort: str = "low",
        model: Optional[str] = None
    ) -> AsyncGenerator[ResponseDelta, None]:
        """Supervisor-specific streaming analysis"""
        async for delta in self.stream_response(
            messages=messages,
            reasoning_effort=reasoning_effort,
            session_id=session_id,
            model=model or self._get_model_name()
        ):
            yield delta


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
