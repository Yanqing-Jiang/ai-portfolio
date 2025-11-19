import asyncio
import json
from analytics.core.session_state import get_session_state_repository

SESSION_ID = "f353c0e8-99d8-4808-9a0c-61a9c96ea90b"

async def main() -> None:
    repo = get_session_state_repository()
    snapshot = await repo.load(SESSION_ID)
    if snapshot is None:
        print("snapshot=None")
        return
    manifest = snapshot.analysis_inputs_manifest if isinstance(snapshot.analysis_inputs_manifest, dict) else {}
    print("manifest=", json.dumps(manifest, indent=2))
    cache = snapshot.tool_cache if isinstance(snapshot.tool_cache, dict) else {}
    preview = cache.get("planner_dataset_preview")
    print("dataset_preview=", json.dumps(preview, indent=2))
    print("last_sql ready?", bool(snapshot.last_sql and snapshot.last_sql.strip()))
    analysis_text = snapshot.last_analysis if isinstance(snapshot.last_analysis, str) else None
    print("last_analysis chars=", len(analysis_text or ""))

asyncio.run(main())
