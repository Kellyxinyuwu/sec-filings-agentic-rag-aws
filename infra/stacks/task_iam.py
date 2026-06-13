"""
Phase 5 Step 6 — ECS task role policies (S3 read + OpenSearch Serverless API).

IAM identity policy on the task role is only half of AOSS access; also run:
    python scripts/aoss_grant_task_role.py
to add TaskRoleArn to the Serverless data access policy.
"""

from __future__ import annotations

from urllib.parse import urlparse

from aws_cdk import Stack
from aws_cdk import aws_iam as iam
from constructs import Construct

DEFAULT_COLLECTION_NAME = "kelly-sec-rag-vectors"


def _lookup(scope: Construct, key: str, default: str = "") -> str:
    ctx = scope.node.try_get_context(key)
    if ctx is not None and str(ctx).strip():
        return str(ctx).strip()
    return default


def collection_id_from_endpoint(endpoint: str) -> str:
    """Parse AOSS collection id from endpoint host (first label)."""
    endpoint = endpoint.strip()
    if not endpoint:
        return ""
    if "://" in endpoint:
        host = urlparse(endpoint).hostname or ""
    else:
        host = endpoint.split("/")[0].rstrip("/")
    return host.split(".")[0] if host else ""


def attach_task_policies(scope: Construct, task_role: iam.Role) -> None:
    """Grant S3 read + AOSS API access for retrieve (no ~/.aws in container)."""
    stack = Stack.of(scope)
    account = stack.account
    region = stack.region

    bucket = _lookup(scope, "s3_bucket")
    prefix = _lookup(scope, "s3_prefix", "filings").strip("/")

    if bucket:
        resources = [f"arn:aws:s3:::{bucket}"]
        if prefix:
            resources.append(f"arn:aws:s3:::{bucket}/{prefix}/*")
        else:
            resources.append(f"arn:aws:s3:::{bucket}/*")
        task_role.add_to_policy(
            iam.PolicyStatement(
                sid="S3ReadFilings",
                actions=["s3:GetObject", "s3:ListBucket"],
                resources=resources,
            )
        )

    endpoint = _lookup(scope, "opensearch_endpoint")
    collection_id = _lookup(scope, "opensearch_collection_id") or collection_id_from_endpoint(endpoint)
    if collection_id and account and region and not account.startswith("${"):
        collection_arn = f"arn:aws:aoss:{region}:{account}:collection/{collection_id}"
        task_role.add_to_policy(
            iam.PolicyStatement(
                sid="AossApiAccess",
                actions=["aoss:APIAccessAll"],
                resources=[collection_arn],
            )
        )


def opensearch_collection_name(scope: Construct) -> str:
    return _lookup(scope, "opensearch_collection_name", DEFAULT_COLLECTION_NAME)
