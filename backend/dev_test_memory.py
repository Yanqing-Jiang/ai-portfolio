import asyncio
import json
import os
import sys

# Ensure project root is on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Avoid LLM calls for this test to keep it deterministic
os.environ.pop("OPENAI_API_KEY", None)

from backend.analytics_memory.workflow import analytics_memory_workflow


async def main():
    print("[DEV TEST] Starting analytics_memory_workflow test...")
    gen = analytics_memory_workflow(query="How fast is NVDA growing vs industry average")
    i = 0
    async for event in gen:
        print("[DEV TEST] EVENT:", json.dumps(event, default=str))
        i += 1
        if i >= 8:
            break


if __name__ == "__main__":
    asyncio.run(main())

