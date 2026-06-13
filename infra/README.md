# Infrastructure (AWS CDK) — Phase 5

Python CDK app for **ECS Fargate + ALB + ECR + IAM + CloudWatch**.  
Phase 4 的 S3 / OpenSearch 已在控制台建好；本栈负责 **API 算力面**。

## 前置（必读）

| 工具 | 检查 | 说明 |
|------|------|------|
| **Node.js 18+** | `node --version` | **必填** — CDK Python (jsii) 即使用 `python3 app.py` 也要 Node |
| **npm** | `npm --version` | 装 CDK CLI 用（Step 3 deploy 时需要） |
| AWS 凭证 | `python scripts/cdk_env.py` | deploy/push 时用 boto3 设 account |
| Python 3.11+ | repo 根 `.venv` | `pip install -r requirements.txt` |

### macOS 安装 Node（若 `node: command not found`）

```bash
brew install node
node --version    # 应 ≥ v18
npm --version
```

装完后**新开一个终端**（或 `source ~/.zshrc`），再跑 synth。

### 安装 CDK CLI（Step 3 deploy 前）

```bash
npm install -g aws-cdk
cdk --version
```

## Step 2 — 本地 synth（不创建 AWS 资源）

```bash
cd sec-filings-agentic-rag-aws
source .venv/bin/activate
cd infra
pip install -r requirements.txt
python3 app.py
```

期望：生成 `cdk.out/SecRagStack.template.json`，Outputs 含 `StackPhase = 5-step2-skeleton`。

等价命令（装好 CDK CLI 后）：`cdk synth`

## Step 3 — ECR + push ✅（2026-06-13）

**实际路径：** Console 建 `sec-rag-api` + IAM `AmazonEC2ContainerRegistryPowerUser` + `scripts/ecr_push.py`  
（CDK `cdk deploy` 可选；dev-kelly 无 CloudFormation 时可跳过）

```bash
# repo 根目录
eval "$(python scripts/cdk_env.py)"   # 勿用 aws sts（本机 pyexpat 可能报错）
python scripts/ecr_push.py            # 复用 sec-rag-api:local
```

镜像 URI：`449873021145.dkr.ecr.us-east-1.amazonaws.com/sec-rag-api:latest`

详见 `docs/PHASE_5.md` Step 3（Console 截图级步骤 + Q&A）。

## Step 4 — ECS Fargate ✅（2026-06-13）

**目标：** Fargate task **RUNNING**；无 ALB 时用任务 **公网 IP:8000** curl `/health`。

```bash
eval "$(python scripts/cdk_env.py)"
python scripts/check_cdk_permissions.py   # 可选
python scripts/ecr_push.py --build        # Mac 必读：linux/amd64
python scripts/cdk_ecs_context.py --deploy --bootstrap   # 首次 bootstrap
python scripts/ecs_status.py --curl
```

| 资源 | 名 |
|------|-----|
| Cluster | `sec-rag-cluster` |
| Service | `sec-rag-api` |
| Logs | `/ecs/sec-rag-api` |
| Task | 1 vCPU / 2 GB，`sec-rag-api:latest` |

**验证：** `/health` → `status: ok`, `phase: 4`, `vector_backend: opensearch`。

**踩坑：** 勿用 `cdk deploy $(... --cdk-args)`；Mac 需 amd64 镜像；IAM role description 勿用 em dash。

`/retrieve` 要等 **Step 6 task IAM + OpenSearch data access**。公网 IP 在 Step 5 ALB 前会变。详见 `docs/PHASE_5.md` Step 4。

## Step 5 — ALB + health check ✅（2026-06-13）

**目标：** 稳定 DNS；`GET /health` 做 target health check；任务 SG 仅允许 ALB。

```bash
eval "$(python scripts/cdk_env.py)"
python scripts/cdk_ecs_context.py --deploy
python scripts/alb_status.py --curl
```

| 资源 | 名 |
|------|-----|
| ALB | `SecRagStack-ApiAlb-*` |
| Target group | health check `/health` |
| Outputs | `AlbDnsName`, `AlbUrl` |

**验证：** `alb_status.py --curl` → `status: ok`, `phase: 4`, `vector_backend: opensearch`。

`/retrieve` 仍待 **Step 6**。详见 `docs/PHASE_5.md` Step 5。

## Step 6 — Task IAM ✅（2026-06-13）

**目标：** ECS task role 访问 S3 + AOSS；无容器内 `~/.aws/credentials`。

```bash
eval "$(python scripts/cdk_env.py)"
python scripts/cdk_ecs_context.py --deploy
python scripts/aoss_grant_task_role.py
python scripts/alb_api_smoke.py
```

| 层 | 文件 |
|----|------|
| IAM policy | `infra/stacks/task_iam.py` |
| AOSS data access | `scripts/aoss_grant_task_role.py` → `sec-rag-data-access` |

**验证：** `alb_api_smoke.py` → 3 AAPL chunks via OpenSearch（无容器内 AWS credentials 文件）。

## Step 7 — Secrets Manager ✅（2026-06-13）

**目标：** `MANTLE_API_KEY` 从 Secrets Manager 注入，不进 CDK 明文 context。

```bash
python scripts/secrets_sync_mantle.py
python scripts/cdk_ecs_context.py --deploy
python scripts/alb_api_smoke.py --chat-only
```

| 项 | 值 |
|----|-----|
| Secret | `sec-rag/mantle-api-key` |
| CDK | `ecs_secrets.py` + execution role `grant_read` |

**验证：** `alb_api_smoke.py --chat-only` → `qa`, 5 evidence, `citations ok`。

## Step 8 — CloudWatch logs ✅（2026-06-13）

```bash
python scripts/ecs_logs_tail.py --smoke
```

Log group `/ecs/sec-rag-api` 已在 Step 4 CDK 创建；`ecs_logs_tail.py --smoke` → **OK**。

## Step 9 — ALB E2E ✅（2026-06-13）

```bash
python scripts/alb_e2e.py
```

**验证：** health + retrieve + 3 golden QA + REFUSE 全绿（~80s）。

## Step 10 — Done ✅

Phase 5 complete. Teardown after demo:

```bash
python scripts/cdk_teardown.py
python scripts/cdk_teardown.py --destroy   # actually delete stack
```

See also Phase 4 OpenSearch / S3 cleanup in `docs/NOTICE.md`.

## 想省钱咋办？（不请求也计费）

只要 **SecRagStack 还在 + OpenSearch collection 还在**，就算没人 curl ALB，也会持续计费：

| 常开费用 | 说明 |
|----------|------|
| ECS Fargate | 1 task RUNNING → 按 vCPU/内存小时 |
| ALB | 负载均衡器存在 → 按小时 |
| OpenSearch Serverless | collection 在 → **通常账单最大头** |
| ECR / Secrets / Logs / S3 | 相对小，但仍有 |

**按次才明显计费：** Bedrock Mantle（`/chat` token）— 不打 `/chat` 这块几乎不涨。

```bash
python scripts/cdk_teardown.py              # 只看清单，不删
python scripts/cdk_teardown.py --destroy    # 删 ECS + ALB + …
# 然后控制台删 OpenSearch collection kelly-sec-rag-vectors
```

| 场景 | 建议 |
|------|------|
| 还要 demo | 先别 destroy |
| 项目交完、短期不用云 | destroy + 删 OpenSearch |
| 只本地开发 | laptop uvicorn 即可，不必常开 ECS |

## Teardown reference

```bash
cdk bootstrap   # 账号/区域首次 deploy 前
cdk deploy      # 创建/更新 CloudFormation 栈
cdk destroy     # demo 后拆栈
```

Region 默认 **us-east-1**（与 Phase 4 一致）。deploy 前建议：

```bash
export CDK_DEFAULT_REGION=us-east-1
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
```

## 目录

```
infra/
├── app.py                 # CDK 入口（启动前检查 node）
├── cdk.json
├── requirements.txt
└── stacks/
    └── sec_rag_stack.py   # SecRagStack（Step 3+ 加 ECR/ECS/ALB…）
```

## 常见错误

| 错误 | 原因 | 解决 |
|------|------|------|
| `No such file or directory: 'node'` | 终端 PATH 无 Node | `brew install node`，新开终端 |
| `Unable to parse aws:///us-east-1` | account 未设 | 本地 synth 用 `app.py`（已 fallback）；deploy 前 export `CDK_DEFAULT_ACCOUNT` |
| **Node 26+ 大横幅** | jsii 未官方测试 v26 | 可忽略；`app.py` 已设 `JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION`；推荐 LTS **22** 或 **24** |
| **manifest 403 after layers Pushed** | 缺 `ecr:PutImage` | Attach **AmazonEC2ContainerRegistryPowerUser** |
| `cdk deploy` AccessDenied | 缺 CloudFormation/IAM | `check_cdk_permissions.py`；加 PowerUser 或 IAMFullAccess |
| `CannotPullContainerError` linux/amd64 | Mac ARM 镜像 | `python scripts/ecr_push.py --build` + force redeploy |
| `No stacks match Wu'` | shell 空格拆参 | `python scripts/cdk_ecs_context.py --deploy` |
