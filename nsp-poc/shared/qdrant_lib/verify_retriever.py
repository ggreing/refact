import os
import sys
from typing import List

from qdrant_client import QdrantClient

from .qdrant_client import search_qdrant


def env(name: str, default: str | None = None) -> str:
    v = os.getenv(name, default)
    if v is None:
        print(f"[ERROR] Missing env var: {name}")
        sys.exit(1)
    return v


def main():
    qdrant_url = env("QDRANT_URL")
    collection = env("QDRANT_COLLECTION")

    client = QdrantClient(url=qdrant_url)

    # Basic collection presence and count
    cols = [c.name for c in client.get_collections().collections]
    if collection not in cols:
        print(f"[FAIL] Collection '{collection}' does not exist at {qdrant_url}")
        sys.exit(2)

    try:
        count = client.count(collection_name=collection, exact=True).count
    except Exception:
        # Older clients may not support count; fallback to scroll one
        pts, _ = client.scroll(collection_name=collection, limit=100)
        count = len(pts)

    if count == 0:
        print(f"[FAIL] Collection '{collection}' has 0 points. Ingestion likely failed.")
        sys.exit(3)

    print(f"[OK] Collection '{collection}' ready with {count} points.")

    # Smoke test queries based on provided CSV fields
    queries: List[str] = [
        "플렉스캠 사용법",
        "AI 카메라 활용",
        "클로징 멘트",
        "갤럭시 A 시리즈 가성비"
    ]

    for q in queries:
        results = search_qdrant(q, collection, top_k=3)
        print(f"\nQuery: {q}")
        if not results:
            print("  - No results")
            continue
        for r in results:
            meta = (r.get("payload", {}) or {}).get("metadata", {})
            title = meta.get("course_name")
            cid = meta.get("course_id")
            score = r.get("score")
            print(f"  - score={score:.4f} id={cid} title={title}")


if __name__ == "__main__":
    # Ensure envs are present for embedding/search
    if not os.getenv("OPENAI_API_KEY"):
        print("[WARN] OPENAI_API_KEY not set; search will fail.")
    main()

