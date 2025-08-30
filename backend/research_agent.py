import os
from datetime import datetime
from langchain.prompts import PromptTemplate
from langchain.agents import initialize_agent, Tool
from langchain.agents import AgentType
from langchain.chat_models import ChatOpenAI
from langchain.prompts import MessagesPlaceholder
from langchain.memory import ConversationSummaryBufferMemory
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.summarize import load_summarize_chain
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Generator
from bs4 import BeautifulSoup
import requests
import json
from langchain.schema import SystemMessage
from dotenv import load_dotenv
from pathlib import Path
from langchain.callbacks.base import BaseCallbackHandler
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
import threading
import queue
import time

# Ensure .env in backend is loaded regardless of CWD
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)

# Secrets from environment variables
browserless_api_key = os.getenv("BROWSERLESS_API_KEY")
serper_api_key = os.getenv("SERPER_API_KEY")

# Custom streaming callback handler
class ResearchStreamingCallbackHandler(BaseCallbackHandler):
    def __init__(self):
        self.current_step = ""
        self.chunks = []
        self._lock = threading.Lock()
        self._finished = False

    def on_agent_action(self, action, **kwargs):
        """Called when agent is about to take an action"""
        with self._lock:
            if not self._finished:
                tool_name = action.tool
                tool_input = action.tool_input
                if isinstance(tool_input, dict):
                    # For complex inputs, just show the main query
                    input_str = tool_input.get('query', str(tool_input))
                else:
                    input_str = str(tool_input)
                
                # Limit input display length
                if len(input_str) > 100:
                    input_str = input_str[:100] + "..."
                
                # Add a status update that can replace the initial status
                if tool_name == "Search":
                    self.chunks.append(f"STATUS_REPLACE:🔍 Searching for: {input_str}")
                elif tool_name == "scrape_website":
                    # Extract URL for display
                    url = tool_input.get('url', '') if isinstance(tool_input, dict) else ''
                    if url:
                        domain = url.split('/')[2] if len(url.split('/')) > 2 else url
                        self.chunks.append(f"STATUS_REPLACE:📄 Scraping website: {domain}")
                    else:
                        self.chunks.append(f"STATUS_REPLACE:📄 Scraping website content...")
                
                # Add the detailed invocation info as status (not regular chunk)
                invocation_detail = f"STATUS_UPDATE:> Invoking: `{tool_name}` with `{input_str}`"
                self.chunks.append(invocation_detail)

    def on_agent_finish(self, finish, **kwargs):
        """Called when agent finishes"""
        with self._lock:
            if not self._finished:
                # Don't add completion message - let the final output speak for itself
                pass

    def on_chain_start(self, serialized, inputs, **kwargs):
        """Called when a chain starts"""
        with self._lock:
            if not self._finished:
                chain_name = serialized.get("name", "Unknown")
                if chain_name == "AgentExecutor":
                    self.chunks.append("STATUS_REPLACE:🤖 Starting agent execution...")
                    self.chunks.append("STATUS_UPDATE:> Entering new AgentExecutor chain...")
                elif chain_name == "StuffDocumentsChain":
                    self.chunks.append("STATUS_REPLACE:📝 Processing documents...")
                    self.chunks.append("STATUS_UPDATE:> Entering new StuffDocumentsChain chain...")
                elif chain_name == "LLMChain":
                    self.chunks.append("STATUS_REPLACE:💭 Generating response...")
                    self.chunks.append("STATUS_UPDATE:> Entering new LLMChain chain...")
                elif chain_name != "Unknown":
                    self.chunks.append(f"STATUS_UPDATE:> Entering new {chain_name} chain...")

    def on_chain_end(self, outputs, **kwargs):
        """Called when a chain ends"""
        with self._lock:
            if not self._finished:
                # Don't add "Finished chain" messages - they're too noisy
                pass

    def on_tool_start(self, tool, input_str, **kwargs):
        with self._lock:
            if not self._finished:
                # Don't add generic tool messages since we have more specific ones
                pass

    def on_tool_end(self, output, **kwargs):
        with self._lock:
            if not self._finished:
                # Add a completion indicator as status
                self.chunks.append("STATUS_UPDATE:> Tool execution completed.")

    def on_llm_start(self, serialized, prompts, **kwargs):
        with self._lock:
            if not self._finished:
                # Only add this for the final response generation
                self.chunks.append("STATUS_UPDATE:> Generating response...")

    def on_llm_new_token(self, token: str, **kwargs):
        with self._lock:
            if not self._finished and token:
                # Mark that we're now in final response mode
                self.chunks.append("FINAL_RESPONSE_START")
                # Stream individual tokens from the LLM
                self.chunks.append(token)

    def on_text(self, text, **kwargs):
        with self._lock:
            if not self._finished and text and text.strip():
                # Check if this is intermediate agent thought or final output
                if any(text.startswith(phrase) for phrase in ["I need to", "I should", "Let me", "I'll", "Based on"]):
                    # This is likely agent reasoning, put it in status
                    self.chunks.append(f"STATUS_UPDATE:💭 {text}")
                else:
                    # This is likely final output content
                    self.chunks.append("FINAL_RESPONSE_START")
                    self.chunks.append(text)

    def get_chunks(self):
        """Safely get and remove chunks from the queue"""
        with self._lock:
            chunks_to_yield = []
            # Get up to 10 chunks at a time to prevent infinite loops
            for _ in range(min(10, len(self.chunks))):
                if self.chunks:
                    chunks_to_yield.append(self.chunks.pop(0))
            
            for chunk in chunks_to_yield:
                yield chunk
    
    def finish(self):
        """Mark the handler as finished to prevent new chunks"""
        with self._lock:
            self._finished = True
    
    def has_chunks(self):
        """Check if there are chunks available"""
        with self._lock:
            return len(self.chunks) > 0

# 1. Tool for search
def search(query):
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query})
    headers = {
        'X-API-KEY': serper_api_key,
        'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    return response.text

# 2. Tool for scraping
def scrape_website(objective: str, url: str):
    headers = {
        'Cache-Control': 'no-cache',
        'Content-Type': 'application/json',
    }
    data = {"url": url}
    data_json = json.dumps(data)
    post_url = f"https://chrome.browserless.io/content?token={browserless_api_key}"
    response = requests.post(post_url, headers=headers, data=data_json)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, "html.parser")
        text = soup.get_text()
        if len(text) > 10000:
            output = summary(objective, text)
            return output
        else:
            return text
    else:
        return f"HTTP request failed with status code {response.status_code}"

def summary(objective, content):
    llm = ChatOpenAI(temperature=0, model="gpt-4o-mini-2024-07-18", openai_api_key=os.getenv("OPENAI_API_KEY"))
    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n"], chunk_size=10000, chunk_overlap=500)
    docs = text_splitter.create_documents([content])
    summary_chain = load_summarize_chain(
        llm=llm,
        chain_type='stuff',
        verbose=True
    )
    output = summary_chain.run(input_documents=docs, objective=objective)
    return output

class ScrapeWebsiteInput(BaseModel):
    objective: str = Field(description="The objective & task that users give to the agent")
    url: str = Field(description="The url of the website to be scraped")

class ScrapeWebsiteTool(BaseTool):
    name: str = "scrape_website"
    description: str = "useful when you need to get data from a website url, passing both url and objective to the function; DO NOT make up any url, the url should only be from the search results"
    args_schema: Type[BaseModel] = ScrapeWebsiteInput
    def _run(self, objective: str, url: str):
        return scrape_website(objective, url)
    def _arun(self, url: str):
        raise NotImplementedError("error here")

tools = [
    Tool(
        name="Search",
        func=search,
        description="useful for when you need to answer questions about current events, data. You should ask targeted questions"
    ),
    ScrapeWebsiteTool()
]

current_date = datetime.now().strftime('%B %d, %Y')

system_message = SystemMessage(
    content=f"""You are a world class researcher, who can do detailed research on any topic and produce facts based results;
You do not make things up, you will try as hard as possible to gather facts & data to back up the research.

The current date is {current_date}. Make sure you are up to date with the latest information.

Please make sure you complete the objective above with the following rules:
1/ You should do enough research to gather as much information as possible about the objective
2/ If there are url of relevant links & articles, you will scrape it to gather more information
3/ After scraping & search, you should think 'is there any new things i should search & scraping based on the data I collected to increase research quality?' If answer is yes, continue; But don't do this more than 3 iterations
4/ You should not make things up, you should only write facts & data that you have gathered
5/ In the final output, You should include *ALL* reference data & links to back up your research
6/ In the final output, You should include *all* reference data & links to back up your research"""
)

agent_kwargs = {
    "system_message": system_message,
}

def create_agent(streaming=False):
    callbacks = []
    if streaming:
        callbacks.append(ResearchStreamingCallbackHandler())
    
    llm = ChatOpenAI(
        temperature=0, 
        model="gpt-4o-mini-2024-07-18", 
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        streaming=streaming,
        callbacks=callbacks if streaming else None
    )
    
    agent = initialize_agent(
        tools,
        llm,
        agent=AgentType.OPENAI_FUNCTIONS,
        verbose=True,
        agent_kwargs=agent_kwargs,
        callbacks=callbacks if streaming else None,
        max_iterations=3,  # Limit iterations to prevent infinite loops
        early_stopping_method="generate",  # Stop early if needed
        handle_parsing_errors=True  # Handle parsing errors gracefully
    )
    
    return agent, callbacks[0] if streaming else None

def run_research_agent(query: str) -> str:
    agent, _ = create_agent(streaming=False)
    result = agent({"input": query})
    output = result['output']
    return output 

def run_research_agent_stream(query: str) -> Generator[str, None, None]:
    """Stream research agent responses in real-time"""
    agent, callback_handler = create_agent(streaming=True)
    
    try:
        # Start the agent in a separate thread
        
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        agent_finished = threading.Event()
        
        def run_agent():
            try:
                result = agent({"input": query})
                if result and 'output' in result:
                    result_queue.put(result['output'])
                else:
                    result_queue.put("Research completed but no output was generated.")
            except Exception as e:
                exception_queue.put(e)
            finally:
                agent_finished.set()
        
        # Start the agent
        thread = threading.Thread(target=run_agent)
        thread.daemon = True  # Make thread daemon so it doesn't prevent shutdown
        thread.start()
        
        # Track if we've yielded anything to prevent empty streams
        yielded_anything = False
        max_wait_time = 900  # 15 minutes max wait time
        start_time = time.time()
        
        # Stream chunks as they become available
        while not agent_finished.is_set():
            # Check for timeout
            if time.time() - start_time > max_wait_time:
                callback_handler.finish()
                yield "⏰ Request timed out after 5 minutes"
                break
            
            # Check for exceptions
            try:
                if not exception_queue.empty():
                    error = exception_queue.get_nowait()
                    callback_handler.finish()
                    yield f"❌ Error: {str(error)}"
                    break
            except queue.Empty:
                pass
            
            # Yield any available chunks
            try:
                for chunk in callback_handler.get_chunks():
                    if chunk and chunk.strip():  # Only yield non-empty chunks
                        yield chunk
                        yielded_anything = True
            except Exception as e:
                callback_handler.finish()
                yield f"⚠️ Chunk processing error: {str(e)}"
                break
            
            # Small delay to prevent busy waiting
            time.sleep(0.1)
        
        # Wait a bit more for the thread to finish
        thread.join(timeout=5.0)
        callback_handler.finish()
        
        # Process any remaining chunks after agent finishes
        try:
            for chunk in callback_handler.get_chunks():
                if chunk and chunk.strip():
                    yield chunk
                    yielded_anything = True
        except Exception as e:
            yield f"⚠️ Final chunk processing error: {str(e)}"
        
        # Get final result if available
        try:
            if not result_queue.empty():
                final_result = result_queue.get_nowait()
                if final_result and final_result.strip():
                    
                    # Always add a newline before the final output for better formatting
                    yield "\n"
                    
                    # Only yield final result if it's different from streamed content
                    if not yielded_anything:
                        yield final_result
        except queue.Empty:
            pass
        except Exception as e:
            yield f"⚠️ Final result error: {str(e)}"
        
        # Check for any final exceptions
        try:
            if not exception_queue.empty():
                error = exception_queue.get_nowait()
                yield f"❌ Final error: {str(error)}"
        except queue.Empty:
            pass
        
        # Ensure we always yield something
        if not yielded_anything:
            yield "⚠️ No response generated. Please try again."
            
    except Exception as e:
        yield f"💥 Critical error: {str(e)}" 