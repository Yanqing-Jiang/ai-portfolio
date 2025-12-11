# --- Analytics Function/Class Map ---
# Class: OpenAIClient
#   Role: Adapter for analytics_memory to use UnifiedResponsesClient with Responses API only
#   Called from: Internal to analytics.core.openai_client
#   Collaborators: openai.AsyncOpenAI, os.getenv, concurrent.futures.futures.ThreadPoolExecutor
#   Why: Supports downstream analytics workflows that rely on OpenAIClient.
# Function: get_openai_client
#   Role: Get or create global OpenAI client instance
#   Called from: analytics.core.analysis
#   Invokes: analytics.core.openai_client.OpenAIClient
#   Why: Supports downstream analytics workflows that rely on get_openai_client.
# --- End Analytics Function/Class Map ---
from __future__ import annotations
import os
import json
import logging
from typing import Dict, Any, Optional, AsyncGenerator, TypeVar, Type
from pydantic import BaseModel
import openai
from openai import OpenAI, AsyncOpenAI

# Render starts uvicorn inside the backend/ directory, so the project root
# (which contains the `backend` package) may be missing from PYTHONPATH.
# Fallback to a local import so deployment works whether the package name
# is resolvable or not.
try:
    from backend import unified_responses_client
except ModuleNotFoundError:  # pragma: no cover - only hit in Render envs
    import unified_responses_client  # type: ignore

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class OpenAIClient:
    """Adapter for analytics_memory to use UnifiedResponsesClient with Responses API only"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not found")

        # Use unified client for Responses API
        self.unified_client = unified_responses_client.get_unified_client()
        if not self.unified_client:
            raise ValueError("Failed to initialize unified responses client")

        # Direct async client for responses API only (retry capped at 3 total attempts)
        self.async_client = AsyncOpenAI(api_key=self.api_key, max_retries=3)

    def _get_model_name(self, model: Optional[str] = None) -> str:
        """Get model name with fallback logic"""
        if model:
            return model

        # Check for environment override
        env_model = os.getenv("OPENAI_INTENT_MODEL")
        if env_model:
            return env_model

        # Use GPT-5 mini for next-gen-analytics-agent as specified in CLAUDE.md
        return "gpt-5-mini-2025-08-07"

    def create_structured(
        self,
        response_model: Type[T],
        messages: list[dict],
        model: Optional[str] = None,
        session_id: Optional[str] = None,
        reasoning_effort: str = "medium"
    ) -> T:
        """Create structured response with Pydantic model using responses API only"""
        try:
            # Use unified client with Responses API in a thread to avoid event loop conflicts
            import asyncio
            import concurrent.futures

            async def _create_structured():
                return await self.unified_client.create_structured(
                    response_model=response_model,
                    messages=messages,
                    reasoning_effort=reasoning_effort,
                    session_id=session_id,
                    model=self._get_model_name(model)
                )

            # Run in a new event loop in a thread to avoid conflicts
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _create_structured())
                result, _ = future.result()
                return result

        except Exception as e:
            logger.error(f"Responses API structured request failed: {str(e)}")
            raise

    async def create_structured_async(
        self,
        response_model: Type[T],
        messages: list[dict],
        model: Optional[str] = None,
        session_id: Optional[str] = None,
        reasoning_effort: str = "medium"
    ) -> T:
        """Async version of structured response using responses API only"""
        try:
            # Use unified client with Responses API
            result, _ = await self.unified_client.create_structured(
                response_model=response_model,
                messages=messages,
                reasoning_effort=reasoning_effort,
                session_id=session_id,
                model=self._get_model_name(model)
            )
            return result

        except Exception as e:
            logger.error(f"Responses API async structured request failed: {str(e)}")
            raise

    async def stream_completion(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Stream completion for analysis generation using responses API only"""
        try:
            # Use unified client with Responses API streaming
            async for delta in self.unified_client.stream_response(
                messages=messages,
                reasoning_effort="low",  # Use low effort for streaming analysis
                session_id=session_id,
                model=self._get_model_name(model)
            ):
                if delta.content:
                    yield delta.content

        except Exception as e:
            logger.error(f"Responses API streaming request failed: {str(e)}")
            raise


# Global client instance
_client: Optional[OpenAIClient] = None

def get_openai_client() -> OpenAIClient:
    """Get or create global OpenAI client instance"""
    global _client
    if _client is None:
        try:
            _client = OpenAIClient()
        except ValueError:
            # API key not available - return None to trigger fallback
            return None
    return _client
