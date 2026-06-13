#!/usr/bin/env python3
"""
Phase 5 Step 3 — 用 boto3 创建 ECR 仓库（CDK deploy 权限不足时的备选）

若 `cdk deploy` 因 IAM 失败，但账号已给 ecr:CreateRepository，可：

    python scripts/ensure_ecr_repo.py

若也报 AccessDeniedException，需要在 IAM 给 dev-kelly 加 ECR 权限（见 docs/PHASE_5.md Step 3）。
"""

from __future__ import annotations

import argparse
import json
import sys

import boto3
from botocore.exceptions import ClientError

DEFAULT_REGION = "us-east-1"
DEFAULT_REPOSITORY = "sec-rag-api"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create ECR repo sec-rag-api if missing")
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    args = parser.parse_args()

    ecr = boto3.client("ecr", region_name=args.region)
    try:
        resp = ecr.describe_repositories(repositoryNames=[args.repository])
        uri = resp["repositories"][0]["repositoryUri"]
        print(f"OK: repository already exists: {uri}")
        return 0
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "RepositoryNotFoundException":
            if exc.response.get("Error", {}).get("Code") == "AccessDeniedException":
                print(
                    "FAIL: no ecr:DescribeRepositories permission.\n"
                    "Ask admin to attach ECR policy (see PHASE_5.md Step 3 IAM).",
                    file=sys.stderr,
                )
                return 1
            raise

    try:
        resp = ecr.create_repository(repositoryName=args.repository)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "AccessDeniedException":
            print(
                "FAIL: no ecr:CreateRepository permission for dev-kelly.\n"
                "Options:\n"
                "  1. IAM admin attaches policy in PHASE_5.md Step 3\n"
                "  2. Admin creates repo 'sec-rag-api' in Console → ECR\n"
                "  3. Fix CDK IAM (ssm:GetParameter + CloudFormation) and cdk deploy",
                file=sys.stderr,
            )
            return 1
        raise

    repo = resp["repository"]
    print(json.dumps({"repositoryUri": repo["repositoryUri"], "repositoryArn": repo["repositoryArn"]}, indent=2))
    print(f"OK: created {repo['repositoryUri']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
