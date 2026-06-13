#!/usr/bin/env python3
"""
Phase 5 — smoke /health and /retrieve via ALB (Step 6+).

用法（repo 根）：
    python scripts/alb_api_smoke.py
    python scripts/alb_api_smoke.py --retrieve-only
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


def _curl_json(method: str, url: str, body: dict | None = None) -> tuple[int, str]:
    cmd = ["curl", "-sf", "-X", method, url]
    if body is not None:
        cmd.extend(["-H", "Content-Type: application/json", "-d", json.dumps(body)])
    cp = subprocess.run(cmd, capture_output=True, text=True)
    return cp.returncode, cp.stdout if cp.returncode == 0 else (cp.stderr or cp.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description="ALB /health + /retrieve smoke")
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--stack", default=STACK_NAME)
    parser.add_argument("--retrieve-only", action="store_true")
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

    if not args.retrieve_only:
        code, body = _curl_json("GET", f"{base}/health")
        if code != 0:
            print(f"FAIL /health: {body}", file=sys.stderr)
            return code
        print("/health OK:")
        try:
            print(json.dumps(json.loads(body), indent=2))
        except json.JSONDecodeError:
            print(body)

    code, body = _curl_json(
        "POST",
        f"{base}/retrieve",
        {"query": args.query, "ticker": args.ticker, "top_k": args.top_k},
    )
    if code != 0:
        print(f"FAIL /retrieve: {body}", file=sys.stderr)
        print("Step 6: deploy CDK + python scripts/aoss_grant_task_role.py", file=sys.stderr)
        return code

    print("/retrieve OK:")
    try:
        data = json.loads(body)
        print(json.dumps(data, indent=2))
        chunks = data.get("chunks") or []
        if not chunks:
            print("WARN: empty chunks — index empty or AOSS policy not propagated yet", file=sys.stderr)
            return 1
        print(f"OK: {len(chunks)} chunk(s); top id={chunks[0].get('chunk_id', '?')}")
    except json.JSONDecodeError:
        print(body)

    return 0


if __name__ == "__main__":
    sys.exit(main())
