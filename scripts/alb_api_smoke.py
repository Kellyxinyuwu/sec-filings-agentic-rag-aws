#!/usr/bin/env python3
"""
Phase 5 — smoke /health, /retrieve, /chat via ALB (Step 6+).

用法（repo 根）：
    python scripts/alb_api_smoke.py
    python scripts/alb_api_smoke.py --retrieve-only
    python scripts/alb_api_smoke.py --chat-only
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

import boto3
from botocore.exceptions import ClientError

DEFAULT_REGION = "us-east-1"
STACK_NAME = "SecRagStack"


def _alb_url(cfn, stack_name: str) -> str:
    resp = cfn.describe_stacks(StackName=stack_name)
    outputs = {o["OutputKey"]: o["OutputValue"] for o in resp["Stacks"][0].get("Outputs", [])}
    url = outputs.get("AlbUrl", "").strip()
    if not url:
        dns = outputs.get("AlbDnsName", "").strip()
        url = f"http://{dns}" if dns else ""
    if not url:
        raise ValueError(f"AlbUrl not in stack {stack_name}")
    return url.rstrip("/")


def _curl_json(method: str, url: str, body: dict | None = None, *, timeout: int = 120) -> tuple[int, str, int]:
    cmd = ["curl", "-s", "--max-time", str(timeout), "-w", "\n__HTTP_CODE__:%{http_code}", "-X", method, url]
    if body is not None:
        cmd.extend(["-H", "Content-Type: application/json", "-d", json.dumps(body)])
    cp = subprocess.run(cmd, capture_output=True, text=True)
    raw = cp.stdout if cp.stdout else cp.stderr
    http_code = 0
    if "__HTTP_CODE__:" in raw:
        body_text, _, code_part = raw.rpartition("\n__HTTP_CODE__:")
        http_code = int(code_part.strip() or "0")
        raw = body_text
    if cp.returncode != 0 and http_code == 0:
        return cp.returncode, raw, http_code
    if http_code and http_code >= 400:
        return 1, raw or f"HTTP {http_code}", http_code
    return 0, raw, http_code


def main() -> int:
    parser = argparse.ArgumentParser(description="ALB /health + /retrieve smoke")
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--stack", default=STACK_NAME)
    parser.add_argument("--retrieve-only", action="store_true")
    parser.add_argument("--chat-only", action="store_true")
    parser.add_argument("--skip-retrieve", action="store_true", help="with default run: health + chat only")
    parser.add_argument("--query", default="risk factors")
    parser.add_argument("--ticker", default="AAPL")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    cfn = boto3.client("cloudformation", region_name=args.region)
    try:
        base = _alb_url(cfn, args.stack)
    except (ClientError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"ALB: {base}")

    if not args.retrieve_only and not args.chat_only:
        code, body, http = _curl_json("GET", f"{base}/health")
        if code != 0:
            print(f"FAIL /health (HTTP {http}): {body}", file=sys.stderr)
            return code
        print("/health OK:")
        try:
            print(json.dumps(json.loads(body), indent=2))
        except json.JSONDecodeError:
            print(body)

    if not args.chat_only and not args.skip_retrieve:
        code, body, http = _curl_json(
            "POST",
            f"{base}/retrieve",
            {"query": args.query, "ticker": args.ticker, "top_k": args.top_k},
        )
        if code != 0:
            print(f"FAIL /retrieve (HTTP {http}): {body}", file=sys.stderr)
            print("Step 6: deploy CDK + python scripts/aoss_grant_task_role.py", file=sys.stderr)
            return code

        print("/retrieve OK:")
        try:
            data = json.loads(body)
            chunks = data.get("chunks") or []
            if not chunks:
                print("WARN: empty chunks", file=sys.stderr)
                return 1
            print(f"OK: {len(chunks)} chunk(s); top id={chunks[0].get('chunk_id', '?')}")
        except json.JSONDecodeError:
            print(body)

    if args.retrieve_only:
        return 0

    chat_query = "What are the main risk factors?"
    code, body, http = _curl_json(
        "POST",
        f"{base}/chat",
        {"query": chat_query, "ticker": args.ticker},
        timeout=180,
    )
    if code != 0:
        print(f"FAIL /chat (HTTP {http}): {body}", file=sys.stderr)
        print("Step 7: secrets_sync_mantle.py + cdk deploy", file=sys.stderr)
        return code

    print("/chat OK:")
    try:
        data = json.loads(body)
        evidence = data.get("evidence") or []
        steps = data.get("agent_steps") or []
        print(f"  plan.intent: {data.get('plan', {}).get('intent')}")
        print(f"  evidence: {len(evidence)} chunk(s)")
        if steps:
            print(f"  verifier: {steps[-1].get('detail')}")
        if not evidence:
            print("WARN: empty evidence", file=sys.stderr)
            return 1
        print("OK: chat returned grounded evidence")
    except json.JSONDecodeError:
        print(body)

    return 0


if __name__ == "__main__":
    sys.exit(main())
