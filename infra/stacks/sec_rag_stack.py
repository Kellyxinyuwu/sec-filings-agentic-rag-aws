"""
Phase 5 — SecRagStack（CDK 主栈）

Step 2：空骨架，能 cdk synth。
Step 3：ECR
Step 4：ECS Fargate（公网 IP，无 ALB — Step 5 再加）
Step 5+：ALB → IAM task role → Secrets → CloudWatch

与 Phase 4 共用：
  - region: us-east-1
  - OpenSearch collection / S3 bucket 已在 Phase 4 建好（本栈先不重复创建）
"""

from __future__ import annotations

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from constructs import Construct

from stacks.ecs_env import container_environment

# 与 Dockerfile 本地 tag、ECR 仓库名一致
ECR_REPOSITORY_NAME = "sec-rag-api"
ECS_CLUSTER_NAME = "sec-rag-cluster"
ECS_SERVICE_NAME = "sec-rag-api"
CONTAINER_PORT = 8000

# RAG + MiniLM 冷启动：1 vCPU / 2 GB（Fargate 合法组合）
TASK_CPU = 1024
TASK_MEMORY_MIB = 2048


class SecRagStack(Stack):
    """SEC RAG API on ECS Fargate + ALB（分步填充）。"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        use_existing_ecr = bool(self.node.try_get_context("use_existing_ecr") in (True, "true", "1", 1))

        # -----------------------------------------------------------------
        # Step 3: ECR — 引用 Console 已有仓库，或由 CDK 创建（-c use_existing_ecr=false）
        # -----------------------------------------------------------------
        if use_existing_ecr:
            self.api_repository = ecr.Repository.from_repository_name(
                self,
                "ApiRepository",
                repository_name=ECR_REPOSITORY_NAME,
            )
        else:
            self.api_repository = ecr.Repository(
                self,
                "ApiRepository",
                repository_name=ECR_REPOSITORY_NAME,
                removal_policy=RemovalPolicy.DESTROY,
                empty_on_delete=True,
            )

        CfnOutput(
            self,
            "EcrRepositoryUri",
            value=self.api_repository.repository_uri,
            description="ECR URI (scripts/ecr_push.py)",
        )

        # -----------------------------------------------------------------
        # Step 4: ECS Fargate — default VPC + public IP（Step 5 前临时访问方式）
        # -----------------------------------------------------------------
        vpc = ec2.Vpc.from_lookup(self, "DefaultVpc", is_default=True)

        cluster = ecs.Cluster(
            self,
            "Cluster",
            vpc=vpc,
            cluster_name=ECS_CLUSTER_NAME,
        )

        log_group = logs.LogGroup(
            self,
            "ApiLogGroup",
            log_group_name="/ecs/sec-rag-api",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        execution_role = iam.Role(
            self,
            "TaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="ECS agent: pull ECR image + write CloudWatch logs",
        )
        execution_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
        )

        # Step 6 会在这里加 S3 / OpenSearch 权限；Step 4 先留空 role 让 task 能起
        task_role = iam.Role(
            self,
            "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="App runtime - Step 6 adds S3 + AOSS",
        )

        task_definition = ecs.FargateTaskDefinition(
            self,
            "ApiTaskDef",
            family="sec-rag-api",
            cpu=TASK_CPU,
            memory_limit_mib=TASK_MEMORY_MIB,
            execution_role=execution_role,
            task_role=task_role,
        )

        container = task_definition.add_container(
            "ApiContainer",
            image=ecs.ContainerImage.from_ecr_repository(self.api_repository, tag="latest"),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="api",
                log_group=log_group,
            ),
            environment=container_environment(self),
            port_mappings=[ecs.PortMapping(container_port=CONTAINER_PORT, protocol=ecs.Protocol.TCP)],
        )
        # 避免 linter 报 unused
        assert container is not None

        api_sg = ec2.SecurityGroup(
            self,
            "ApiServiceSg",
            vpc=vpc,
            description="Step 4: allow HTTP to Fargate task public IP (Step 5 ALB replaces this pattern)",
            allow_all_outbound=True,
        )
        api_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(CONTAINER_PORT),
            "Temporary: curl task public IP before ALB",
        )

        self.api_service = ecs.FargateService(
            self,
            "ApiService",
            cluster=cluster,
            service_name=ECS_SERVICE_NAME,
            task_definition=task_definition,
            desired_count=1,
            assign_public_ip=True,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_groups=[api_sg],
            health_check_grace_period=Duration.seconds(120),
        )

        CfnOutput(self, "EcsClusterName", value=cluster.cluster_name)
        CfnOutput(self, "EcsServiceName", value=self.api_service.service_name)
        CfnOutput(
            self,
            "LogGroupName",
            value=log_group.log_group_name,
            description="CloudWatch Logs - aws logs tail /ecs/sec-rag-api",
        )
        CfnOutput(
            self,
            "TaskRoleArn",
            value=task_role.role_arn,
            description="Add to OpenSearch data access policy in Step 6",
        )
        CfnOutput(
            self,
            "EcsStatusHint",
            value="python scripts/ecs_status.py --curl",
            description="After deploy: get task public IP and curl /health",
        )

        # -----------------------------------------------------------------
        # Step 5: Application Load Balancer + target group (/health)
        # Step 6: Task IAM — S3 read, OpenSearch Serverless data access
        # Step 7: Secrets Manager for MANTLE_API_KEY
        # -----------------------------------------------------------------

        CfnOutput(
            self,
            "StackPhase",
            value="5-step4-ecs",
            description="CDK stack phase marker",
        )
