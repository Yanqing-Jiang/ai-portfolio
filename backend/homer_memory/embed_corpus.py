from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from homer_memory.embeddings import embed_texts_sync  # type: ignore
    from homer_memory.search import CORPUS_PATH  # type: ignore
else:  # pragma: no cover
    from .embeddings import embed_texts_sync
    from .search import CORPUS_PATH


def _chunks(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[idx : idx + size] for idx in range(0, len(items), size)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Embed the public Homer memory corpus with Gemini.")
    parser.add_argument("--corpus", type=Path, default=CORPUS_PATH)
    parser.add_argument("--force", action="store_true", help="Regenerate embeddings even when rows already have vectors.")
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    with args.corpus.open("r", encoding="utf-8") as fh:
        corpus = json.load(fh)
    if not isinstance(corpus, list):
        raise SystemExit("corpus.json must be a JSON array")

    pending = [
        row
        for row in corpus
        if args.force or not isinstance(row.get("embedding"), list) or len(row.get("embedding", [])) == 0
    ]
    if not pending:
        print(f"All {len(corpus)} corpus rows already have embeddings.")
        return 0

    start = time.perf_counter()
    completed = 0
    for batch in _chunks(pending, max(1, args.batch_size)):
        texts = [str(row["content"]) for row in batch]
        vectors = embed_texts_sync(texts, task_type="RETRIEVAL_DOCUMENT")
        for row, vector in zip(batch, vectors):
            row["embedding"] = [round(float(v), 7) for v in vector]
            completed += 1
        with args.corpus.open("w", encoding="utf-8") as fh:
            json.dump(corpus, fh, indent=2)
            fh.write("\n")
        print(f"Embedded {completed}/{len(pending)} pending rows")

    elapsed = time.perf_counter() - start
    print(f"Embedded {completed} rows in {elapsed:.1f}s: {args.corpus}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
