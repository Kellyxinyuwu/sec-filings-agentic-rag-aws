#!/usr/bin/env python3
"""
Phase 4 Step 3 — create k-NN index on OpenSearch Serverless.

Prereqs (AWS console — see docs/PHASE_4.md Step 3):
  - VECTORSEARCH collection active
  - Data access policy allows dev-kelly on collection + index
  - Network policy allows your IP (or public for dev)

.env:
  OPENSEARCH_ENDPOINT=https://xxxx.us-east-1.aoss.amazonaws.com
  OPENSEARCH_INDEX=sec-chunks   # default

Usage (repo root):
    python scripts/opensearch_create_index.py
    python scripts/opensearch_create_index.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.aws import get_opensearch_client, require_opensearch_endpoint  # noqa: E402
from app.config import settings  # noqa: E402
from app.opensearch_schema import build_index_body, index_exists  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create OpenSearch k-NN index (Step 3)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print index body JSON only; do not call AWS",
    )
    args = parser.parse_args()

    host = settings.opensearch_endpoint.strip()
    index = settings.opensearch_index
    body = build_index_body()

    if host:
        print(f"Endpoint host: {require_opensearch_endpoint()}")
    else:
        print("Endpoint host: (OPENSEARCH_ENDPOINT not set)")
    print(f"Index: {index}")
    print(f"Vector dimension: {settings.embedding_dimensions}")

    if args.dry_run:
        print("\n--- index body (dry-run) ---")
        print(json.dumps(body, indent=2))
        return 0

    if not host:
        print("OPENSEARCH_ENDPOINT is empty — set it in .env after creating the collection.")
        return 1

    client = get_opensearch_client()

    if index_exists(client, index):
        print(f"OK: index '{index}' already exists — nothing to do")
        return 0

    print(f"Creating index '{index}' ...")
    client.indices.create(index=index, body=body)
    print(f"OK: created index '{index}'")

    # Confirm mapping
    mapping = client.indices.get_mapping(index=index)
    props = mapping[index]["mappings"]["properties"]
    emb = props.get("embedding", {})
    print(f"embedding.type={emb.get('type')}, dimension={emb.get('dimension')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
