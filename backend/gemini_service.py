import os
import asyncio
import json
from typing import AsyncGenerator, Optional, List, Dict, Any, Generator
import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("GEMINI_API_KEY not found in environment variables")
    print("Please set GEMINI_API_KEY in your .env file")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class GeminiChatService:
    def __init__(self):
        # Use the latest Gemini 2.5 Flash model as per current best practices
        self.model = genai.GenerativeModel('gemini-2.5-flash') if GEMINI_API_KEY else None
        self.chats = {}  # Store chat sessions by session_id
    
    def create_chat(self, session_id: str, system_instruction: str = None) -> str:
        """Create a new chat session"""
        if not GEMINI_API_KEY or not self.model:
            return None
            
        if system_instruction:
            self.chats[session_id] = {
                'history': [],
                'system_instruction': system_instruction
            }
        else:
            self.chats[session_id] = {
                'history': [],
                'system_instruction': None
            }
        return session_id
    
    def _prepare_messages(self, session_id: str, user_message: str) -> List[Dict[str, Any]]:
        """Prepare messages for Gemini API"""
        chat_session = self.chats.get(session_id, {'history': [], 'system_instruction': None})
        
        messages = []
        
        # Add system instruction as first message if present and no history exists
        if chat_session['system_instruction'] and not chat_session['history']:
            messages.append({
                'role': 'user',
                'parts': [f"System: {chat_session['system_instruction']}\n\nPlease acknowledge this system instruction and wait for my next message."]
            })
            messages.append({
                'role': 'model',
                'parts': ["I understand the system instruction. I'm ready to help you according to those guidelines."]
            })
        
        # Add conversation history
        for msg in chat_session['history']:
            messages.append({
                'role': msg['role'],
                'parts': [msg['content']]
            })
        
        # Add the new user message
        messages.append({
            'role': 'user', 
            'parts': [user_message]
        })
        
        return messages
    
    async def send_message_stream(self, session_id: str, message: str) -> AsyncGenerator[str, None]:
        """Send a message and stream the response"""
        if not GEMINI_API_KEY or not self.model:
            yield "Error: Gemini API not configured"
            return
            
        if session_id not in self.chats:
            yield "Error: Chat session not found"
            return
            
        try:
            # Prepare messages
            messages = self._prepare_messages(session_id, message)
            
            # Create chat with history
            chat = self.model.start_chat(history=messages[:-1])  # All except the last user message
            
            # Configure generation with no buffering (consistent with your requirements)
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 8192,
                "response_mime_type": "text/plain",
            }
            
            # Send the last user message and stream response
            response = chat.send_message(
                messages[-1]['parts'][0], 
                generation_config=generation_config,
                stream=True
            )
            
            # Stream the response with no buffering
            full_response = ""
            chunk_count = 0
            print(f"Starting Gemini response streaming for session {session_id}")  # Debug log
            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    print(f"Gemini service yielding chunk {chunk_count}: '{chunk.text[:50]}...'")  # Debug log
                    yield chunk.text
                    await asyncio.sleep(0)  # Force immediate flushing - no buffering
                    chunk_count += 1
            
            print(f"Gemini service completed, total chunks: {chunk_count}")  # Debug log
            
            # Update chat history (skip the system instruction setup messages)
            if session_id in self.chats:
                chat_session = self.chats[session_id]
                # Only add to history if this isn't the system instruction setup
                if not (chat_session['system_instruction'] and not chat_session['history']):
                    self.chats[session_id]['history'].append({
                        'role': 'user',
                        'content': message
                    })
                    self.chats[session_id]['history'].append({
                        'role': 'model', 
                        'content': full_response
                    })
            
        except Exception as e:
            print(f"Gemini streaming error: {e}")  # Debug log
            yield f"Error: {str(e)}"
    
    def send_message_sync(self, session_id: str, message: str) -> str:
        """Send message synchronously without streaming"""
        if not GEMINI_API_KEY or not self.model:
            return "Error: Gemini API not configured"
            
        if session_id not in self.chats:
            return "Error: Chat session not found"
        
        try:
            # Prepare messages
            messages = self._prepare_messages(session_id, message)
            
            # Create chat with history
            chat = self.model.start_chat(history=messages[:-1])
            
            # Send message
            response = chat.send_message(messages[-1]['parts'][0])
            
            # Update chat history
            if session_id in self.chats:
                chat_session = self.chats[session_id]
                if not (chat_session['system_instruction'] and not chat_session['history']):
                    self.chats[session_id]['history'].append({
                        'role': 'user',
                        'content': message
                    })
                    self.chats[session_id]['history'].append({
                        'role': 'model', 
                        'content': response.text
                    })
            
            return response.text
        except Exception as e:
            return f"Error during message processing: {str(e)}"
    
    def get_chat_history(self, session_id: str) -> List[Dict[str, str]]:
        """Get chat history for a session"""
        return self.chats.get(session_id, {}).get('history', [])
    
    def clear_chat_history(self, session_id: str):
        """Clear chat history for a session"""
        if session_id in self.chats:
            self.chats[session_id]['history'] = []
    
    def delete_chat(self, session_id: str):
        """Delete a chat session"""
        if session_id in self.chats:
            del self.chats[session_id]

    def search(self, query: str, *, max_results: int = 5, context: Optional[str] = None) -> Dict[str, Any]:
        """Run a Gemini web search and return structured summary data."""

        if not GEMINI_API_KEY or not self.model:
            raise RuntimeError("Gemini API not configured")

        prompt_lines = [
            "Use Google search to gather up-to-date information relevant to the analytics query below.",
            f"Query: {query}",
        ]
        if context:
            prompt_lines.append(f"Context: {context}")
        prompt_lines.append("Return your answer strictly as JSON with keys 'summary' (<=75 words) and 'sources'.")
        prompt_lines.append("'sources' must be an array of objects with fields 'title', 'url', 'snippet', and optional 'published_at'.")
        prompt = "\n".join(prompt_lines)

        generation_config = {
            "temperature": 0.3,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 1024,
        }

        try:
            response = self.model.generate_content(
                prompt,
                tools=[{"google_search_retrieval": {}}],
                generation_config=generation_config,
            )
        except Exception as exc:
            raise RuntimeError(f"Gemini search failed: {exc}") from exc

        text_output = getattr(response, "text", None)
        if not text_output:
            parts: List[str] = []
            for candidate in getattr(response, "candidates", []) or []:
                content = getattr(candidate, "content", None)
                if not content:
                    continue
                for part in getattr(content, "parts", []) or []:
                    segment = getattr(part, "text", None)
                    if segment:
                        parts.append(segment)
            text_output = "\n".join(parts)

        if not text_output:
            return {"summary": "", "sources": [], "model": getattr(self.model, 'model_name', 'gemini-2.5-flash')}

        try:
            data = json.loads(text_output)
        except json.JSONDecodeError:
            data = {"summary": text_output.strip(), "sources": []}

        if not isinstance(data, dict):
            data = {"summary": str(data), "sources": []}

        sources = data.get("sources")
        if isinstance(sources, list):
            data["sources"] = sources[:max_results]
        else:
            data["sources"] = []

        data.setdefault("model", getattr(self.model, 'model_name', 'gemini-2.5-flash'))
        return data

# Global instance
gemini_service = GeminiChatService()