"""
Phase 5 Step 7 — ECS container secrets (Secrets Manager).

MANTLE_API_KEY is injected at runtime by ECS from Secrets Manager — not plain task env.
Sync value before deploy: python scripts/secrets_sync_mantle.py
"""

from __future__ import annotations

from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

DEFAULT_MANTLE_SECRET_NAME = "sec-rag/mantle-api-key"


def mantle_secret_name(scope: Construct) -> str:
    ctx = scope.node.try_get_context("mantle_secret_name")
    if ctx is not None and str(ctx).strip():
        return str(ctx).strip()
    return DEFAULT_MANTLE_SECRET_NAME


def container_secrets(secret: secretsmanager.ISecret) -> dict[str, ecs.Secret]:
    return {
        "MANTLE_API_KEY": ecs.Secret.from_secrets_manager(secret),
    }
