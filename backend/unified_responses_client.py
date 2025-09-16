"""
Unified OpenAI Responses API client for the entire application.

This client provides a single interface for all OpenAI API interactions,
using the new Responses API with reasoning support for o1/o3 models.
"""

from __future__ import annotations
import os
import json
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator, TypeVar, Type, Tuple, Union
from pydantic import BaseModel
import openai
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class ResponseDelta:
    """Represents a streaming delta from the Responses API"""
    def __init__(self, content: str = None, reasoning: str = None, tool_calls: List = None):
        self.content = content
        self.reasoning = reasoning
        self.tool_calls = tool_calls or []

class ResponseMessage:
    """Represents a complete response message"""
    def __init__(self, content: str = None, tool_calls: List = None, response_id: str = None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.response_id = response_id

class UnifiedResponsesClient:
    """
    Central client for OpenAI Responses API with reasoning support.

    This client provides a unified interface for all OpenAI interactions
    in the application using the new Responses API for o1/o3 models.
    """

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
        """Get model name with fallback logic for o1/o3 models"""
        if model:
            return model

        # Check for environment override
        env_model = os.getenv("OPENAI_MODEL")
        if env_model:
            return env_model

        # Use GPT-5 mini for Responses API with reasoning
        return "gpt-5-mini-2025-08-07"

    def _get_previous_response_id(self, session_id: Optional[str] = None) -> Optional[str]:
        """Get previous response ID for context threading"""
        if session_id:
            return self.session_contexts.get(session_id)
        return self.previous_response_id

    def _set_previous_response_id(self, response_id: str, session_id: Optional[str] = None):
        """Set previous response ID for context threading"""
        if session_id:
            self.session_contexts[session_id] = response_id
        else:
            self.previous_response_id = response_id

    async def create_structured(
        self,
        response_format: Type[T],
        messages: List[Dict[str, Any]],
        reasoning_effort: str = "medium",
        session_id: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = None
    ) -> Tuple[T, str]:
        """
        Create structured response with Pydantic model using Responses API.

        Returns:
            Tuple of (parsed_model, response_id)
        """
        model_name = self._get_model_name(model)

        # Build request parameters for responses.parse
        request_params = {
            "model": model_name,
            "messages": messages,
            "response_format": response_format
        }

        # Add previous response ID for context threading
        prev_id = self._get_previous_response_id(session_id)
        if prev_id:
            request_params["previous_response_id"] = prev_id

        try:
            # Use responses.parse for structured outputs
            response = await self.client.responses.parse(**request_params)

            # Extract response ID for context threading
            response_id = getattr(response, 'id', None)
            if response_id:
                self._set_previous_response_id(response_id, session_id)

            # Parse the structured response - responses.parse returns .parsed directly
            parsed_model = response.parsed

            return parsed_model, response_id

        except Exception as e:
            logger.error(f"Responses API structured request failed: {str(e)}")
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
        """
        Execute tool calling turn using Responses API.

        Returns:
            ResponseMessage with content, tool_calls, and response_id
        """
        model_name = self._get_model_name(model)

        request_params = {
            "model": model_name,
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice
        }

        # Add previous response ID for context threading
        prev_id = self._get_previous_response_id(session_id)
        if prev_id:
            request_params["previous_response_id"] = prev_id

        try:
            # Use responses.create for tool calling
            response = await self.client.responses.create(**request_params)

            # Extract response ID
            response_id = getattr(response, 'id', None)
            if response_id:
                self._set_previous_response_id(response_id, session_id)

            # Extract message content and tool calls from responses format
            content = getattr(response, 'content', None)
            tool_calls = getattr(response, 'tool_calls', [])

            return ResponseMessage(
                content=content,
                tool_calls=tool_calls,
                response_id=response_id
            )

        except Exception as e:
            logger.error(f"Responses API tool calling failed: {str(e)}")
            raise

    async def stream_response(
        self,
        messages: List[Dict[str, Any]],
        reasoning_effort: str = "low",
        session_id: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> AsyncGenerator[ResponseDelta, None]:
        """
        Stream response with reasoning tokens using Responses API.

        Yields:
            ResponseDelta objects with content and reasoning
        """
        model_name = self._get_model_name(model)

        request_params = {
            "model": model_name,
            "messages": messages,
            "stream": True
        }

        # Add previous response ID for context threading
        prev_id = self._get_previous_response_id(session_id)
        if prev_id:
            request_params["previous_response_id"] = prev_id

        try:
            # Use responses.stream for streaming
            async with self.client.responses.stream(**request_params) as stream:
                async for chunk in stream:
                    # Extract content and reasoning from stream events
                    content = getattr(chunk, 'content', None)
                    reasoning = getattr(chunk, 'reasoning', None)
                    tool_calls = getattr(chunk, 'tool_calls', None)

                    if content or reasoning or tool_calls:
                        yield ResponseDelta(
                            content=content,
                            reasoning=reasoning,
                            tool_calls=tool_calls
                        )

                    # Update response ID if available
                    if hasattr(chunk, 'id'):
                        self._set_previous_response_id(chunk.id, session_id)

        except Exception as e:
            logger.error(f"Responses API streaming failed: {str(e)}")
            raise

    async def simple_completion(
        self,
        messages: List[Dict[str, Any]],
        reasoning_effort: str = "low",
        session_id: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> Tuple[str, str]:
        """
        Simple completion without structured output.

        Returns:
            Tuple of (content, response_id)
        """
        model_name = self._get_model_name(model)

        request_params = {
            "model": model_name,
            "messages": messages
        }

        # Add previous response ID for context threading
        prev_id = self._get_previous_response_id(session_id)
        if prev_id:
            request_params["previous_response_id"] = prev_id

        try:
            # Use responses.create for simple completion
            response = await self.client.responses.create(**request_params)

            # Extract response ID
            response_id = getattr(response, 'id', None)
            if response_id:
                self._set_previous_response_id(response_id, session_id)

            # Extract content from responses format
            content = getattr(response, 'content', '')
            return content, response_id

        except Exception as e:
            logger.error(f"Responses API simple completion failed: {str(e)}")
            raise


# Global client instance
_unified_client: Optional[UnifiedResponsesClient] = None

def get_unified_client() -> UnifiedResponsesClient:
    """Get or create global unified client instance"""
    global _unified_client
    if _unified_client is None:
        try:
            _unified_client = UnifiedResponsesClient()
        except ValueError:
            # API key not available - return None to trigger fallback
            return None
    return _unified_client