# Phase 0 — 完整实施手册（可粘贴到文件）

> **怎么用这份文档（实习用 Copilot 时）**  
> 1. 按 **步骤顺序** 做，不要跳。  
> 2. 每个「创建文件」小节：在 VS Code 里 **新建对应路径的文件**，把代码块 **整段复制粘贴**（不要漏 `import`）。  
> 3. 用 Copilot 时可以说：*「按 docs/PHASE_0.md 里 app/schemas.py 的契约，不要改字段名」*，避免它乱改接口。  
> 4. 每完成一个大步骤，在终端跑 **验证命令**。  
> 5. 完成后在根目录 `README.md` 的 Phase 0 **Done notes** 填日期和 commit。

**Phase 0 目标：** 可运行的 FastAPI 骨架 + 数据契约 + mock `/chat` + 测试/CI；**不要求** Bedrock 已开通（但建议并行做 AWS 账号准备）。

**Commit 参考：** `047641a` — `feat(phase-0): project skeleton and mock agentic RAG API`

---

## 目录

1. [我们做了什么（总览）](#1-我们做了什么总览)
1.1. [**每个文件是干什么的（建议先读）**](#11-phase-0-每个文件是干什么的建议先读)
2. [前置：GitHub 仓库](#2-前置github-仓库)
3. [步骤 A：创建目录](#3-步骤-a创建目录)
4. [步骤 B：配置文件（非 Python）](#4-步骤-b配置文件非-python)
5. [步骤 C：Python 应用代码](#5-步骤-cpython-应用代码)
6. [步骤 D：测试与 CI](#6-步骤-d测试与-ci)
7. [步骤 E：文档](#7-步骤-e文档)
8. [步骤 F：本地安装与验证](#8-步骤-f本地安装与验证)
9. [步骤 G：Git 提交](#9-步骤-g-git-提交)
10. [步骤 H：AWS 准备（可选，建议 Phase 0 同期做）](#10-步骤-haws-准备可选建议-phase-0-同期做)
11. [验收清单](#11-验收清单)
12. [常见问题](#12-常见问题)

---

## 1. 我们做了什么（总览）

| 顺序 | 事项 | 结果 |
|------|------|------|
| 1 | 在 GitHub 创建 `sec-filings-agentic-rag-aws`，clone 到本地 | 空仓库 |
| 2 | 误建 `app/app/` 后删除 | 避免嵌套包混乱 |
| 3 | 搭骨架：扁平 `app/` + `scripts/` + `tests/` + `docs/` | 简洁结构 |
| 4 | 定义 Pydantic schemas（未来 agent 共用） | `app/schemas.py` |
| 5 | FastAPI：`/health` + mock `/chat` | `app/api.py`, `app/main.py` |
| 6 | 配置与日志 | `app/config.py`, `app/logging_setup.py` |
| 7 | pytest + GitHub Actions | `tests/`, `.github/workflows/ci.yml` |
| 8 | README 阶段追踪 + 架构/AWS 文档 | `README.md`, `docs/` |
| 9 | AWS 账号、us-east-1、Budget $20、Bedrock Support cases | 见 [步骤 H](#10-步骤-haws-准备可选建议-phase-0-同期做) |

**Phase 0 不做：** 真实 EDGAR 下载、向量库、Bedrock 调用、agent 编排。

---

## 1.1 Phase 0 每个文件是干什么的（建议先读）

下面按「根目录配置 → 应用代码 → 测试/脚本 → 文档」说明。**先理解再粘贴代码**，以后用 Copilot 也不容易改错文件。

### 一张图：请求怎么流过这些文件

```
用户 curl /chat
    → app/main.py        （启动 FastAPI，挂上路由）
    → app/api.py         （处理 HTTP：读 body、返回 JSON）
    → app/schemas.py     （校验 JSON 形状：ChatRequest / ChatResponse）
    → app/config.py      （如需读 .env 里的配置）
    → app/logging_setup.py （打结构化日志）
```

Phase 0 的 `/chat` **还没有** 真 RAG，只是在 `api.py` 里造了假数据；Phase 1 会加 `tools.py`，Phase 3 会加 `orchestrator.py`。

---

### 根目录 — 项目配置（4 个核心 + README）

| 文件 | 一句话 | 详细说明 |
|------|--------|----------|
| **`pyproject.toml`** | Python 项目的「说明书 + 依赖清单」 | 告诉 pip：项目叫什么、需要装哪些库（FastAPI、pytest…）、测试/代码检查工具（ruff）怎么配。执行 `pip install -e ".[dev]"` 时读的就是它。类似 Node 的 `package.json`。 |
| **`.gitignore`** | 告诉 Git **不要提交** 哪些文件 | 例如 `.venv/`（虚拟环境）、`.env`（密钥）、下载的 SEC 原文。避免把秘密或几 GB 数据 push 到 GitHub。 |
| **`.env.example`** | 环境变量 **模板**（可提交） | 列出需要哪些配置项（API key、AWS region、SEC 邮箱），**没有真密码**。你复制成 `.env` 再填真实值；`.env` 被 gitignore，不会上传。 |
| **`README.md`** | 项目首页（给人看） | GitHub 打开仓库第一眼看到的：目标、怎么跑、Phase 进度表、文件夹说明。面试官也会看。 |

**`pyproject.toml` 里常见块是什么意思？**

| 块 | 作用 |
|----|------|
| `[project]` | 项目名、版本、`dependencies = [...]` 运行时要装的库 |
| `[project.optional-dependencies] dev` | 只有开发才装的库：`pytest`、`ruff` |
| `[tool.pytest.ini_options]` | 跑 `pytest` 时去 `tests/` 找测试 |
| `[tool.ruff]` | 代码风格/简单错误检查（类似 lint） |

---

### `app/` — 应用代码（FastAPI 服务）

| 文件 | 一句话 | 详细说明 |
|------|--------|----------|
| **`app/__init__.py`** | 把 `app` 标记为 Python **包** | 内容可以只有一行注释。没有它，`from app.api import ...` 可能导入失败。 |
| **`app/main.py`** | 程序 **入口** | 创建 `FastAPI()` 实例、初始化日志、把 `api.py` 里的路由挂到 app 上。终端 `uvicorn app.main:app` 里的 `app.main:app` 就指这里。 |
| **`app/api.py`** | **HTTP 接口**：URL 和处理函数 | `@router.get("/health")`、`@router.post("/chat")` 定义「什么路径、收到请求后做什么」。Phase 0 在这里返回 mock；以后改为调 orchestrator。 |
| **`app/schemas.py`** | **数据结构契约**（Pydantic 模型） | 规定请求/响应 JSON 长什么样：`ChatRequest`、`ChatResponse`、`Plan`、`EvidenceChunk`… 前后端、各 agent 都按这份「合同」传数据，减少字段名混乱。 |
| **`app/config.py`** | 读 **环境变量 / .env** | `Settings` 类：把 `AWS_REGION`、`SEC_COMPANY_EMAIL` 等从 `.env` 读进 Python。业务代码用 `from app.config import settings`，不要到处 `os.getenv`。 |
| **`app/logging_setup.py`** | **日志格式** 配置 | 用 `structlog` 输出带时间、级别的日志，方便以后接 CloudWatch。`main.py` 启动时调用一次即可。 |

**Phase 0 还没有、以后会加的文件（先有概念）：**

| 文件（未来） | 将来干什么 |
|--------------|------------|
| `app/tools.py` | RAG **工具**：`retrieve()`、`get_section()` — agent 用来查文档 |
| `app/aws.py` | 调 **Bedrock / S3 / OpenSearch** 的封装 |
| `app/orchestrator.py` | **多 agent 编排**主循环 |
| `app/agents/*.py` | Planner、Researcher、Writer、Verifier 各自逻辑 |

---

### `tests/` — 自动化测试

| 文件 | 一句话 | 详细说明 |
|------|--------|----------|
| **`tests/__init__.py`** | 让 `tests` 成为包 | 可为空；pytest 不强制，但保留无妨。 |
| **`tests/test_health.py`** | **自动检查** API 是否正常 | 不启动浏览器，用 `TestClient` 模拟请求 `/health` 和 `/chat`，断言状态码 200、返回里有没有 `citations`。改代码后跑 `pytest -q` 快速回归。 |

---

### `scripts/` — 命令行脚本（一般不 `import`）

| 文件 | 一句话 | 详细说明 |
|------|--------|----------|
| **`scripts/local_dev.sh`** | 一键：建 venv、装依赖、起 API | Bash 脚本，省得每次手打三条命令。`chmod +x` 后可 `./scripts/local_dev.sh`。 |
| **`scripts/README.md`** | 说明 scripts 目录里有什么 | 占位；Phase 1 会加 `ingest_edgar.py` 下载 SEC。 |

---

### `.github/workflows/` — GitHub Actions（云端 CI）

| 文件 | 一句话 | 详细说明 |
|------|--------|----------|
| **`.github/workflows/ci.yml`** | push 代码时在 **GitHub 服务器** 自动跑测试 | 每次 push `main`：装 Python → `pip install` → `ruff check` → `pytest`。保证远程仓库里的代码也是绿的，和本机一致。 |

---

### `docs/` 和 `infra/` — 文档与基础设施

| 文件 | 一句话 | 详细说明 |
|------|--------|----------|
| **`docs/ARCHITECTURE.md`** | **系统设计**：agent 角色、AWS 组件 | 给未来的你和面试官看「整体怎么搭」，不是可执行代码。 |
| **`docs/AWS_SETUP.md`** | **AWS 开通步骤**：Region、Budget、Bedrock Support | 操作 checklist，避免忘记绑卡或开错 Region。 |
| **`docs/PHASE_0.md`** | Phase 0 **手把手教程**（本文件） | 步骤 + 可粘贴源码。 |
| **`docs/PHASES.md`** | 各 Phase 文档 **索引** | 链接到 PHASE_0、未来的 PHASE_1… |
| **`infra/README.md`** | 占位：Phase 5 放 **CDK**（AWS 基础设施代码） | Phase 0 空的正常；以后 `cdk deploy` 建 S3、ECS 等。 |

---

### 不在仓库里的重要东西（故意不 commit）

| 路径 | 是什么 | 为什么不在 Git 里 |
|------|--------|-------------------|
| **`.venv/`** | 本机 Python 虚拟环境 | 体积大、每人路径不同；用 `pyproject.toml` 重装即可。 |
| **`.env`** | 你的 **真实** 密钥和邮箱 | 安全；只保留 `.env.example` 当模板。 |
| **`data/`、`sec-edgar-filings/`** | 下载的 SEC 原文（Phase 1+） | 可能很大；在 `.gitignore` 里。 |

---

### 和「四个配置文件」的对应关系

你提到的 **步骤 B 里 4 个配置类文件**，就是：

1. **`pyproject.toml`** — 依赖与工具配置  
2. **`.gitignore`** — Git 忽略规则  
3. **`.env.example`** — 环境变量模板  
4. （第 4 个若把 **CI** 算进去则是 **`.github/workflows/ci.yml`**；若只算根目录文本配置，则上面 3 个 + 根目录 **`README.md`** 也算「给人看的配置」）

下面 [步骤 B](#4-步骤-b配置文件非-python) 里每个文件代码块前，会再有一句 **「这个文件做什么」** 提醒。

---

## 2. 前置：GitHub 仓库

1. GitHub → **New repository** → 名：`sec-filings-agentic-rag-aws`
2. 本地：

```bash
cd "/path/to/your/workspace"
git clone https://github.com/Kellyxinyuwu/sec-filings-agentic-rag-aws.git
cd sec-filings-agentic-rag-aws
```

---

## 3. 步骤 A：创建目录

在仓库根目录执行（Mac/Linux）：

```bash
mkdir -p app scripts tests docs infra .github/workflows
touch app/__init__.py tests/__init__.py
```

**最终结构（Phase 0 结束时）：**

```
sec-filings-agentic-rag-aws/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api.py
│   ├── schemas.py
│   ├── config.py
│   └── logging_setup.py
├── scripts/
│   ├── local_dev.sh
│   └── README.md
├── tests/
│   ├── __init__.py
│   └── test_health.py
├── docs/
│   ├── ARCHITECTURE.md
│   ├── AWS_SETUP.md
│   └── PHASE_0.md          # 本文件
├── infra/
│   └── README.md
├── .github/workflows/ci.yml
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

---

## 4. 步骤 B：配置文件（非 Python）

> 先读 [§1.1 每个文件是干什么的](#11-phase-0-每个文件是干什么的建议先读) 里的总表。

### 4.1 `pyproject.toml`

**做什么：** 声明项目名、Python 版本、依赖库（FastAPI 等），以及 `pytest` / `ruff` 怎么跑。`pip install -e ".[dev]"` 读这个文件。

创建文件 `pyproject.toml`，粘贴：

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "sec-filings-agentic-rag-aws"
version = "0.1.0"
description = "Agentic RAG for SEC filings on AWS (Bedrock, OpenSearch, ECS)"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-dotenv>=1.0.0",
    "structlog>=24.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "httpx>=0.27.0",
    "ruff>=0.8.0",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["app*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
```

### 4.2 `.gitignore`

**做什么：** 列出 Git 应忽略的路径（`.venv`、`.env`、大数据目录），防止误提交密钥或巨型文件。

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.eggs/
dist/
build/
.venv/
venv/
.env

# IDE
.idea/
.vscode/
*.swp
.DS_Store

# Project data (do not commit filings or secrets)
data/
sec-edgar-filings/
*.pem

# AWS / CDK
infra/cdk.out/
infra/.venv/
cdk.context.json

# Test / coverage
.pytest_cache/
.coverage
htmlcov/
```

### 4.3 `.env.example`

**做什么：** 环境变量清单的**示例**（无真实密码）。复制为 `.env` 后填入你的 SEC 姓名邮箱和以后的 AWS 配置。

```bash
# App
APP_ENV=local
API_KEY=change-me-in-production
LOG_LEVEL=INFO

# AWS (Phase 2+)
AWS_REGION=us-east-1
# AWS_PROFILE=your-sso-profile

# Bedrock (Phase 2+)
# BEDROCK_CHAT_MODEL_ID=anthropic.claude-3-5-sonnet-20240620-v1:0
# BEDROCK_EMBED_MODEL_ID=amazon.titan-embed-text-v2:0

# OpenSearch / S3 (Phase 4+)
# OPENSEARCH_ENDPOINT=
# S3_BUCKET=

# SEC EDGAR (required for downloads — use real name/email)
SEC_COMPANY_NAME=Your Name or University
SEC_COMPANY_EMAIL=you@example.com
```

复制为本地配置：`cp .env.example .env`（**.env 不要 commit**）。

---

## 5. 步骤 C：Python 应用代码

> 各文件职责见 [§1.1](#11-phase-0-每个文件是干什么的建议先读) 的 `app/` 表格。

### 5.1 `app/__init__.py`

**做什么：** 标记 `app` 为 Python 包，使 `from app.xxx import ...` 生效。

```python
"""SEC filings agentic RAG application package."""
```

### 5.2 `app/schemas.py`

**做什么：** 用 Pydantic 定义 JSON 长什么样（请求、响应、Plan、证据块等）。全项目「数据合同」，改字段要慎重。

**每个类型含义：** 见 `app/schemas.py` 文件顶部的模块说明和各 class 的 docstring。

所有 API / agent 共用的数据类型。**Phase 3 之前不要删字段。**

```python
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class QueryIntent(str, Enum):
    QA = "qa"
    DIFF = "diff"
    SUMMARIZE = "summarize"
    REFUSE = "refuse"


class Plan(BaseModel):
    """Planner output — drives Researcher and Writer."""

    intent: QueryIntent = QueryIntent.QA
    need_retrieval: bool = True
    ticker: str | None = None
    filing_ids: list[str] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)
    rationale: str = ""


class EvidenceChunk(BaseModel):
    chunk_id: str
    filing_id: str
    ticker: str
    section: str
    excerpt: str
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidencePack(BaseModel):
    query: str
    chunks: list[EvidenceChunk] = Field(default_factory=list)


class Citation(BaseModel):
    chunk_id: str
    filing_id: str
    section: str
    excerpt: str


class AgentStep(BaseModel):
    step: str
    latency_ms: float | None = None
    detail: str | None = None


class ChatRequest(BaseModel):
    query: str
    ticker: str | None = None
    filing_ids: list[str] = Field(default_factory=list)
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    evidence: list[EvidenceChunk] = Field(default_factory=list)
    trace_id: str
    agent_steps: list[AgentStep] = Field(default_factory=list)
    plan: Plan | None = None
```

### 5.3 `app/config.py`

**做什么：** 从 `.env` 读取配置（region、SEC 邮箱、API key），集中在一个 `settings` 对象里。

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    api_key: str = "dev-key"
    log_level: str = "INFO"

    aws_region: str = "us-east-1"
    sec_company_name: str = "Your Name"
    sec_company_email: str = "you@example.com"


settings = Settings()
```

### 5.4 `app/logging_setup.py`

**做什么：** 配置 structlog，让 API 请求打印结构化日志（以后对接 CloudWatch）。

```python
import logging

import structlog


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
    )
```

### 5.5 `app/api.py`

**做什么：** 定义 URL 和处理函数：`/health` 探活，`/chat` 接收问题并返回答案（Phase 0 为 mock 数据）。

Phase 0 返回 **假数据**；Phase 3 改为调 `orchestrator`。

```python
import uuid

import structlog
from fastapi import APIRouter

from app.schemas import (
    AgentStep,
    ChatRequest,
    ChatResponse,
    Citation,
    EvidenceChunk,
    Plan,
    QueryIntent,
)

router = APIRouter()
log = structlog.get_logger()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "0"}


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Mock chat — replaced by orchestrator in Phase 3."""
    trace_id = str(uuid.uuid4())
    log.info("chat_request", trace_id=trace_id, query=request.query, ticker=request.ticker)

    plan = Plan(
        intent=QueryIntent.QA,
        need_retrieval=True,
        ticker=request.ticker,
        filing_ids=request.filing_ids,
        rationale="Phase 0 mock planner",
    )

    mock_chunk = EvidenceChunk(
        chunk_id="mock-chunk-1",
        filing_id="mock-filing-1",
        ticker=request.ticker or "AAPL",
        section="Item 1A — Risk Factors",
        excerpt="[Mock] Example risk factor excerpt for development.",
        score=0.99,
    )

    return ChatResponse(
        answer=(
            "[Mock response] Connect ingest + Bedrock + orchestrator in later phases. "
            f"Your question: {request.query!r}"
        ),
        citations=[
            Citation(
                chunk_id=mock_chunk.chunk_id,
                filing_id=mock_chunk.filing_id,
                section=mock_chunk.section,
                excerpt=mock_chunk.excerpt,
            )
        ],
        evidence=[mock_chunk],
        trace_id=trace_id,
        agent_steps=[
            AgentStep(step="planner", latency_ms=1.0),
            AgentStep(step="researcher", latency_ms=2.0),
            AgentStep(step="writer", latency_ms=3.0),
            AgentStep(step="verifier", latency_ms=1.0, detail="mock pass"),
        ],
        plan=plan,
    )
```

### 5.6 `app/main.py`

**做什么：** 应用入口：创建 FastAPI、开日志、注册 `api.py` 的路由。`uvicorn app.main:app` 启动的就是它。

```python
from fastapi import FastAPI

from app.api import router
from app.config import settings
from app.logging_setup import configure_logging

configure_logging(settings.log_level)

app = FastAPI(
    title="SEC Filings Agentic RAG",
    description="Agentic RAG over SEC EDGAR filings (AWS-backed)",
    version="0.1.0",
)
app.include_router(router)
```

---

## 6. 步骤 D：测试与 CI

### 6.1 `tests/__init__.py`

**做什么：** 可选；标记 `tests` 为包。留空即可。

### 6.2 `tests/test_health.py`

**做什么：** 自动测试 `/health` 和 `/chat` 是否返回 200 和必要字段；`pytest -q` 运行。

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_mock() -> None:
    response = client.post(
        "/chat",
        json={"query": "What are risk factors?", "ticker": "AAPL"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "answer" in body
    assert body["citations"]
    assert body["trace_id"]
```

### 6.3 `.github/workflows/ci.yml`

**做什么：** GitHub 在每次 push 时自动安装依赖、跑 ruff 和 pytest，远程代码质量与本机一致。

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install
        run: pip install -e ".[dev]"
      - name: Ruff
        run: ruff check app tests
      - name: Pytest
        run: pytest -q
```

### 6.4 `scripts/local_dev.sh`

**做什么：** Shell 快捷脚本：创建 venv、安装包、启动 `uvicorn`（端口 8000）。

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -e ".[dev]"
[[ -f .env ]] || cp .env.example .env

exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

终端执行：`chmod +x scripts/local_dev.sh`

---

## 7. 步骤 E：文档

- `README.md` — 项目目标、Quick start、**Phase progress 表**（见仓库根目录现有文件）
- `docs/ARCHITECTURE.md` — 目标架构（agent 角色）
- `docs/AWS_SETUP.md` — AWS 开通说明（含 Bedrock 新流程）
- `docs/PHASE_0.md` — 本手册

`infra/README.md`、`scripts/README.md` 各写一两句占位即可。

---

## 8. 步骤 F：本地安装与验证

```bash
cd sec-filings-agentic-rag-aws
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
pytest -q
ruff check app tests
uvicorn app.main:app --reload --port 8000
```

另开终端：

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the main risk factors?", "ticker": "AAPL"}'
```

**期望：** health 返回 `"status":"ok"`；chat 返回 `answer`、`citations`、`trace_id`、`agent_steps`（planner/researcher/writer/verifier）。

---

## 9. 步骤 G：Git 提交

```bash
git add .
git status   # 确认没有 .env / .venv
git commit -m "$(cat <<'EOF'
feat(phase-0): project skeleton and mock agentic RAG API

Add FastAPI app with /health and mock /chat (citations, trace_id, agent_steps),
Pydantic schemas for future multi-agent flow, config/logging, pytest + CI,
docs (architecture, AWS setup), and README phase tracker for build log.
EOF
)"
git push -u origin main
```

---

## 10. 步骤 H：AWS 准备（可选，建议 Phase 0 同期做）

**不阻塞 Phase 0 代码**；Bedrock 审批期间可先做 Phase 1（本地）。

| 步骤 | 操作 | 你的进度（可勾选） |
|------|------|-------------------|
| H1 | 注册/登录 AWS，Account ID 可见 | ✅ |
| H2 | Region 改为 **us-east-1**（不要用 Sydney 做 Bedrock） | ✅ |
| H3 | **Billing** → 绑定信用卡 | ✅ |
| H4 | **Budget** `sec-rag-monthly` **$20**，告警 **80% + 100%** → 邮箱 | ✅ |
| H5 | Bedrock **Model access** 页已废弃 → 无需勾选 | — |
| H6 | Anthropic **use case** 表单若报错 → 开 **Support case** | ✅ 已提交 |
| H7 | Playground 红条 *corporate customer* → 再开 **Support case**（Bedrock 总开通） | ✅ 2 cases |
| H8 | **等待** Support 邮件；期间 **Playground → Chat** 试 Nova/Titan | ⏳ |
| H9 | （可选）`aws configure` + `aws sts get-caller-identity` | 待做 |

Support case 正文模板见 [AWS_SETUP.md](./AWS_SETUP.md)。

**Claude vs Anthropic vs Bedrock：**

- **Anthropic** = 公司；**Claude** = 它的模型。
- **Bedrock** = AWS 上的模型平台；除 Claude 外还有 **Amazon Titan/Nova**、**Meta Llama** 等。
- 你当前是 **整个 Bedrock 账号级** 待开通，不是只缺 Claude。

---

## 11. 验收清单

- [ ] `pytest -q` 全绿
- [ ] `curl /health` 和 `curl /chat` 正常
- [ ] GitHub 有 Phase 0 commit
- [ ] `.env` 未提交到 git
- [ ] README Phase 0 Done notes 已填写
- [ ] AWS：信用卡 + Budget（Bedrock 可等待）

---

## 12. 常见问题

**Q: `ModuleNotFoundError: app`**  
在仓库根目录执行，且已 `pip install -e ".[dev]"`。

**Q: Copilot 改了 schemas 字段名**  
以本文 `schemas.py` 为准，否则 tests 和后续 Phase 会对不上。

**Q: Playground Run 灰色**  
账号 Bedrock 未开通，等 Support；用 **Chat** 标签，不要 **Image**。

**Q: Phase 0 必须等 Bedrock 吗？**  
不必。Phase 1 用本地 pgvector + Ollama 即可。

---

## 下一步

→ **[PHASE_1.md](./PHASE_1.md)**（将添加）或根目录 README Phase 1：EDGAR ingest + `app/tools.py`。
