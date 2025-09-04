import argparse
import os
from .qdrant_client import ingest_courses_csv, search_qdrant


def main():
    parser = argparse.ArgumentParser(description="Course metadata CSV → Qdrant utilities")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ingest = sub.add_parser("ingest", help="Ingest CSV rows into Qdrant")
    p_ingest.add_argument("--file", required=True, help="Path to CSV file")
    p_ingest.add_argument("--collection", required=True, help="Qdrant collection name")
    p_ingest.add_argument("--org", required=False, help="Optional org_code for Mongo tracking")

    p_search = sub.add_parser("search", help="Semantic search over a collection")
    p_search.add_argument("--collection", required=True, help="Qdrant collection name")
    p_search.add_argument("--query", required=True, help="Search query text")
    p_search.add_argument("--k", type=int, default=5, help="Top-k results")

    args = parser.parse_args()

    if args.cmd == "ingest":
        file_hash = ingest_courses_csv(args.file, args.collection, org_code=args.org)
        print(f"Ingested '{args.file}' → collection='{args.collection}', file_hash={file_hash}")
    elif args.cmd == "search":
        results = search_qdrant(args.query, args.collection, top_k=args.k)
        for i, r in enumerate(results, start=1):
            meta = r.get("payload", {}).get("metadata", {})
            text = r.get("payload", {}).get("text", "")
            title = meta.get("course_name") or text.splitlines()[0][:80]
            print(f"[{i}] score={r['score']:.4f} id={r['id']} title={title}")
    else:
        parser.error("Unknown command")


if __name__ == "__main__":
    # Validate required env vars
    if not os.getenv("QDRANT_URL"):
        print("[WARN] QDRANT_URL not set; default client may fail to connect.")
    if not os.getenv("OPENAI_API_KEY"):
        print("[WARN] OPENAI_API_KEY not set; embedding calls will fail.")
    main()

