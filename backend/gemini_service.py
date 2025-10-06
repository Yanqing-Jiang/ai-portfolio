import os
import asyncio
import json
from typing import AsyncGenerator, Optional, List, Dict, Any, Generator
from types import SimpleNamespace
from google import genai as google_genai
from google.genai import types as genai_types
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
    # Inline minimal shim configure
    pass

class GeminiChatService:
    def __init__(self):
        # Use the latest Gemini 2.5 Flash model as per current best practices
        self.model = None
        if GEMINI_API_KEY:
            _genai_configure(api_key=GEMINI_API_KEY)
            self.model = _GenerativeModel('gemini-2.5-flash')
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
        """Send a message and stream the response (via google-genai)."""
        if not GEMINI_API_KEY or not self.model:
            yield "Error: Gemini API not configured"
            return

        if session_id not in self.chats:
            yield "Error: Chat session not found"
            return

        try:
            # Prepare messages and flatten to strings
            messages = self._prepare_messages(session_id, message)
            history_texts: List[str] = []
            for msg in messages:
                parts = msg.get('parts') if isinstance(msg, dict) else None
                part = (parts or [None])[-1] if isinstance(parts, list) else None
                text = part if isinstance(part, str) else (part.get('text') if isinstance(part, dict) else None)
                if isinstance(text, str) and text:
                    history_texts.append(text)

            generation_config = {
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 8192,
            }

            # Stream the response with no buffering via shim
            full_response = ""
            chunk_count = 0
            print(f"Starting Gemini response streaming for session {session_id}")  # Debug log
            model_name = getattr(self.model, 'model_name', 'gemini-2.5-flash') if self.model else 'gemini-2.5-flash'
            for chunk_text in _generate_content_stream(
                model=model_name,
                contents=history_texts,
                generation_config=generation_config,
            ):
                if chunk_text:
                    full_response += chunk_text
                    print(f"Gemini service yielding chunk {chunk_count}: '{chunk_text[:50]}...'")  # Debug log
                    yield chunk_text
                    await asyncio.sleep(0)
                    chunk_count += 1

            print(f"Gemini service completed, total chunks: {chunk_count}")  # Debug log

            # Update chat history (skip the system instruction setup messages)
            if session_id in self.chats:
                chat_session = self.chats[session_id]
                if not (chat_session['system_instruction'] and not chat_session['history']):
                    self.chats[session_id]['history'].append({'role': 'user', 'content': message})
                    self.chats[session_id]['history'].append({'role': 'model', 'content': full_response})

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

            # Flatten to simple list[str]
            history_texts: List[str] = []
            for msg in messages:
                parts = msg.get('parts') if isinstance(msg, dict) else None
                part = (parts or [None])[-1] if isinstance(parts, list) else None
                text = part if isinstance(part, str) else (part.get('text') if isinstance(part, dict) else None)
                if isinstance(text, str) and text:
                    history_texts.append(text)

            model_name = getattr(self.model, 'model_name', 'gemini-2.5-flash') if self.model else 'gemini-2.5-flash'
            resp = _GenerativeModel(model_name, {"temperature": 0.7, "top_p": 0.8, "top_k": 40, "max_output_tokens": 8192}).generate_content(contents=history_texts)
            text = (resp or {}).get('text') if isinstance(resp, dict) else None

            # Update chat history
            if session_id in self.chats:
                chat_session = self.chats[session_id]
                if not (chat_session['system_instruction'] and not chat_session['history']):
                    self.chats[session_id]['history'].append({'role': 'user','content': message})
                    self.chats[session_id]['history'].append({'role': 'model','content': text or ''})
            return text or ""
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
            response = _GenerativeModel(getattr(self.model, 'model_name', 'gemini-2.5-flash') if self.model else 'gemini-2.5-flash', generation_config).generate_content(
                contents=prompt,
                tools=[{"google_search": {}}],
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

# --- Inline shim for google-genai (local to this module) ---
_client: Optional[google_genai.Client] = None


def _ensure_client() -> google_genai.Client:
    global _client
    if _client is None:
        _client = google_genai.Client()
    return _client


def _genai_configure(*, api_key: str) -> None:
    global _client
    _client = google_genai.Client(api_key=api_key)


class _GenerativeModel:
    def __init__(self, model_name: str, generation_config: Optional[Dict[str, Any]] = None) -> None:
        self.model_name = model_name
        self._gen_cfg = dict(generation_config or {})

    def generate_content(self, *, contents: Any, tools: Optional[List[Dict[str, Any]]] = None, **_: Any) -> Dict[str, Any]:
        client = _ensure_client()
        tool_objs: Optional[List[genai_types.Tool]] = None
        if tools:
            for item in tools:
                if isinstance(item, dict) and ("google_search" in item):
                    tool_objs = tool_objs or []
                    tool_objs.append(genai_types.Tool(google_search=genai_types.GoogleSearch()))
        cfg_dict = dict(self._gen_cfg)
        if tool_objs is not None:
            cfg_dict["tools"] = tool_objs
        config = genai_types.GenerateContentConfig(**cfg_dict) if cfg_dict else None

        # Coerce to list[str]
        content_list: List[str] = []
        if isinstance(contents, str):
            content_list = [contents]
        elif isinstance(contents, list):
            for entry in contents:
                if isinstance(entry, dict) and "parts" in entry:
                    for p in entry.get("parts") or []:
                        text = p.get("text") if isinstance(p, dict) else None
                        if isinstance(text, str):
                            content_list.append(text)
                elif isinstance(entry, str):
                    content_list.append(entry)
        else:
            content_list = [str(contents)]

        resp = client.models.generate_content(model=self.model_name, contents=content_list, config=config)
        for attr in ("to_dict", "model_dump"):
            fn = getattr(resp, attr, None)
            if callable(fn):
                try:
                    data = fn()
                    if isinstance(data, dict):
                        return data
                except Exception:
                    pass
        text = getattr(resp, "text", None)
        return {"text": text} if isinstance(text, str) else {}


def _generate_content_stream(*, model: str, contents: Any, generation_config: Optional[Dict[str, Any]] = None, tools: Optional[List[Dict[str, Any]]] = None):
    client = _ensure_client()
    cfg_dict = dict(generation_config or {})
    tool_objs: Optional[List[genai_types.Tool]] = None
    if tools:
        for item in tools:
            if isinstance(item, dict) and ("google_search" in item):
                tool_objs = tool_objs or []
                tool_objs.append(genai_types.Tool(google_search=genai_types.GoogleSearch()))
    if tool_objs is not None:
        cfg_dict["tools"] = tool_objs
    config = genai_types.GenerateContentConfig(**cfg_dict) if cfg_dict else None

    content_list: List[str] = []
    if isinstance(contents, str):
        content_list = [contents]
    elif isinstance(contents, list):
        for entry in contents:
            if isinstance(entry, dict) and "parts" in entry:
                for p in entry.get("parts") or []:
                    text = p.get("text") if isinstance(p, dict) else None
                    if isinstance(text, str):
                        content_list.append(text)
            elif isinstance(entry, str):
                content_list.append(entry)
    else:
        content_list = [str(contents)]

    for chunk in client.models.generate_content_stream(model=model, contents=content_list, config=config):
        text = getattr(chunk, 'text', None)
        if isinstance(text, str) and text:
            yield text

# Global instance
gemini_service = GeminiChatService()

