#!/usr/bin/env python3
"""
Phase 5 Step 8 — read CloudWatch Logs for ECS task (boto3, no aws CLI).

Log group: /ecs/sec-rag-api (from SecRagStack)

用法（repo 根）：
    python scripts/ecs_logs_tail.py
    python scripts/ecs_logs_tail.py --minutes 30
    python scripts/ecs_logs_tail.py --smoke    # curl /health then show new lines
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta

import boto3
from botocore.exceptions import ClientError

DEFAULT_REGION = "us-east-1"
STACK_NAME = "SecRagStack"
DEFAULT_LOG_GROUP = "/ecs/sec-rag-api"


def _stack_outputs(cfn, stack_name: str) -> dict[str, str]:
    resp = cfn.describe_stacks(StackName=stack_name)
    stacks = resp.get("Stacks", [])
    if not stacks:
        return {}
    return {o["OutputKey"]: o["OutputValue"] for o in stacks[0].get("Outputs", [])}


def _log_group_name(cfn, stack_name: str) -> str:
    outputs = _stack_outputs(cfn, stack_name)
    return outputs.get("LogGroupName", "").strip() or DEFAULT_LOG_GROUP


def _fetch_events(
    logs,
    log_group: str,
    *,
    start_ms: int,
    pattern: str = "",
    limit: int = 100,
) -> list[dict]:
    kwargs: dict = {
        "logGroupName": log_group,
        "startTime": start_ms,
        "limit": limit,
        "interleaved": True,
    }
    if pattern:
        kwargs["filterPattern"] = pattern

    events: list[dict] = []
    token = None
    while len(events) < limit:
        if token:
            kwargs["nextToken"] = token
        resp = logs.filter_log_events(**kwargs)
        batch = resp.get("events", [])
        if not batch:
            break
        events.extend(batch)
        token = resp.get("nextToken")
        if not token:
            break
    return events[:limit]


def _print_events(events: list[dict]) -> None:
    if not events:
        print("(no log events in window)")
        return
    for event in events:
        ts = datetime.fromtimestamp(event["timestamp"] / 1000, tz=UTC)
        stream = event.get("logStreamName", "")
        short_stream = stream.split("/")[-1][:12] if stream else "?"
        msg = event.get("message", "").rstrip()
        print(f"{ts:%Y-%m-%d %H:%M:%S}Z [{short_stream}] {msg}")


def _alb_health_curl(cfn, stack_name: str) -> int:
    outputs = _stack_outputs(cfn, stack_name)
    url = outputs.get("AlbUrl", "").strip()
    if not url:
        return 1
    cp = subprocess.run(
        ["curl", "-s", "--max-time", "30", f"{url.rstrip('/')}/health"],
        capture_output=True,
        text=True,
    )
    if cp.returncode != 0:
        print(f"WARN: /health curl failed: {cp.stderr or cp.stdout}", file=sys.stderr)
        return cp.returncode
    print(f"OK: curl {url}/health")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Tail ECS API logs from CloudWatch (boto3)")
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--stack", default=STACK_NAME)
    parser.add_argument("--log-group", default="", help="default: from stack LogGroupName output")
    parser.add_argument("--minutes", type=int, default=15, help="look back N minutes")
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--pattern", default="", help="CloudWatch filter pattern")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="curl ALB /health first, wait, then show logs (proves request → log line)",
    )
    args = parser.parse_args()

    cfn = boto3.client("cloudformation", region_name=args.region)
    logs = boto3.client("logs", region_name=args.region)

    try:
        log_group = args.log_group.strip() or _log_group_name(cfn, args.stack)
    except ClientError as exc:
        print(f"FAIL: CloudFormation: {exc}", file=sys.stderr)
        return 1

    print(f"Log group: {log_group}")
    print(f"Window: last {args.minutes} min")

    start_ms = int((datetime.now(UTC) - timedelta(minutes=args.minutes)).timestamp() * 1000)

    if args.smoke:
        before = _fetch_events(logs, log_group, start_ms=start_ms, limit=1)
        last_ts = before[-1]["timestamp"] if before else start_ms
        _alb_health_curl(cfn, args.stack)
        print("Waiting 8s for log delivery...")
        time.sleep(8)
        start_ms = last_ts

    try:
        events = _fetch_events(
            logs,
            log_group,
            start_ms=start_ms,
            pattern=args.pattern,
            limit=args.limit,
        )
    except ClientError as exc:
        print(f"FAIL: filter_log_events: {exc}", file=sys.stderr)
        return 1

    _print_events(events)

    if args.smoke:
        text = "\n".join(e.get("message", "") for e in events).lower()
        hints = ("uvicorn", "health", "started", "application startup", "get /health")
        if any(h in text for h in hints):
            print("\nOK: CloudWatch shows API / uvicorn activity")
            return 0
        print("\nWARN: no obvious uvicorn/health lines — widen --minutes or check ECS task", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
