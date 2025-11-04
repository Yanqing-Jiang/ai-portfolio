import asyncio
import logging
from analytics.flows.workflow import analytics_memory_workflow
from analytics.core.session_state import get_session_state_repository, close_session_state_repository

logging.basicConfig(level=logging.INFO)

async def run_workflow():
    session_id = 'redis-baseline-only'
    repo = get_session_state_repository()
    async for event in analytics_memory_workflow(
        query='AMD vs NVIDIA revenue comparison in the past 5 years?',
        session_id=session_id,
        flow='single-agent',
    ):
        if event.get('event') == 'workflow_complete':
            break
    snapshot = await repo.load(session_id)
    analytics_cache = snapshot.tool_cache.get('analytics') if snapshot else {}
    print('revision snapshot present:', isinstance(analytics_cache, dict) and 'revision_snapshot' in analytics_cache)
    await close_session_state_repository()

asyncio.run(run_workflow())
