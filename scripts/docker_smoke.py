#!/usr/bin/env python3
"""
Phase 5 Step 1 — 本地 Docker smoke 辅助脚本（可选）

在宿主机跑（不是容器里）：
    python scripts/docker_smoke.py
    python scripts/docker_smoke.py --base-url http://127.0.0.1:8000

前提：你已经 docker run 起来了，且 --env-file .env + 挂载 ~/.aws（OpenSearch 需要）。

这个脚本不启动 Docker，只 curl 式检查 /health 是否 200。
"""

from __future__ import annotations

import argparse
import http.client
import json
import sys
import urllib.error
import urllib.request


def fetch_health(base_url: str) -> dict:
    """GET /health，返回 JSON dict；失败则抛异常。"""
    url = f"{base_url.rstrip('/')}/health"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test containerized API /health")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Docker 映射端口（默认 8000，与 Dockerfile EXPOSE 一致）",
    )
    args = parser.parse_args()

    print(f"Checking {args.base_url}/health ...")
    try:
        data = fetch_health(args.base_url)
    except (urllib.error.URLError, ConnectionError, http.client.RemoteDisconnected) as exc:
        reason = getattr(exc, "reason", exc)
        print(f"FAIL: cannot reach API — {reason}")
        print(
            "Hints:\n"
            "  1. cd sec-filings-agentic-rag-aws  (script lives under scripts/)\n"
            "  2. docker rm -f sec-rag-api-smoke 2>/dev/null\n"
            "  3. docker run --rm -p 127.0.0.1:8000:8000 --env-file .env "
            '-v "$HOME/.aws:/root/.aws:ro" --name sec-rag-api-smoke sec-rag-api:local\n'
            "  4. docker ps  →  PORTS must show 127.0.0.1:8000->8000/tcp\n"
            "  5. docker logs sec-rag-api-smoke  if uvicorn crashed"
        )
        return 1

    print(json.dumps(data, indent=2))
    if data.get("status") != "ok":
        print("FAIL: status is not ok")
        return 1

    print("OK: container health check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
