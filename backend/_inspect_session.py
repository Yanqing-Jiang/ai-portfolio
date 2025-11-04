import asyncio
from analytics.core.session_state import get_session_state_repository

async def main():
    repo = get_session_state_repository()
    keys = []
    for attr in ('store', '_store'):
        if hasattr(repo, attr):
            store = getattr(repo, attr)
            if isinstance(store, dict):
                keys.extend(list(store.keys()))
    uniq = []
    for sid in keys:
        if sid not in uniq:
            uniq.append(sid)
    print('sessions:', uniq)
    if not uniq:
        return
    sid = uniq[-1]
    snapshot = await repo.load(sid)
    if not snapshot:
        print('no snapshot for', sid)
        return
    print('session_id:', sid)
    print('last_query:', snapshot.last_query)
    print('last_revision_directive:', snapshot.last_revision_directive)
    analytics = (snapshot.tool_cache or {}).get('analytics')
    if analytics:
        print('analytics keys:', analytics.keys())
        rev = analytics.get('revision_snapshot') or {}
        print('revision_snapshot keys:', rev.keys())

asyncio.run(main())
