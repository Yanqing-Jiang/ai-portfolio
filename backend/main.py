import asyncio
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
import os
import json
import uuid


from research_agent import run_research_agent, run_research_agent_stream
from resume_agent import run_resume_agent, run_resume_agent_stream
from tts import get_voice_bytes
from gemini_service import gemini_service
from rate_limiter import init_rate_limiter, smart_rate_limit, get_user_usage, who_am_i

from langchain.callbacks.base import BaseCallbackHandler
from typing import List, Tuple, Optional

# Always load the .env file located in the backend directory (same folder as this file)
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)

app = FastAPI()

# Initialize rate limiter on startup
@app.on_event("startup")
async def startup_event():
    await init_rate_limiter()

# Allow CORS for local frontend dev
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "*"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ResearchRequest(BaseModel):
    query: str
    chat_history: List[Tuple[str, str]] = []

# Request model for TTS
class TTSRequest(BaseModel):
    text: str

# Request models for Gemini API
class GeminiChatRequest(BaseModel):
    system_instruction: str

class GeminiMessageRequest(BaseModel):
    message: str
    session_id: str

# Request model for streaming TTS
class TTSStreamRequest(BaseModel):
    text: str
    session_id: Optional[str] = None

# In-memory chat sessions storage
chat_sessions = {}

class StreamingCallbackHandler(BaseCallbackHandler):
    def __init__(self):
        self.steps = []

    def on_tool_start(self, tool, input_str, **kwargs):
        step = f"🔍 Running {tool.name}..."
        self.steps.append(step)
        return step

    def on_tool_end(self, output, **kwargs):
        step = "✅ Tool completed"
        self.steps.append(step)
        return step

    def on_text(self, text, **kwargs):
        self.steps.append(text)
        return text

    def on_llm_start(self, serialized, prompts, **kwargs):
        step = "🤖 Thinking..."
        self.steps.append(step)
        return step

class StepCollectorCallbackHandler(BaseCallbackHandler):
    def __init__(self):
        self.steps = []

    def on_tool_start(self, tool, input_str, **kwargs):
        self.steps.append(f"Running tool: {tool.name} with input: {input_str}")

    def on_tool_end(self, output, **kwargs):
        self.steps.append(f"Tool output: {output}")

    def on_text(self, text, **kwargs):
        self.steps.append(f"Agent: {text}")

@app.post("/api/research")
def research_endpoint(request: ResearchRequest):
    result = run_research_agent(request.query)
    return result  # returns both 'answer' and 'steps'

@app.get("/api/research/stream")
async def research_stream_endpoint(query: str, request: Request, _=Depends(smart_rate_limit)):
    async def generate_stream():
        try:
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': '🔎 Starting research agent...', 'replace': False})}\n\n"
            await asyncio.sleep(0)  # Flush event loop
            
            # Run the research agent with streaming
            chunk_count = 0
            in_final_response = False
            final_response_message_sent = False
            last_heartbeat = asyncio.get_event_loop().time()
            
            for chunk in run_research_agent_stream(query):
                if chunk:
                    try:
                        # Handle special status replacement messages
                        if chunk.startswith("STATUS_REPLACE:"):
                            status_message = chunk[15:]  # Remove "STATUS_REPLACE:" prefix
                            yield f"data: {json.dumps({'type': 'status', 'message': status_message, 'replace': True})}\n\n"
                            await asyncio.sleep(0)  # Flush event loop
                            continue
                        
                        # Handle status update messages (append to status)
                        if chunk.startswith("STATUS_UPDATE:"):
                            status_message = chunk[14:]  # Remove "STATUS_UPDATE:" prefix
                            yield f"data: {json.dumps({'type': 'status', 'message': status_message, 'replace': False})}\n\n"
                            await asyncio.sleep(0)  # Flush event loop
                            continue
                        
                        # Handle final response marker
                        if chunk == "FINAL_RESPONSE_START":
                            in_final_response = True
                            # Only send the message once
                            if not final_response_message_sent:
                                yield f"data: {json.dumps({'type': 'status', 'message': '✅ Research complete, generating final response...', 'replace': True})}\n\n"
                                await asyncio.sleep(0)  # Flush event loop
                                final_response_message_sent = True
                            continue
                        
                        # (Optional) Previously truncated long chunks; keep full chunk to avoid losing data
                        
                        # Determine chunk type based on content and mode
                        chunk_type = 'response' if in_final_response else 'chunk'
                        yield f"data: {json.dumps({'type': chunk_type, 'text': chunk})}\n\n"
                        await asyncio.sleep(0)  # Flush event loop immediately after each chunk
                        chunk_count += 1
                        
                        # Send heartbeat every 15 seconds to prevent timeouts
                        current_time = asyncio.get_event_loop().time()
                        if current_time - last_heartbeat > 15:
                            yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                            await asyncio.sleep(0)
                            last_heartbeat = current_time
                        
                        # Prevent too many chunks
                        if chunk_count > 5000:
                            yield f"data: {json.dumps({'type': 'status', 'message': '⚠️ Response truncated due to length', 'replace': True})}\n\n"
                            await asyncio.sleep(0)
                            break
                            
                    except Exception as chunk_error:
                        # Handle individual chunk errors
                        yield f"data: {json.dumps({'type': 'error', 'message': f'Chunk error: {str(chunk_error)}'})}\n\n"
                        await asyncio.sleep(0)
                        break
            
            # Send completion signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            await asyncio.sleep(0)  # Final flush
            
        except GeneratorExit:
            # Client disconnected
            return
        except Exception as e:
            try:
                error_msg = f"Error during research: {str(e)}"
                yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                await asyncio.sleep(0)
            except:
                # If we can't even send the error, just return
                return
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )

@app.get("/api/resume-search/stream")
async def resume_search_stream_endpoint(query: str, request: Request, chat_history: str = "[]", _=Depends(smart_rate_limit)):
    # Parse chat_history from JSON string
    try:
        parsed_history = json.loads(chat_history) if chat_history else []
    except json.JSONDecodeError:
        parsed_history = []
    
    async def generate_stream():
        try:
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': '📄 Starting resume search...', 'replace': False})}\n\n"
            await asyncio.sleep(0)  # Flush event loop
            
            # Run the resume agent with streaming
            chunk_count = 0
            in_final_response = False
            last_heartbeat = asyncio.get_event_loop().time()
            
            for chunk in run_resume_agent_stream(query, parsed_history):
                if chunk:
                    try:
                        # Handle special status replacement messages
                        if chunk.startswith("STATUS_REPLACE:"):
                            status_message = chunk[15:]  # Remove "STATUS_REPLACE:" prefix
                            yield f"data: {json.dumps({'type': 'status', 'message': status_message, 'replace': True})}\n\n"
                            await asyncio.sleep(0)  # Flush event loop
                            continue
                        
                        # Handle status update messages (append to status)
                        if chunk.startswith("STATUS_UPDATE:"):
                            status_message = chunk[14:]  # Remove "STATUS_UPDATE:" prefix
                            yield f"data: {json.dumps({'type': 'status', 'message': status_message, 'replace': False})}\n\n"
                            await asyncio.sleep(0)  # Flush event loop
                            continue
                        
                        # Handle final response marker
                        if chunk == "FINAL_RESPONSE_START":
                            in_final_response = True
                            yield f"data: {json.dumps({'type': 'status', 'message': '✅ Resume search complete, generating final response...', 'replace': True})}\n\n"
                            await asyncio.sleep(0)  # Flush event loop
                            continue
                        
                        # Limit chunk size to prevent socket issues
                        if len(chunk) > 1000:
                            chunk = chunk[:1000] + "..."
                        
                        # Determine chunk type based on content and mode
                        chunk_type = 'response' if in_final_response else 'chunk'
                        yield f"data: {json.dumps({'type': chunk_type, 'text': chunk})}\n\n"
                        await asyncio.sleep(0)  # Flush event loop immediately after each chunk
                        chunk_count += 1
                        
                        # Send heartbeat every 15 seconds to prevent timeouts
                        current_time = asyncio.get_event_loop().time()
                        if current_time - last_heartbeat > 15:
                            yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                            await asyncio.sleep(0)
                            last_heartbeat = current_time
                        
                        # Prevent too many chunks
                        if chunk_count > 1000:
                            yield f"data: {json.dumps({'type': 'status', 'message': '⚠️ Response truncated due to length', 'replace': True})}\n\n"
                            await asyncio.sleep(0)
                            break
                            
                    except Exception as chunk_error:
                        # Handle individual chunk errors
                        yield f"data: {json.dumps({'type': 'error', 'message': f'Chunk error: {str(chunk_error)}'})}\n\n"
                        await asyncio.sleep(0)
                        break
            
            # Send completion signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            await asyncio.sleep(0)  # Final flush
            
        except GeneratorExit:
            # Client disconnected
            return
        except Exception as e:
            try:
                error_msg = f"Error during resume search: {str(e)}"
                yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                await asyncio.sleep(0)
            except:
                # If we can't even send the error, just return
                return
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


# -------------------- TTS Endpoint --------------------

@app.get("/api/test-stream")
async def test_stream_endpoint():
    """Simple test endpoint to verify SSE streaming works without buffering"""
    async def generate_test_stream():
        try:
            for i in range(10):
                yield f"data: {json.dumps({'type': 'test', 'message': f'Test chunk {i+1}/10', 'timestamp': asyncio.get_event_loop().time()})}\n\n"
                await asyncio.sleep(0)  # Flush event loop
                await asyncio.sleep(0.5)  # 500ms delay between chunks
            
            yield f"data: {json.dumps({'type': 'done', 'message': 'Test completed successfully!'})}\n\n"
            await asyncio.sleep(0)
            
        except GeneratorExit:
            return
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Test error: {str(e)}'})}\n\n"
            await asyncio.sleep(0)
    
    return StreamingResponse(
        generate_test_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",
        }
    )

@app.post("/api/tts")
async def tts_endpoint(request: TTSRequest):
    """Convert text to speech using ElevenLabs and return MP3 bytes."""
    try:
        audio_bytes = get_voice_bytes(request.text)
        return Response(content=audio_bytes, media_type="audio/mpeg", headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e:
        # Log full traceback on server for debugging
        import traceback, logging
        logging.error("TTS generation failed", exc_info=True)
        error_detail = {
            "error": str(e),
            "detail": traceback.format_exc(),
        }
        return JSONResponse(content=error_detail, status_code=500, headers={"Access-Control-Allow-Origin": "*"})

# -------------------- Streaming TTS Endpoints --------------------

@app.post("/api/tts/stream/start")
async def start_tts_stream(request: TTSStreamRequest):
    """Start streaming TTS generation"""
    try:
        session_id = request.session_id or str(uuid.uuid4())
        
        return JSONResponse(
            content={"session_id": session_id, "message": "TTS stream ready"}, 
            headers={"Access-Control-Allow-Origin": "*"}
        )
        
    except Exception as e:
        import traceback, logging
        logging.error("TTS stream start failed", exc_info=True)
        error_detail = {
            "error": str(e),
            "detail": traceback.format_exc(),
        }
        return JSONResponse(content=error_detail, status_code=500, headers={"Access-Control-Allow-Origin": "*"})

@app.get("/api/tts/stream/{session_id}")
async def stream_tts_audio(session_id: str, text: str):
    """Stream TTS audio with progress tracking"""
    
    async def generate_audio_stream():
        try:
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': '🎵 Generating speech...', 'session_id': session_id})}\n\n"
            await asyncio.sleep(0)
            
            total_chunks = 0
            
            # Stream audio from TTS service
            async for chunk in tts_streaming_service.generate_audio_stream(session_id, text):
                if chunk:
                    try:
                        # Convert bytes to base64 for JSON transmission
                        import base64
                        chunk_b64 = base64.b64encode(chunk).decode('utf-8')
                        
                        # Send audio chunk
                        yield f"data: {json.dumps({'type': 'audio_chunk', 'data': chunk_b64, 'chunk_id': total_chunks, 'session_id': session_id})}\n\n"
                        await asyncio.sleep(0)
                        
                        total_chunks += 1
                        
                        # Send progress update every 10 chunks
                        if total_chunks % 10 == 0:
                            yield f"data: {json.dumps({'type': 'progress', 'chunks_sent': total_chunks, 'session_id': session_id})}\n\n"
                            await asyncio.sleep(0)
                        
                    except Exception as chunk_error:
                        yield f"data: {json.dumps({'type': 'error', 'message': f'Audio chunk error: {str(chunk_error)}', 'session_id': session_id})}\n\n"
                        await asyncio.sleep(0)
                        break
            
            # Get final audio info
            audio_info = tts_streaming_service.get_audio_info(session_id)
            
            # Send completion signal with audio metadata
            yield f"data: {json.dumps({'type': 'complete', 'total_chunks': total_chunks, 'session_id': session_id, 'audio_info': audio_info})}\n\n"
            await asyncio.sleep(0)
            
        except GeneratorExit:
            return
        except Exception as e:
            try:
                error_msg = f"Error during TTS streaming: {str(e)}"
                yield f"data: {json.dumps({'type': 'error', 'message': error_msg, 'session_id': session_id})}\n\n"
                await asyncio.sleep(0)
            except:
                return
    
    return StreamingResponse(
        generate_audio_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )

@app.get("/api/tts/audio/{session_id}")
async def get_complete_audio(session_id: str):
    """Get complete audio file for a session"""
    try:
        audio_data = tts_streaming_service.get_complete_audio(session_id)
        
        if not audio_data:
            return JSONResponse(
                content={"error": "Audio session not found or not ready"}, 
                status_code=404, 
                headers={"Access-Control-Allow-Origin": "*"}
            )
        
        return Response(
            content=audio_data, 
            media_type="audio/mpeg", 
            headers={
                "Access-Control-Allow-Origin": "*",
                "Content-Length": str(len(audio_data))
            }
        )
        
    except Exception as e:
        return JSONResponse(
            content={"error": str(e)}, 
            status_code=500, 
            headers={"Access-Control-Allow-Origin": "*"}
        )

@app.get("/api/tts/info/{session_id}")
async def get_audio_info(session_id: str):
    """Get audio session information"""
    try:
        audio_info = tts_streaming_service.get_audio_info(session_id)
        
        if not audio_info:
            return JSONResponse(
                content={"error": "Audio session not found"}, 
                status_code=404, 
                headers={"Access-Control-Allow-Origin": "*"}
            )
        
        return JSONResponse(
            content=audio_info, 
            headers={"Access-Control-Allow-Origin": "*"}
        )
        
    except Exception as e:
        return JSONResponse(
            content={"error": str(e)}, 
            status_code=500, 
            headers={"Access-Control-Allow-Origin": "*"}
        )

@app.delete("/api/tts/{session_id}")
async def cleanup_tts_session(session_id: str):
    """Clean up TTS session"""
    try:
        tts_streaming_service.cleanup_session(session_id)
        return JSONResponse(
            content={"message": "TTS session cleaned up"}, 
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        return JSONResponse(
            content={"error": str(e)}, 
            status_code=500, 
            headers={"Access-Control-Allow-Origin": "*"}
        )

# -------------------- Gemini API Endpoints --------------------

@app.post("/api/gemini/chat/create")
async def create_gemini_chat(request: GeminiChatRequest):
    """Create a new Gemini chat session"""
    try:
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # Create chat session using the improved service
        result = gemini_service.create_chat(session_id, request.system_instruction)
        
        if not result:
            return JSONResponse(
                content={"error": "Failed to create chat session - check if GEMINI_API_KEY is configured"}, 
                status_code=500, 
                headers={"Access-Control-Allow-Origin": "*"}
            )
        
        return JSONResponse(
            content={"session_id": session_id}, 
            headers={"Access-Control-Allow-Origin": "*"}
        )
        
    except Exception as e:
        import traceback, logging
        logging.error("Gemini chat creation failed", exc_info=True)
        error_detail = {
            "error": str(e),
            "detail": traceback.format_exc(),
        }
        return JSONResponse(content=error_detail, status_code=500, headers={"Access-Control-Allow-Origin": "*"})

@app.get("/api/gemini/chat/stream")
async def gemini_chat_stream(session_id: str, message: str, request: Request, _=Depends(smart_rate_limit)):
    """Stream Gemini chat response with no buffering"""
    
    async def generate_stream():
        try:
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': '🤖 Gemini is thinking...', 'replace': False})}\n\n"
            await asyncio.sleep(0)
            
            chunk_count = 0
            current_text = ""
            
            # Stream response from improved Gemini service
            async for chunk in gemini_service.send_message_stream(session_id, message):
                if chunk:
                    try:
                        # Check for error messages
                        if chunk.startswith("Error:"):
                            yield f"data: {json.dumps({'type': 'error', 'message': chunk})}\n\n"
                            await asyncio.sleep(0)
                            break
                        
                        current_text += chunk
                        
                        # Send chunk immediately without buffering
                        yield f"data: {json.dumps({'type': 'response', 'text': chunk})}\n\n"
                        await asyncio.sleep(0)  # Force immediate flush
                        
                        chunk_count += 1
                        
                        # Prevent too many chunks (safety)
                        if chunk_count > 10000:
                            yield f"data: {json.dumps({'type': 'status', 'message': '⚠️ Response truncated due to length', 'replace': True})}\n\n"
                            await asyncio.sleep(0)
                            break
                            
                    except Exception as chunk_error:
                        yield f"data: {json.dumps({'type': 'error', 'message': f'Chunk error: {str(chunk_error)}'})}\n\n"
                        await asyncio.sleep(0)
                        break
            
            # Send completion signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            await asyncio.sleep(0)
            
        except GeneratorExit:
            return
        except Exception as e:
            try:
                error_msg = f"Error during Gemini chat: {str(e)}"
                yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                await asyncio.sleep(0)
            except:
                return
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",  # Disable nginx buffering for no-stream buffering
        }
    )

@app.post("/api/gemini/chat/message")
async def send_gemini_message(request: GeminiMessageRequest):
    """Send message to Gemini chat (non-streaming)"""
    try:
        response = gemini_service.send_message_sync(request.session_id, request.message)
        
        if response.startswith("Error:"):
            return JSONResponse(
                content={"error": response}, 
                status_code=400, 
                headers={"Access-Control-Allow-Origin": "*"}
            )
        
        return JSONResponse(
            content={"response": response}, 
            headers={"Access-Control-Allow-Origin": "*"}
        )
        
    except Exception as e:
        import traceback, logging
        logging.error("Gemini message failed", exc_info=True)
        error_detail = {
            "error": str(e),
            "detail": traceback.format_exc(),
        }
        return JSONResponse(content=error_detail, status_code=500, headers={"Access-Control-Allow-Origin": "*"})

@app.delete("/api/gemini/chat/{session_id}")
async def delete_gemini_chat(session_id: str):
    """Delete a Gemini chat session"""
    try:
        gemini_service.delete_chat(session_id)
        return JSONResponse(
            content={"message": "Chat session deleted"}, 
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        return JSONResponse(
            content={"error": str(e)}, 
            status_code=500, 
            headers={"Access-Control-Allow-Origin": "*"}
        )

# -------------------- Rate Limiting Endpoints --------------------

@app.get("/api/rate-limit/usage")
async def get_usage_stats(request: Request):
    """Get current rate limit usage for the user"""
    try:
        # Get user identifier
        identifier = await who_am_i(request)
        
        # Get usage stats
        current_usage, limit = await get_user_usage(identifier)
        
        # Determine user type
        is_authenticated = not identifier.startswith("ip:")
        user_type = "member" if is_authenticated else "guest"
        
        return JSONResponse(
            content={
                "current_usage": current_usage,
                "limit": limit,
                "remaining": max(0, limit - current_usage),
                "user_type": user_type,
                "identifier": identifier
            },
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        return JSONResponse(
            content={"error": str(e)}, 
            status_code=500, 
            headers={"Access-Control-Allow-Origin": "*"}
        )
