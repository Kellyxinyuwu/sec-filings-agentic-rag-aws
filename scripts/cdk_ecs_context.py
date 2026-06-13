#!/usr/bin/env python3
"""
Phase 5 Step 4 — 从 repo 根 .env 生成 CDK deploy 用的 context / deploy

用法（repo 根，推荐）：
    eval "$(python scripts/cdk_env.py)"
    python scripts/cdk_ecs_context.py --deploy

勿用：cdk deploy $(python ... --cdk-args)  — 值含空格（如 Kelly Wu）会被 shell 拆坏。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INFRA_DIR = REPO_ROOT / "infra"
ENV_FILE = REPO_ROOT / ".env"
STACK_NAME = "SecRagStack"

# 与 infra/stacks/ecs_env.py CONTEXT_KEYS 的 context 名一致
ENV_TO_CONTEXT: dict[str, str] = {
    "APP_ENV": "app_env",
    "VECTOR_BACKEND": "vector_backend",
    "AWS_REGION": "aws_region",
    "OPENSEARCH_ENDPOINT": "opensearch_endpoint",
    "OPENSEARCH_INDEX": "opensearch_index",
    "OPENSEARCH_COLLECTION_NAME": "opensearch_collection_name",
    "S3_BUCKET": "s3_bucket",
    "S3_PREFIX": "s3_prefix",
    "EMBEDDING_MODEL": "embedding_model",
    "EMBEDDING_PROVIDER": "embedding_provider",
    "EMBEDDING_DIMENSIONS": "embedding_dimensions",
    "LLM_PROVIDER": "llm_provider",
    "MANTLE_BASE_URL": "mantle_base_url",
    "MANTLE_API_KEY": "mantle_api_key",
    "MANTLE_MODEL_ID": "mantle_model_id",
    "LOG_LEVEL": "log_level",
    "SEC_COMPANY_NAME": "sec_company_name",
    "SEC_COMPANY_EMAIL": "sec_company_email",
}

SECRET_CONTEXT_KEYS = frozenset({"mantle_api_key"})
# Never pass to CDK deploy -c (would land in CFN); use scripts/secrets_sync_mantle.py
CDK_DEPLOY_CONTEXT_EXCLUDE = frozenset({"mantle_api_key"})


def parse_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        # 修正常见 typo：两行粘在一起 --- Phase 2...LLM_PROVIDER=mantle
        if "---" in key:
            continue
        if key in ENV_TO_CONTEXT or key.isupper():
            out[key] = value
    return out


def build_context(env: dict[str, str], *, for_deploy: bool = False) -> dict[str, str]:
    ctx: dict[str, str] = {}
    for env_key, ctx_key in ENV_TO_CONTEXT.items():
        if for_deploy and ctx_key in CDK_DEPLOY_CONTEXT_EXCLUDE:
            continue
        val = env.get(env_key, "").strip()
        if val:
            ctx[ctx_key] = val
    if "vector_backend" not in ctx:
        ctx["vector_backend"] = "opensearch"
    # ECS 任务固定为 container（.env 里 laptop 可能是 local）
    ctx["app_env"] = "container"
    return ctx


def cdk_deploy_argv(ctx: dict[str, str]) -> list[str]:
    """Build argv for subprocess — safe for values with spaces."""
    cmd = ["cdk", "deploy", STACK_NAME, "--require-approval", "never"]
    for key, value in sorted(ctx.items()):
        cmd.extend(["-c", f"{key}={value}"])
    return cmd


def run_cdk_deploy(ctx: dict[str, str], *, bootstrap: bool = False) -> int:
    if bootstrap:
        bootstrap_cmd = [
            "cdk",
            "bootstrap",
            f"aws://{os.environ.get('CDK_DEFAULT_ACCOUNT', '')}/{os.environ.get('CDK_DEFAULT_REGION', 'us-east-1')}",
        ]
        print("+", " ".join(bootstrap_cmd), flush=True)
        br = subprocess.run(bootstrap_cmd, cwd=INFRA_DIR, check=False)
        if br.returncode != 0:
            print(
                "FAIL: cdk bootstrap — need iam:CreateRole/GetRole. "
                "Run: python scripts/check_cdk_permissions.py",
                file=sys.stderr,
            )
            return br.returncode
    cmd = cdk_deploy_argv(ctx)
    print("+", " ".join(cmd[:4]), f"... ({len(ctx)} x -c)", flush=True)
    return subprocess.run(cmd, cwd=INFRA_DIR, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CDK context from .env for ECS deploy")
    parser.add_argument(
        "--export",
        action="store_true",
        help="Print export CDK_CONTEXT_* lines for eval",
    )
    parser.add_argument(
        "--cdk-args",
        action="store_true",
        help="Print -c key=value (unsafe with spaces — prefer --deploy)",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Run cdk bootstrap before deploy",
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Run cdk deploy SecRagStack with context from .env (safe quoting)",
    )
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    args = parser.parse_args()

    env = parse_dotenv(args.env_file)
    ctx = build_context(env)

    missing = [k for k in ("opensearch_endpoint", "mantle_model_id") if not ctx.get(k)]
    if not env.get("MANTLE_API_KEY", "").strip():
        missing.append("mantle_api_key (MANTLE_API_KEY in .env)")
    if missing:
        print(f"# WARN: missing in {args.env_file}: {', '.join(missing)}", file=sys.stderr)

    if args.deploy:
        deploy_ctx = build_context(env, for_deploy=True)
        print("# deploy context excludes mantle_api_key — use scripts/secrets_sync_mantle.py", file=sys.stderr)
        return run_cdk_deploy(deploy_ctx, bootstrap=args.bootstrap)

    if args.export:
        for key, value in sorted(ctx.items()):
            print(f"export CDK_CONTEXT_{key.upper()}={repr(value)}")
        print("# Prefer: python scripts/cdk_ecs_context.py --deploy")
        return 0

    if args.cdk_args:
        print("# WARN: do not use with $(...) if values contain spaces; use --deploy", file=sys.stderr)
        cmd = cdk_deploy_argv(ctx)
        # 仅展示，实际 deploy 请 --deploy
        print(" ".join(cmd[3:]))  # skip cdk deploy SecRagStack
        return 0

    # 默认：人类可读摘要
    print(f"# Context from {args.env_file} ({len(ctx)} keys)")
    for key, value in sorted(ctx.items()):
        if key in SECRET_CONTEXT_KEYS:
            shown = value[:8] + "..." if len(value) > 8 else "(empty)"
        else:
            shown = value
        print(f"  {key}: {shown}")
    print("\nDeploy (recommended):")
    print("  eval \"$(python scripts/cdk_env.py)\"")
    print("  python scripts/cdk_ecs_context.py --deploy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
