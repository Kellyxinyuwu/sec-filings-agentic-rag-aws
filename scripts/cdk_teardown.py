#!/usr/bin/env python3
"""
Phase 5 Step 10 — teardown SecRagStack (save AWS cost after demo).

默认只打印步骤；加 --destroy 才真正跑 cdk destroy。

用法（repo 根）：
    python scripts/cdk_teardown.py
    python scripts/cdk_teardown.py --destroy
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INFRA_DIR = REPO_ROOT / "infra"
STACK_NAME = "SecRagStack"


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 5 CDK teardown guide + optional destroy")
    parser.add_argument(
        "--destroy",
        action="store_true",
        help="Run cdk destroy SecRagStack (removes ECS, ALB, log group; not ECR image or Phase 4 data)",
    )
    args = parser.parse_args()

    print("Phase 5 teardown — SecRagStack")
    print()
    print("CDK destroy removes:")
    print("  - ECS Fargate service + task definition")
    print("  - Application Load Balancer + target group")
    print("  - CloudWatch log group /ecs/sec-rag-api")
    print("  - IAM roles created by the stack")
    print()
    print("NOT removed by cdk destroy (clean up separately if needed):")
    print("  - ECR image sec-rag-api:latest (Console or lifecycle policy)")
    print("  - Secrets Manager sec-rag/mantle-api-key")
    print("  - Phase 4 OpenSearch collection (largest ongoing cost)")
    print("  - Phase 4 S3 bucket filings/")
    print()
    print("Commands:")
    print("  eval \"$(python scripts/cdk_env.py)\"")
    print(f"  cd infra && cdk destroy {STACK_NAME}")
    print()
    print("After stack delete — optional Phase 4 savings:")
    print("  - OpenSearch Serverless: delete collection kelly-sec-rag-vectors")
    print("  - S3: empty/delete bucket kelly-sec-rag-filings-wxy")
    print("  - Secrets: delete sec-rag/mantle-api-key if rotating keys")

    if not args.destroy:
        print("\n(dry-run — pass --destroy to execute)")
        return 0

    print("\nRunning cdk destroy...")
    cmd = ["cdk", "destroy", STACK_NAME, "--force"]
    print("+", " ".join(cmd))
    return subprocess.run(cmd, cwd=INFRA_DIR, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
