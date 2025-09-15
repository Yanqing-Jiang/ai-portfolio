from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator, Type, TypeVar
from pydantic import BaseModel
import openai
from openai import OpenAI, AsyncOpenAI
from analytics_memory.openai_client import get_openai_client

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class SupervisorResponsesClient:
    """
    Specialized client for OpenAI Responses API with Claude Code-style supervision.
    
    Handles planning turns, tool calling loops, and structured outputs for the
    single-agent supervisor pattern.
    """
    
    def __init__(self):
        # Reuse the existing OpenAI client from analytics_memory
        self.base_client = get_openai_client()
        if not self.base_client:
            raise ValueError("OpenAI client not available - check API key")
    
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
        model_name = self._get_model_name()
        
        request_params = {
            "model": model_name,
            "messages": messages,
            "response_format": response_format
        }
        
        # Add reasoning effort if supported
        if hasattr(openai, "responses") and reasoning_effort:
            request_params["reasoning"] = {"effort": reasoning_effort}
        
        # Only add temperature for non-GPT-5 models
        if not model_name.startswith("gpt-5"):
            request_params["temperature"] = 0
            
        try:
            if self.base_client.async_client:
                response = await self.base_client.async_client.chat.completions.parse(**request_params)
            else:
                response = self.base_client.client.chat.completions.parse(**request_params)
            
            # Parse structured response
            return response.choices[0].message.parsed
            
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
        model_name = self._get_model_name()
        
        request_params = {
            "model": model_name,
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice
        }
        
        # Add reasoning effort if supported  
        if hasattr(openai, "responses") and reasoning_effort:
            request_params["reasoning"] = {"effort": reasoning_effort}
        
        # Only add temperature for non-GPT-5 models
        if not model_name.startswith("gpt-5"):
            request_params["temperature"] = 0
            
        try:
            if self.base_client.async_client:
                response = await self.base_client.async_client.chat.completions.create(**request_params)
            else:
                response = self.base_client.client.chat.completions.create(**request_params)
            
            # Return the full response for tool call processing
            return response.choices[0].message
            
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
        model_name = self._get_model_name()
        
        request_params = {
            "model": model_name,
            "messages": messages
        }
        
        if response_format:
            request_params["response_format"] = response_format
        
        # Add reasoning effort if supported
        if hasattr(openai, "responses") and reasoning_effort:
            request_params["reasoning"] = {"effort": reasoning_effort}
        
        # Only add temperature for non-GPT-5 models
        if not model_name.startswith("gpt-5"):
            request_params["temperature"] = 0
            
        try:
            if response_format:
                if self.base_client.async_client:
                    response = await self.base_client.async_client.chat.completions.parse(**request_params)
                else:
                    response = self.base_client.client.chat.completions.parse(**request_params)
                return response.choices[0].message.parsed
            else:
                if self.base_client.async_client:
                    response = await self.base_client.async_client.chat.completions.create(**request_params)
                else:
                    response = self.base_client.client.chat.completions.create(**request_params)
                return response.choices[0].message.content
                
        except Exception as e:
            logger.error(f"Finalization turn failed: {str(e)}")
            raise
    
    async def stream_analysis(
        self,
        messages: List[Dict[str, Any]],
        session_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream analysis using the existing analysis streaming from analytics_memory.
        Reuses the proven streaming implementation.
        """
        try:
            async for chunk in self.base_client.stream_completion(
                messages=messages,
                session_id=session_id
            ):
                if chunk:
                    yield chunk
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