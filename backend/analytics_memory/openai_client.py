from __future__ import annotations
import os
import json
import logging
from typing import Dict, Any, Optional, AsyncGenerator, TypeVar, Type
from pydantic import BaseModel
import openai
from openai import OpenAI, AsyncOpenAI

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class OpenAIClient:
    """Lightweight wrapper for OpenAI Responses API with session support"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not found")
        
        # Initialize both sync and async clients
        self.client = OpenAI(api_key=self.api_key)
        self.async_client = AsyncOpenAI(api_key=self.api_key)
    
    def _get_model_name(self, model: Optional[str] = None) -> str:
        """Get model name with fallback logic"""
        if model:
            return model
        
        # Check for environment override
        env_model = os.getenv("OPENAI_INTENT_MODEL")
        if env_model:
            return env_model
            
        # Use GPT-5 mini for next-gen-analytics-memory as specified in CLAUDE.md
        return "gpt-5-mini-2025-08-07"
    
    def create_structured(
        self, 
        response_model: Type[T], 
        messages: list[dict], 
        model: Optional[str] = None,
        session_id: Optional[str] = None,
        reasoning_effort: str = "medium",
        temperature: float = 0
    ) -> T:
        """Create structured response with Pydantic model"""
        model_name = self._get_model_name(model)
        
        # Use structured outputs with proper syntax for GPT-5 models
        request_params = {
            "model": model_name,
            "messages": messages,
            "response_format": response_model  # Direct Pydantic model for structured output
        }
        
        # Only add temperature for non-GPT-5 models (GPT-5 only supports default temperature=1)
        if not model_name.startswith("gpt-5"):
            request_params["temperature"] = temperature
        
        try:
            # Use parse() for structured outputs
            response = self.client.chat.completions.parse(**request_params)
            
            # For structured outputs, the response is already parsed
            return response.choices[0].message.parsed
            
        except Exception as e:
            logger.error(f"OpenAI structured request failed: {str(e)}")
            # Re-raise to allow fallback handling
            raise
    
    async def create_structured_async(
        self, 
        response_model: Type[T], 
        messages: list[dict], 
        model: Optional[str] = None,
        session_id: Optional[str] = None,
        reasoning_effort: str = "medium",
        temperature: float = 0
    ) -> T:
        """Async version of structured response"""
        model_name = self._get_model_name(model)
        
        # Use structured outputs with proper syntax for GPT-5 models
        request_params = {
            "model": model_name,
            "messages": messages,
            "response_format": response_model  # Direct Pydantic model for structured output
        }
        
        # Only add temperature for non-GPT-5 models
        if not model_name.startswith("gpt-5"):
            request_params["temperature"] = temperature
        
        try:
            # Use parse() for structured outputs
            response = await self.async_client.chat.completions.parse(**request_params)
            
            # For structured outputs, the response is already parsed
            return response.choices[0].message.parsed
            
        except Exception as e:
            logger.error(f"OpenAI async structured request failed: {str(e)}")
            raise
    
    async def stream_completion(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        session_id: Optional[str] = None,
        temperature: float = 0
    ) -> AsyncGenerator[str, None]:
        """Stream completion for analysis generation"""
        model_name = self._get_model_name(model)
        
        # Prepare request params
        request_params = {
            "model": model_name,
            "messages": messages,
            "stream": True
        }
        
        # Only add temperature for non-GPT-5 models
        if not model_name.startswith("gpt-5"):
            request_params["temperature"] = temperature
        
        try:
            stream = await self.async_client.chat.completions.create(**request_params)
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"OpenAI streaming request failed: {str(e)}")
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