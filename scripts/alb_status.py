#!/usr/bin/env python3
"""
Phase 5 Step 5 — 从 CloudFormation 读 ALB DNS，curl /health

用法（repo 根）：
    python scripts/alb_status.py
    python scripts/alb_status.py --curl
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


def _stack_outputs(cfn, stack_name: str) -> dict[str, str]:
    resp = cfn.describe_stacks(StackName=stack_name)
    stacks = resp.get("Stacks", [])
    if not stacks:
        return {}
    return {o["OutputKey"]: o["OutputValue"] for o in stacks[0].get("Outputs", [])}


def main() -> int:
    parser = argparse.ArgumentParser(description="ALB DNS from SecRagStack outputs + optional /health curl")
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--stack", default=STACK_NAME)
    parser.add_argument("--curl", action="store_true", help="curl GET /health on ALB URL")
    args = parser.parse_args()

    cfn = boto3.client("cloudformation", region_name=args.region)
    try:
        outputs = _stack_outputs(cfn, args.stack)
    except ClientError as exc:
        print(f"FAIL: describe_stacks({args.stack}): {exc}", file=sys.stderr)
        return 1

    alb_url = outputs.get("AlbUrl", "").strip()
    alb_dns = outputs.get("AlbDnsName", "").strip()
    if not alb_url and alb_dns:
        alb_url = f"http://{alb_dns}"
    if not alb_url:
        print(
            f"FAIL: AlbUrl / AlbDnsName not in stack '{args.stack}' outputs — deploy Step 5 first:\n"
            "  python scripts/cdk_ecs_context.py --deploy",
            file=sys.stderr,
        )
        return 1

    print(f"Stack: {args.stack}")
    print(f"ALB URL: {alb_url}")
    print(f"  curl -s {alb_url}/health")

    stack_phase = outputs.get("StackPhase", "")
    if stack_phase:
        print(f"  StackPhase: {stack_phase}")

    if args.curl:
        cp = subprocess.run(["curl", "-sf", f"{alb_url}/health"], capture_output=True, text=True)
        if cp.returncode != 0:
            print(f"\nFAIL curl: {cp.stderr or cp.stdout}", file=sys.stderr)
            print("Tip: new ALB targets need ~1–2 min; check ECS → service → Events.", file=sys.stderr)
            return cp.returncode
        print("\n/health response:")
        try:
            print(json.dumps(json.loads(cp.stdout), indent=2))
        except json.JSONDecodeError:
            print(cp.stdout)

    return 0


if __name__ == "__main__":
    sys.exit(main())
