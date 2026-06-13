#!/usr/bin/env python3
"""
Phase 5 Step 7 — sync MANTLE_API_KEY from .env to AWS Secrets Manager.

ECS task reads the secret at runtime (not from CDK context / CloudFormation plain env).

用法（repo 根，deploy 前）：
    python scripts/secrets_sync_mantle.py
    python scripts/secrets_sync_mantle.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / ".env"
DEFAULT_REGION = "us-east-1"
DEFAULT_SECRET_NAME = "sec-rag/mantle-api-key"


def parse_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip("'\"")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync MANTLE_API_KEY to Secrets Manager")
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--secret-name", default=DEFAULT_SECRET_NAME)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env = parse_dotenv(args.env_file)
    api_key = env.get("MANTLE_API_KEY", "").strip()
    if not api_key:
        print(f"FAIL: MANTLE_API_KEY empty in {args.env_file}", file=sys.stderr)
        return 1

    print(f"Secret: {args.secret_name}")
    print(f"Source: {args.env_file} (MANTLE_API_KEY len={len(api_key)})")

    if args.dry_run:
        print("(dry-run — no AWS call)")
        return 0

    sm = boto3.client("secretsmanager", region_name=args.region)
    try:
        sm.describe_secret(SecretId=args.secret_name)
        sm.put_secret_value(SecretId=args.secret_name, SecretString=api_key)
        print(f"OK: updated secret {args.secret_name}")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code != "ResourceNotFoundException":
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        sm.create_secret(
            Name=args.secret_name,
            Description="Bedrock Mantle API key for sec-rag-api ECS task",
            SecretString=api_key,
        )
        print(f"OK: created secret {args.secret_name}")

    print("Next: python scripts/cdk_ecs_context.py --deploy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
