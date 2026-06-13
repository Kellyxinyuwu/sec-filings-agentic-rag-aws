"""
Phase 5 Step 4 — 从 CDK context / 环境变量读取 ECS 容器 env（deploy 时用）

用法（在 SecRagStack 内）：
    from stacks.ecs_env import container_environment

不在 repo 里硬编码 .env 值；deploy 前用 scripts/cdk_ecs_context.py 传 -c 或 export。
"""

from __future__ import annotations

import os

from constructs import Construct

# 与 app/config.py 字段对应（容器内用大写 env 名）
CONTEXT_KEYS: tuple[tuple[str, str], ...] = (
    ("app_env", "APP_ENV"),
    ("vector_backend", "VECTOR_BACKEND"),
    ("aws_region", "AWS_REGION"),
    ("opensearch_endpoint", "OPENSEARCH_ENDPOINT"),
    ("opensearch_index", "OPENSEARCH_INDEX"),
    ("s3_bucket", "S3_BUCKET"),
    ("s3_prefix", "S3_PREFIX"),
    ("embedding_model", "EMBEDDING_MODEL"),
    ("embedding_provider", "EMBEDDING_PROVIDER"),
    ("embedding_dimensions", "EMBEDDING_DIMENSIONS"),
    ("llm_provider", "LLM_PROVIDER"),
    ("mantle_base_url", "MANTLE_BASE_URL"),
    ("mantle_model_id", "MANTLE_MODEL_ID"),
    ("log_level", "LOG_LEVEL"),
    ("sec_company_name", "SEC_COMPANY_NAME"),
    ("sec_company_email", "SEC_COMPANY_EMAIL"),
)

DEFAULTS: dict[str, str] = {
    "app_env": "container",
    "vector_backend": "opensearch",
    "aws_region": "us-east-1",
    "opensearch_index": "sec-chunks",
    "s3_prefix": "filings",
    "embedding_model": "all-MiniLM-L6-v2",
    "embedding_provider": "local",
    "embedding_dimensions": "384",
    "llm_provider": "mantle",
    "mantle_base_url": "https://bedrock-mantle.us-east-1.api.aws/v1",
    "log_level": "INFO",
}


def _lookup(scope: Construct, key: str) -> str:
    ctx = scope.node.try_get_context(key)
    if ctx is not None and str(ctx).strip():
        return str(ctx).strip()
    env_key = key.upper()
    if os.environ.get(env_key, "").strip():
        return os.environ[env_key].strip()
    return DEFAULTS.get(key, "")


def container_environment(scope: Construct) -> dict[str, str]:
    """Non-secret env only; MANTLE_API_KEY comes from Secrets Manager (Step 7)."""
    env: dict[str, str] = {}
    for ctx_key, container_key in CONTEXT_KEYS:
        value = _lookup(scope, ctx_key)
        if value:
            env[container_key] = value
    return env
