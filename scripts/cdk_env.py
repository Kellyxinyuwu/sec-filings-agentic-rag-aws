#!/usr/bin/env python3
"""
Phase 5 — 打印 CDK 用的环境变量（用 boto3，不依赖 aws CLI）

当 `aws sts get-caller-identity` 因 Homebrew Python/pyexpat 报错时，
用这个脚本代替：

    eval "$(python scripts/cdk_env.py)"
    cd infra && cdk bootstrap && cdk deploy

或手动复制输出里的 export 行。
"""

from __future__ import annotations

import sys

import boto3

DEFAULT_REGION = "us-east-1"


def main() -> int:
    region = DEFAULT_REGION
    if len(sys.argv) > 1:
        region = sys.argv[1]

    try:
        ident = boto3.client("sts").get_caller_identity()
    except Exception as exc:
        print(f"# ERROR: boto3 STS failed: {exc}", file=sys.stderr)
        return 1

    account = ident["Account"]
    arn = ident["Arn"]
    print(f"# {arn}")
    print(f"export CDK_DEFAULT_ACCOUNT={account}")
    print(f"export CDK_DEFAULT_REGION={region}")
    print(f"export AWS_REGION={region}")
    print(f"export AWS_DEFAULT_REGION={region}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
