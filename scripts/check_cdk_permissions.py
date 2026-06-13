#!/usr/bin/env python3
"""
Phase 5 — 检查 dev-kelly 能否跑 cdk bootstrap / deploy / ECS

用法（repo 根）：
    python scripts/check_cdk_permissions.py
"""

from __future__ import annotations

import sys

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"


def check(name: str, fn) -> bool:
    try:
        fn()
        print(f"  OK   {name}")
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "?")
        print(f"  FAIL {name} — {code}")
        return False
    except Exception as exc:
        print(f"  FAIL {name} — {exc}")
        return False


def main() -> int:
    print(f"Account: {boto3.client('sts').get_caller_identity()['Account']}  region: {REGION}\n")

    ok = True
    ok &= check(
        "cloudformation:DescribeStacks",
        lambda: boto3.client("cloudformation", region_name=REGION).describe_stacks(StackName="CDKToolkit"),
    )
    ok &= check(
        "ssm:GetParameter (cdk bootstrap version)",
        lambda: boto3.client("ssm", region_name=REGION).get_parameter(
            Name="/cdk-bootstrap/hnb659fds/version"
        ),
    )
    ok &= check(
        "ec2:DescribeVpcs",
        lambda: boto3.client("ec2", region_name=REGION).describe_vpcs(
            Filters=[{"Name": "is-default", "Values": ["true"]}]
        ),
    )
    ok &= check("ecs:CreateCluster", lambda: boto3.client("ecs", region_name=REGION).create_cluster(clusterName="sec-rag-perm-probe"))
    ok &= check(
        "iam:CreateRole",
        lambda: boto3.client("iam").create_role(
            RoleName="sec-rag-perm-probe",
            AssumeRolePolicyDocument='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}',
        ),
    )

    # cleanup probes
    ecs = boto3.client("ecs", region_name=REGION)
    iam = boto3.client("iam")
    try:
        ecs.delete_cluster(cluster="sec-rag-perm-probe")
    except ClientError:
        pass
    try:
        iam.delete_role(RoleName="sec-rag-perm-probe")
    except ClientError:
        pass

    cf = boto3.client("cloudformation", region_name=REGION)
    try:
        status = cf.describe_stacks(StackName="CDKToolkit")["Stacks"][0]["StackStatus"]
        if status != "CREATE_COMPLETE":
            print(f"\nWARN: CDKToolkit stack status = {status}")
            print("      Admin may need to delete stack CDKToolkit + orphaned cdk-hnb659fds-* roles.")
    except ClientError:
        print("\nINFO: CDKToolkit stack not found — run cdk bootstrap after IAM is fixed.")

    print("\nCDK deploy needs: bootstrap OK + iam:CreateRole/GetRole/PassRole + ecs + ec2 + logs.")
    print("Quick fix (personal account): attach IAMFullAccess or PowerUserAccess to dev-kelly.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
