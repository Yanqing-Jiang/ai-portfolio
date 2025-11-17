from pathlib import Path
path = Path('backend/tests/analytics/test_web_retriever_adapter.py').resolve()
for i in range(4):
    print(i, path.parents[i])
