#!/usr/bin/env python3
"""
Phase 5 Step 4 — 查看 ECS service / 任务公网 IP，方便 curl /health（无 ALB 时）

用法（repo 根）：
    python scripts/ecs_status.py
    python scripts/ecs_status.py --curl
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

import boto3
from botocore.exceptions import ClientError

DEFAULT_REGION = "us-east-1"
CLUSTER = "sec-rag-cluster"
SERVICE = "sec-rag-api"


def main() -> int:
    parser = argparse.ArgumentParser(description="ECS Fargate task status and public URL")
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--cluster", default=CLUSTER)
    parser.add_argument("--service", default=SERVICE)
    parser.add_argument("--curl", action="store_true", help="curl /health on public IP")
    args = parser.parse_args()

    ecs = boto3.client("ecs", region_name=args.region)
    ec2 = boto3.client("ec2", region_name=args.region)

    resp = ecs.describe_services(cluster=args.cluster, services=[args.service])
    services = resp.get("services", [])
    if not services:
        failures = resp.get("failures", [])
        reason = failures[0].get("reason", "unknown") if failures else "service not found"
        print(f"FAIL: service '{args.service}' not in cluster '{args.cluster}' ({reason})")
        print("      Run deploy first: python scripts/cdk_ecs_context.py --deploy")
        return 1
    try:
        svc = services[0]
    except (ClientError, KeyError) as exc:
        print(f"FAIL: describe service: {exc}", file=sys.stderr)
        return 1

    print(f"Service: {args.service}")
    print(f"  status: {svc.get('status')}")
    print(f"  desired/running: {svc.get('desiredCount')}/{svc.get('runningCount')}")
    print(f"  pending: {svc.get('pendingCount')}")

    tasks = ecs.list_tasks(cluster=args.cluster, serviceName=args.service, desiredStatus="RUNNING").get(
        "taskArns", []
    )
    if not tasks:
        print("\nNo RUNNING tasks yet — check ECS Console → Events / stopped task reason.")
        return 0

    desc = ecs.describe_tasks(cluster=args.cluster, tasks=tasks[:1])["tasks"][0]
    task_arn = desc["taskArn"]
    print(f"\nTask: {task_arn.split('/')[-1]}")
    print(f"  lastStatus: {desc.get('lastStatus')}")
    print(f"  healthStatus: {desc.get('healthStatus', 'N/A')}")

    eni_ids = [
        detail["value"]
        for att in desc.get("attachments", [])
        for detail in att.get("details", [])
        if detail.get("name") == "networkInterfaceId"
    ]
    public_ip = None
    if eni_ids:
        enis = ec2.describe_network_interfaces(NetworkInterfaceIds=eni_ids[:1])["NetworkInterfaces"]
        if enis:
            public_ip = enis[0].get("Association", {}).get("PublicIp")

    if public_ip:
        url = f"http://{public_ip}:8000"
        print(f"\nPublic URL: {url}")
        print(f"  curl -s {url}/health")
        if args.curl:
            cp = subprocess.run(["curl", "-sf", f"{url}/health"], capture_output=True, text=True)
            if cp.returncode == 0:
                print("\n/health response:")
                try:
                    print(json.dumps(json.loads(cp.stdout), indent=2))
                except json.JSONDecodeError:
                    print(cp.stdout)
            else:
                print(f"\nFAIL curl: {cp.stderr or cp.stdout}", file=sys.stderr)
                return cp.returncode
    else:
        print("\nNo public IP on task ENI (assignPublicIp enabled? task still starting?)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
