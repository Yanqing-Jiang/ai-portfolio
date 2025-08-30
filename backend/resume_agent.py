# resume_agent.py – simplified version without FAISS

import os
from pathlib import Path
from typing import Generator, List, Tuple

from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI

# ---------------------------------------------------------------------------
# Environment loading
# ---------------------------------------------------------------------------
# Always load the .env file that sits next to this script so that API keys are
# available regardless of the working directory.
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)

# ---------------------------------------------------------------------------
# Helper: Load the full text of every .txt resume file in the backend folder.
# ---------------------------------------------------------------------------

def _load_resume_corpus() -> str:
    """Concatenate the contents of all .txt files found in the backend dir."""
    backend_dir = Path(__file__).resolve().parent
    txt_files = list(backend_dir.glob("*.txt"))

    if not txt_files:
        print("Warning: no .txt resume files found in the backend directory.")
        return ""

    parts: List[str] = []
    for txt in txt_files:
        try:
            parts.append(txt.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error reading {txt}: {e}")

    return "\n\n".join(parts)

# Load once at import time
RESUME_CORPUS: str = _load_resume_corpus()

# ---------------------------------------------------------------------------
# Streaming agent
# ---------------------------------------------------------------------------

def run_resume_agent_stream(query: str, chat_history: List[Tuple[str, str]]) -> Generator[str, None, None]:
    """Generate a streamed answer to `query` using the full resume text."""

    if not RESUME_CORPUS:
        yield "STATUS_REPLACE:⚠️ Resume corpus is empty. Please add .txt files to backend folder."
        return

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        yield "STATUS_REPLACE:⚠️ OPENAI_API_KEY is not set. Resume agent disabled."
        return

    # Inform frontend that retrieval step is done (trivial now)
    yield "STATUS_REPLACE:🔍 Reviewing full resume…"

    # Prepare prompt – you can customise wording here
    prompt = (
        "You are a seasoned Human Resources leader helping Yanqing to promote himself.\n"
        "Below is the Yanqing's resume:\n"
        "{resume}\n\n"
        "Here is a question from a potential hiring manager or recruiter:\n"
        "{question}\n\n"
        "Answer questions *concisely*, emphasising quantified achievements, leadership, and impact relevant to the query. Use bullet points when possible. If the question is not related to Yanqing's resume or career, please say 'I'm sorry, I can only answer questions related to Yanqing's resume.'."
    ).format(resume=RESUME_CORPUS, question=query)

    # Signal that we are generating the final answer
    yield "STATUS_REPLACE:💭 Generating final answer…"
    yield "FINAL_RESPONSE_START"

    llm = ChatOpenAI(
        temperature=0.2,
        model="gpt-4o-mini-2024-07-18",
        streaming=True,
        openai_api_key=openai_api_key,
    )

    # Stream response tokens
    for chunk in llm.stream(prompt):
        if chunk.content:
            yield chunk.content

# ---------------------------------------------------------------------------
# Non-streaming helper (used elsewhere for compatibility)
# ---------------------------------------------------------------------------

def run_resume_agent(query: str, chat_history: List[Tuple[str, str]]) -> str:
    """Collect the full response in a single string (non-streaming)."""
    response_parts: List[str] = []
    for part in run_resume_agent_stream(query, chat_history):
        if part in ("FINAL_RESPONSE_START",) or part.startswith("STATUS_"):
            continue  # skip control tokens
        response_parts.append(part)
    return "".join(response_parts) 