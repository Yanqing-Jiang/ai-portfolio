from __future__ import annotations
import logging
import os
import sys
from typing import Dict, Any, List, Optional, AsyncGenerator, Type, TypeVar
from pydantic import BaseModel
import openai
from openai import OpenAI, AsyncOpenAI

# Add parent directory to path for unified client import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unified_responses_client import get_unified_client
from analytics_memory.openai_client import get_openai_client

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class SupervisorResponsesClient:
    """
    Specialized client for OpenAI Responses API with Claude Code-style supervision.

    Handles planning turns, tool calling loops, and structured outputs for the
    single-agent supervisor pattern using the unified responses client.
    """

    def __init__(self):
        # Use unified client for Responses API
        self.unified_client = get_unified_client()

        # Keep base client for direct API access
        self.base_client = get_openai_client()
        if not self.base_client and not self.unified_client:
            raise ValueError("OpenAI client not available - check API key")

        # Direct async client for responses API
        self.async_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def _get_model_name(self, model: Optional[str] = None) -> str:
        """Get model name for supervisor - prefer GPT-5 for reasoning"""
        if model:
            return model
        return "gpt-5-mini-2025-08-07"  # Use GPT-5 for supervisor reasoning

    async def planning_turn(
        self,
        messages: List[Dict[str, Any]],
        response_format: Type[T],
        session_id: Optional[str] = None,
        reasoning_effort: str = "high"
    ) -> T:
        """
        Planning turn: structured response with high reasoning effort.
        No tool calls - just planning and approval requirements.
        """
        try:
            if self.unified_client:
                # Use unified client with Responses API
                result, _ = await self.unified_client.create_structured(
                    response_format=response_format,
                    messages=messages,
                    reasoning_effort=reasoning_effort,
                    session_id=session_id,
                    model=self._get_model_name()
                )
                return result
            else:
                # Direct responses API call
                model_name = self._get_model_name()
                request_params = {
                    "model": model_name,
                    "messages": messages,
                    "response_format": response_format
                }

                response = await self.async_client.responses.parse(**request_params)
                return response.parsed

        except Exception as e:
            logger.error(f"Planning turn failed: {str(e)}")
            raise

    async def tool_calling_turn(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        tool_choice: str = "auto",
        session_id: Optional[str] = None,
        reasoning_effort: str = "medium"
    ) -> Dict[str, Any]:
        """
        Tool calling turn: agent decides which tools to call and with what parameters.
        Returns the assistant's response including any tool calls.
        """
        try:
            if self.unified_client:
                # Use unified client with Responses API
                response = await self.unified_client.tool_calling_turn(
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    reasoning_effort=reasoning_effort,
                    session_id=session_id,
                    model=self._get_model_name()
                )
                # Return message content for tool call processing
                return {
                    "content": response.content,
                    "tool_calls": response.tool_calls
                }
            else:
                # Direct responses API call
                model_name = self._get_model_name()
                request_params = {
                    "model": model_name,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": tool_choice
                }

                response = await self.async_client.responses.create(**request_params)
                return {
                    "content": getattr(response, 'content', ''),
                    "tool_calls": getattr(response, 'tool_calls', [])
                }

        except Exception as e:
            logger.error(f"Tool calling turn failed: {str(e)}")
            raise

    async def finalization_turn(
        self,
        messages: List[Dict[str, Any]],
        response_format: Optional[Type[T]] = None,
        session_id: Optional[str] = None,
        reasoning_effort: str = "low"
    ) -> T:
        """
        Finalization turn: summarize results with low reasoning effort.
        """
        try:
            if self.unified_client and response_format:
                # Use unified client with structured response
                result, _ = await self.unified_client.create_structured(
                    response_format=response_format,
                    messages=messages,
                    reasoning_effort=reasoning_effort,
                    session_id=session_id,
                    model=self._get_model_name()
                )
                return result
            elif self.unified_client:
                # Use unified client for simple completion
                content, _ = await self.unified_client.simple_completion(
                    messages=messages,
                    reasoning_effort=reasoning_effort,
                    session_id=session_id,
                    model=self._get_model_name()
                )
                return content
            else:
                # Direct responses API call
                model_name = self._get_model_name()
                request_params = {
                    "model": model_name,
                    "messages": messages
                }

                if response_format:
                    response = await self.async_client.responses.parse(**request_params)
                    return response.parsed
                else:
                    response = await self.async_client.responses.create(**request_params)
                    return getattr(response, 'content', '')

        except Exception as e:
            logger.error(f"Finalization turn failed: {str(e)}")
            raise

    async def stream_analysis(
        self,
        messages: List[Dict[str, Any]],
        session_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream analysis using unified client with Responses API streaming.
        """
        try:
            if self.unified_client:
                # Use unified client with Responses API streaming
                async for delta in self.unified_client.stream_response(
                    messages=messages,
                    reasoning_effort="low",  # Low effort for streaming analysis
                    session_id=session_id,
                    model=self._get_model_name()
                ):
                    if delta.content:
                        yield delta.content
            else:
                # Direct responses streaming
                model_name = self._get_model_name()
                request_params = {
                    "model": model_name,
                    "messages": messages,
                    "stream": True
                }

                async with self.async_client.responses.stream(**request_params) as stream:
                    async for chunk in stream:
                        content = getattr(chunk, 'content', None)
                        if content:
                            yield content
        except Exception as e:
            logger.error(f"Analysis streaming failed: {str(e)}")
            yield f"Analysis error: {str(e)}"


# Global supervisor client instance
_supervisor_client: Optional[SupervisorResponsesClient] = None

def get_supervisor_client() -> SupervisorResponsesClient:
    """Get or create global supervisor client instance"""
    global _supervisor_client
    if _supervisor_client is None:
        try:
            _supervisor_client = SupervisorResponsesClient()
        except ValueError:
            # API key not available - raise error since supervisor requires it
            raise ValueError("OpenAI API key required for supervisor functionality")
    return _supervisor_client