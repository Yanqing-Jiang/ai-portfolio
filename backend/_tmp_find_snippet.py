# -*- coding: utf-8 -*-
import os, asyncio, json, sys
from pathlib import Path
from dotenv import load_dotenv
from analytics.services.response_search import perform_response_search

env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path, override=False)

QUERIES = [
  "NVIDIA data center revenue 2025 site:reuters.com",
  "AMD MI300 2025 hyperscaler deployments site:reuters.com OR site:bloomberg.com",
  "Microsoft Copilot+ PC launch 2025 site:theverge.com OR site:blogs.microsoft.com",
  "Tesla Q2 2025 delivery results site:tesla.com OR site:reuters.com",
]

async def run_one(q: str):
    res = await perform_response_search(q, session_id='cli-scan')
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
    print(json.dumps(out, indent=2), flush=True)
    return out

async def main():
    for q in QUERIES:
        print("\n=== LIVE QUERY ===\n" + q, flush=True)
        out = await run_one(q)
        if out['snippets_count'] > 0:
            break

if __name__ == '__main__':
    asyncio.run(main())