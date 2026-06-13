#!/usr/bin/env python3
"""
Phase 5 Step 3 — 构建本地镜像并 push 到 ECR

前提：
  1. Docker 已 build 过 sec-rag-api:local（或本脚本加 --build）
  2. CDK 已 deploy 创建 ECR 仓库：cd infra && cdk deploy
  3. AWS CLI 已登录：aws sts get-caller-identity

用法（repo 根目录）：
    python scripts/ecr_push.py
    python scripts/ecr_push.py --build
    python scripts/ecr_push.py --tag v1 --also-tag latest
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGION = "us-east-1"
DEFAULT_REPOSITORY = "sec-rag-api"
DEFAULT_LOCAL_IMAGE = "sec-rag-api:local"


def run(cmd: list[str], *, check: bool = True, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """跑 shell 命令并打印（学习时看得见每一步）。"""
    print("+", " ".join(cmd))
    return subprocess.run(cmd, check=check, text=True, cwd=cwd)


def get_account_id() -> str:
    sts = boto3.client("sts")
    return sts.get_caller_identity()["Account"]


def default_repository_uri(account_id: str, region: str, repository_name: str) -> str:
    return f"{account_id}.dkr.ecr.{region}.amazonaws.com/{repository_name}"


def get_repository_uri(region: str, repository_name: str, account_id: str) -> str:
    """从 ECR 查仓库 URI；Describe 被拒时用标准 URI 格式（Console 已建仓库时）。"""
    ecr = boto3.client("ecr", region_name=region)
    try:
        resp = ecr.describe_repositories(repositoryNames=[repository_name])
        return resp["repositories"][0]["repositoryUri"]
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "RepositoryNotFoundException":
            print(
                f"FAIL: ECR repository '{repository_name}' not found in {region}.\n"
                "Create it: AWS Console → ECR → Create repository → sec-rag-api"
            )
            sys.exit(1)
        if code == "AccessDeniedException":
            uri = default_repository_uri(account_id, region, repository_name)
            print(
                "WARN: ecr:DescribeRepositories denied — using standard URI:\n"
                f"      {uri}\n"
                "      (OK if you created sec-rag-api in Console)"
            )
            return uri
        raise


def docker_login(region: str) -> None:
    """ECR 登录：get_authorization_token → docker login --password-stdin"""
    ecr = boto3.client("ecr", region_name=region)
    try:
        auth = ecr.get_authorization_token()["authorizationData"][0]
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "AccessDeniedException":
            print(
                "FAIL: ecr:GetAuthorizationToken denied for dev-kelly.\n"
                "Console 建仓库 ≠ push 权限。请 IAM 附加策略（PHASE_5.md Step 3）：\n"
                "  ecr:GetAuthorizationToken, BatchCheckLayerAvailability,\n"
                "  InitiateLayerUpload, UploadLayerPart, CompleteLayerUpload, PutImage\n"
                "或请管理员在 ECR → sec-rag-api → Permissions 给你 push 权限。"
            )
            sys.exit(1)
        raise
    endpoint = auth["proxyEndpoint"]
    decoded = base64.b64decode(auth["authorizationToken"]).decode("utf-8")
    _, password = decoded.split(":", 1)
    print(f"+ docker login --username AWS --password-stdin {endpoint}")
    subprocess.run(
        ["docker", "login", "--username", "AWS", "--password-stdin", endpoint],
        input=password,
        text=True,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build/tag/push sec-rag-api image to ECR")
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--local-image", default=DEFAULT_LOCAL_IMAGE)
    parser.add_argument("--tag", default="latest", help="Primary tag to push")
    parser.add_argument(
        "--also-tag",
        action="append",
        default=[],
        help="Extra tags (e.g. git sha). Can repeat.",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="docker build before push (default --platform linux/amd64 for Fargate)",
    )
    parser.add_argument(
        "--platform",
        default="linux/amd64",
        help="docker build --platform (Mac ARM local smoke can use linux/arm64; ECS Fargate needs linux/amd64)",
    )
    parser.add_argument("--no-login", action="store_true", help="Skip docker login")
    args = parser.parse_args()

    tags = [args.tag, *args.also_tag]
    # 去重保序
    seen: set[str] = set()
    tags = [t for t in tags if not (t in seen or seen.add(t))]

    account_id = get_account_id()
    repo_uri = get_repository_uri(args.region, args.repository, account_id)
    print(f"Account: {account_id}")
    print(f"ECR URI: {repo_uri}")

    if args.build:
        run(
            ["docker", "build", "--platform", args.platform, "-t", args.local_image, "."],
            check=True,
            cwd=REPO_ROOT,
        )

    if not args.no_login:
        docker_login(args.region)

    for tag in tags:
        remote = f"{repo_uri}:{tag}"
        run(["docker", "tag", args.local_image, remote], check=True)
        run(["docker", "push", remote], check=True)
        print(f"OK: pushed {remote}")

    print(json.dumps({"repository_uri": repo_uri, "tags": tags}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
