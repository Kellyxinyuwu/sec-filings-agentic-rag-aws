#!/usr/bin/env python3
"""
Phase 5 Step 2 — CDK 入口

用法（在 infra/ 目录）：
    pip install -r requirements.txt
    python3 app.py       # 无 CDK CLI 时也可 synth → cdk.out/
    cdk synth            # 若已 npm install -g aws-cdk
    cdk bootstrap        # 首次 deploy 前做一次（本 Step 可不跑）
    cdk deploy           # Step 3+ 再 deploy

账号/区域：
  - 默认 region us-east-1（与 Phase 4 OpenSearch / S3 一致）
  - deploy 前建议：export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# jsii（AWS CDK Python）会 spawn Node 子进程 — 没有 node 会 FileNotFoundError
if shutil.which("node") is None:
    print(
        "ERROR: Node.js not found on PATH.\n"
        "AWS CDK Python (jsii) requires Node 18+ even for `python3 app.py`.\n\n"
        "Install (macOS Homebrew):\n"
        "  brew install node\n"
        "Then verify:\n"
        "  node --version\n"
        "  npm --version\n"
    )
    sys.exit(1)

# Node 26+ 会打 jsii 大横幅警告（不影响 synth）；可静默
os.environ.setdefault("JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION", "1")

import aws_cdk as cdk

from stacks.sec_rag_stack import SecRagStack

# 与 Phase 4 .env 里 AWS_REGION 保持一致
DEFAULT_REGION = "us-east-1"

app = cdk.App()

# account 未 export 时用 cdk.Aws.ACCOUNT_ID（token，本地 synth 可过）
account = os.environ.get("CDK_DEFAULT_ACCOUNT") or cdk.Aws.ACCOUNT_ID
region = os.environ.get("CDK_DEFAULT_REGION", DEFAULT_REGION)

SecRagStack(
    app,
    "SecRagStack",
    description="SEC filings agentic RAG API — ECS Fargate + ALB (Phase 5)",
    env=cdk.Environment(account=account, region=region),
)

# CDK 2.x 默认 synth 到临时目录；复制到 infra/cdk.out 方便查看（等同 cdk synth）
assembly = app.synth()
outdir = Path(__file__).resolve().parent / "cdk.out"
if assembly.directory != str(outdir):
    if outdir.exists():
        shutil.rmtree(outdir)
    shutil.copytree(assembly.directory, outdir)

template = outdir / "SecRagStack.template.json"
print(f"OK: synth complete → {outdir}/")
print(f"    template: {template.name}")
print("    StackPhase = 5-step2-skeleton")
