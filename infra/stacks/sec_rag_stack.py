"""
Phase 5 — SecRagStack（CDK 主栈）

Step 2：空骨架，能 cdk synth。
Step 3+ 在本文件里逐步加：ECR → ECS Fargate → ALB → IAM → Secrets → CloudWatch。

与 Phase 4 共用：
  - region: us-east-1
  - OpenSearch collection / S3 bucket 已在 Phase 4 建好（本栈先不重复创建）
"""

from __future__ import annotations

from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_ecr as ecr
from constructs import Construct

# 与 Dockerfile 本地 tag、Step 4 ECS task 镜像名一致
ECR_REPOSITORY_NAME = "sec-rag-api"


class SecRagStack(Stack):
    """SEC RAG API on ECS Fargate + ALB（分步填充）。"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -----------------------------------------------------------------
        # Step 3: ECR — 私有镜像仓库（ECS 从这里 pull）
        # -----------------------------------------------------------------
        self.api_repository = ecr.Repository(
            self,
            "ApiRepository",
            repository_name=ECR_REPOSITORY_NAME,
            # capstone teardown：删栈时清空并删除仓库（demo 后省 ECR 存储费）
            removal_policy=RemovalPolicy.DESTROY,
            empty_on_delete=True,
        )

        CfnOutput(
            self,
            "EcrRepositoryUri",
            value=self.api_repository.repository_uri,
            description="docker tag / push 目标（scripts/ecr_push.py 会读这个）",
        )
        CfnOutput(
            self,
            "EcrRepositoryName",
            value=self.api_repository.repository_name,
        )

        # -----------------------------------------------------------------
        # Step 4: ECS cluster + Fargate task definition + service
        # Step 5: Application Load Balancer + target group (/health)
        # Step 6: Task IAM role (S3 read, OpenSearch Serverless, logs)
        # Step 7: Secrets Manager + task environment variables
        # Step 8: CloudWatch log group
        # -----------------------------------------------------------------

        CfnOutput(
            self,
            "StackPhase",
            value="5-step3-ecr",
            description="CDK stack phase marker (updated as we add resources)",
        )
