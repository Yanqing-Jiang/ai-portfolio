# -*- coding: utf-8 -*-
import os, asyncio, json
from pathlib import Path
from dotenv import load_dotenv
from analytics.services.response_search import perform_response_search
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path, override=False)

QUERIES = [
  "Mercury Research x86 CPU market share Q2 2025 AMD Intel site:anandtech.com OR site:tomshardware.com",
  "Steam hardware survey AMD CPU share 2020..2025 site:store.steampowered.com",
]

async def run_one(q: str):
    res = await perform_response_search(q, session_id='cli-retry2')
    p = res.to_payload()
    out = {
        'query': p.get('query'),
        'search_topic': p.get('search_topic'),
        'model': p.get('model'),
        'latency_ms': p.get('latency_ms'),
        'snippets_count': len(p.get('snippets') or []),
        'snippets': [
            {
                'title': s.get('title'),
                'url': s.get('url') or s.get('display_url'),
                'published_at': s.get('published_at'),
                'excerpt': (s.get('snippet') or '')[:200]
            }
            for s in (p.get('snippets') or [])[:3]
        ]
    }
    print(json.dumps(out, indent=2))

async def main():
    for q in QUERIES:
        print("\n=== RETRY QUERY 2 ===")
        print(q)
        await run_one(q)

if __name__ == '__main__':
    asyncio.run(main())