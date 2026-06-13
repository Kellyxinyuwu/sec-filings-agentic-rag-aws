#!/usr/bin/env python3
"""
Phase 5 Step 6 — add ECS TaskRoleArn to OpenSearch Serverless data access policy.

AOSS needs BOTH:
  1. IAM policy on task role (CDK SecRagStack — aoss:APIAccessAll)
  2. Data access policy principal list (this script)

用法（repo 根，deploy Step 6 后）：
    python scripts/aoss_grant_task_role.py
    python scripts/aoss_grant_task_role.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / ".env"
DEFAULT_REGION = "us-east-1"
STACK_NAME = "SecRagStack"
POLICY_NAME = "sec-rag-data-access"
DEFAULT_COLLECTION = "kelly-sec-rag-vectors"

# Retrieve-only permissions (API task does not ingest)
AOSS_RULES = [
    {
        "Resource": ["collection/{collection}"],
        "Permission": [
            "aoss:DescribeCollectionItems",
        ],
        "ResourceType": "collection",
    },
    {
        "Resource": ["index/{collection}/*"],
        "Permission": [
            "aoss:DescribeIndex",
            "aoss:ReadDocument",
        ],
        "ResourceType": "index",
    },
]


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


def task_role_arn_from_stack(cfn, stack_name: str) -> str:
    resp = cfn.describe_stacks(StackName=stack_name)
    outputs = {o["OutputKey"]: o["OutputValue"] for o in resp["Stacks"][0].get("Outputs", [])}
    arn = outputs.get("TaskRoleArn", "").strip()
    if not arn:
        raise ValueError(f"TaskRoleArn not in stack {stack_name} outputs — deploy Step 6 CDK first")
    return arn


def build_policy_document(collection: str, principals: list[str]) -> list[dict]:
    rules = []
    for rule in AOSS_RULES:
        rules.append(
            {
                "Resource": [r.format(collection=collection) for r in rule["Resource"]],
                "Permission": list(rule["Permission"]),
                "ResourceType": rule["ResourceType"],
            }
        )
    return [{"Rules": rules, "Principal": sorted(set(principals))}]


def merge_principals(current: list[dict], task_arn: str, collection: str) -> list[dict]:
    if not current:
        doc = build_policy_document(collection, [task_arn])
        return doc

    merged = json.loads(json.dumps(current))
    entry = merged[0]
    principals = list(entry.get("Principal") or [])
    if task_arn not in principals:
        principals.append(task_arn)
    entry["Principal"] = sorted(set(principals))
    # Ensure Rules exist (do not wipe custom grants if already present)
    if not entry.get("Rules"):
        entry["Rules"] = build_policy_document(collection, principals)[0]["Rules"]
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Grant ECS task role in AOSS data access policy")
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--stack", default=STACK_NAME)
    parser.add_argument("--policy-name", default=POLICY_NAME)
    parser.add_argument("--collection", default="", help=f"default: .env OPENSEARCH_COLLECTION_NAME or {DEFAULT_COLLECTION}")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    args = parser.parse_args()

    env = parse_dotenv(args.env_file)
    collection = (
        args.collection.strip()
        or env.get("OPENSEARCH_COLLECTION_NAME", "").strip()
        or DEFAULT_COLLECTION
    )

    cfn = boto3.client("cloudformation", region_name=args.region)
    ossl = boto3.client("opensearchserverless", region_name=args.region)

    try:
        task_arn = task_role_arn_from_stack(cfn, args.stack)
    except (ClientError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"Task role: {task_arn}")
    print(f"Data access policy: {args.policy_name}")
    print(f"Collection: {collection}")

    try:
        detail = ossl.get_access_policy(type="data", name=args.policy_name)["accessPolicyDetail"]
    except ClientError as exc:
        print(f"FAIL: get_access_policy: {exc}", file=sys.stderr)
        print("Create policy in console first (Phase 4) or check policy name.", file=sys.stderr)
        return 1

    version = detail["policyVersion"]
    raw_policy = detail.get("policy") or "[]"
    if isinstance(raw_policy, str):
        current = json.loads(raw_policy)
    else:
        current = raw_policy
    updated = merge_principals(current, task_arn, collection)

    existing_principals = (current[0].get("Principal") or []) if current else []
    if task_arn in existing_principals:
        print("OK: task role already in data access policy — no change")
        return 0

    print("\nUpdated policy (preview):")
    print(json.dumps(updated, indent=2))

    if args.dry_run:
        print("\n(dry-run — no update)")
        return 0

    try:
        ossl.update_access_policy(
            type="data",
            name=args.policy_name,
            policyVersion=version,
            policy=json.dumps(updated),
        )
    except ClientError as exc:
        print(f"FAIL: update_access_policy: {exc}", file=sys.stderr)
        return 1

    print("\nOK: data access policy updated — wait ~30s then curl ALB /retrieve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
