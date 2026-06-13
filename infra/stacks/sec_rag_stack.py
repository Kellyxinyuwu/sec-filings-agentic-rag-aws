"""
Phase 5 — SecRagStack（CDK 主栈）

Step 2：空骨架，能 cdk synth。
Step 3+ 在本文件里逐步加：ECR → ECS Fargate → ALB → IAM → Secrets → CloudWatch。

与 Phase 4 共用：
  - region: us-east-1
  - OpenSearch collection / S3 bucket 已在 Phase 4 建好（本栈先不重复创建）
"""

from __future__ import annotations

from aws_cdk import CfnOutput, Stack
from constructs import Construct


class SecRagStack(Stack):
    """SEC RAG API on ECS Fargate + ALB（分步填充）。"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -----------------------------------------------------------------
        # Step 3: ECR repository for sec-rag-api image
        # Step 4: ECS cluster + Fargate task definition + service
        # Step 5: Application Load Balancer + target group (/health)
        # Step 6: Task IAM role (S3 read, OpenSearch Serverless, logs)
        # Step 7: Secrets Manager + task environment variables
        # Step 8: CloudWatch log group
        # -----------------------------------------------------------------

        # 占位输出 — 证明 synth 成功；deploy 后可在 CloudFormation Outputs 看到
        CfnOutput(
            self,
            "StackPhase",
            value="5-step2-skeleton",
            description="CDK stack phase marker (updated as we add resources)",
        )
