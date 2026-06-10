# Phase 1 — EDGAR ingest + 本地检索

> **状态：** ✅ 已完成（2026-06-10）  
> **LLM：** Phase 1 **不用** Mantle / Bedrock；生成在 **Phase 2** 接 Mantle（见 [BEDROCK_MANTLE_VS_RUNTIME.md](./BEDROCK_MANTLE_VS_RUNTIME.md)）

### 怎么用这个文档（和 Chat 分工）

| 在哪 | 内容 |
|------|------|
| **Chat（Cursor）** | 每一步的 **完整代码** + 行内讲解 → 你复制粘贴到文件 |
| **本文 PHASE_1.md** | 每一步 **做什么、为什么、验证什么**（**不放代码**）+ 做完后的 **实现笔记** |
| **README.md** | 仅 **整 Phase 完成** 时更新状态（不在 README 里记逐步笔记） |

流程：读本文对应 Step → Chat 拿代码 → 粘贴 → 验证 → 在本文该 Step 下写 **实现笔记**、更新 §11 步骤总览表 → 下一步 Chat。

---

## 目录

1. [Phase 0 回顾 vs Phase 1 目标](#1-phase-0-回顾-vs-phase-1-目标)
2. [Phase 1 一句话](#2-phase-1-一句话)
3. [要做什么 / 不做什么](#3-要做什么--不做什么)
4. [任务清单（checkbox）](#4-任务清单checkbox)
5. [会新增/修改哪些文件](#5-会新增修改哪些文件)
6. [和旧项目 SEC-10-K-RAG 的关系](#6-和旧项目-sec-10-k-rag-的关系)
7. [步骤顺序（建议按天）](#7-步骤顺序建议按天)
8. [验收标准](#8-验收标准)
9. [和 Phase 2（Mantle）的衔接](#9-和-phase-2mantle-的衔接)
10. [7 天入职前优先级](#10-7-天入职前优先级)
11. [分步讲解（无代码）](#11-分步讲解无代码)

---

## 1. Phase 0 回顾 vs Phase 1 目标

### Phase 0 你已经有什么？

| 类别 | 已完成 |
|------|--------|
| **架构（文档）** | `docs/ARCHITECTURE.md` — agent 角色、AWS 目标态 |
| **目录** | `app/`、`scripts/`、`tests/`、`docs/`、`infra/`（占位） |
| **数据契约** | `app/schemas.py` — `ChatRequest`、`Plan`、`EvidenceChunk` 等 |
| **API 骨架** | `GET /health`、`POST /chat`（**mock**，假 citation） |
| **工程** | `pyproject.toml`、pytest、CI、`.env.example` |
| **AWS 笔记** | Support、Mantle vs Runtime 等 |

### Phase 0 还没有什么？

- 真实 SEC 文件
- 向量库
- `retrieve()` / `app/tools.py`
- Agent orchestrator
- 真实 LLM 回答

### Phase 1 要补上什么？

**第一次有真数据、真能搜到 SEC 原文。**

---

## 2. Phase 1 一句话

把 **1 家公司** 的 **10-K** 从 EDGAR 拉下来 → **切块 + metadata** → 写入 **本地 pgvector** → API 能 **`retrieve`** 到真实的 `EvidenceChunk`。

---

## 3. 要做什么 / 不做什么

### ✅ Phase 1 要做

| # | 事项 |
|---|------|
| 1 | `.env` 配置 SEC 姓名邮箱、`DATABASE_URL` |
| 2 | Docker **pgvector** 本地库 |
| 3 | `scripts/ingest_edgar.py` — 下载 + 解析 + chunk + embed + 入库 |
| 4 | `app/tools.py` — `retrieve()`、`get_section()`（后者可选） |
| 5 | `app/store.py`（或 `db.py`）— 连 Postgres |
| 6 | `POST /retrieve` — 返回真实 chunks |
| 7 | `tests/test_retrieve.py` |

### ❌ Phase 1 不做

| 事项 | 放到哪 |
|------|--------|
| Mantle / Bedrock 生成答案 | Phase 2 |
| 完整 agent orchestrator | Phase 3 |
| S3 / OpenSearch / ECS | Phase 4–5 |
| `/chat` 真答案（可先仍 mock，只换真 evidence） | Phase 2 |

**MVP ticker：** 建议先 **AAPL**，**1 份 10-K**（范围小、好 debug）。

---

## 4. 任务清单（checkbox）

完成一项勾一项；逐步 **实现笔记** 写在本文 §11 各 Step 下（整 Phase 验收通过后再填 `README.md` Phase 1 的 Done notes）。

### A. 环境与配置

- [x] `cp .env.example .env`
- [x] 填写 `SEC_COMPANY_NAME`、`SEC_COMPANY_EMAIL`（EDGAR 要求真实信息）
- [x] 填写 `DATABASE_URL`（例：`postgresql://postgres:postgres@localhost:5433/rag_db`）
- [x] `pyproject.toml` 增加依赖（见下方）
- [x] `docker-compose.yml` — 仅 `db` 服务即可（Phase 1 本地 uvicorn）

**Phase 1 额外依赖（计划加入 `pyproject.toml`）：**

```
psycopg2-binary
pgvector
sentence-transformers
tiktoken
# EDGAR 下载（二选一，实现时定）:
# sec-edgar-downloader  或  沿用 SEC-10-K-RAG 脚本逻辑
```

### B. 数据管道 `scripts/ingest_edgar.py`

- [x] 从 EDGAR 下载指定 ticker 的 10-K（遵守 rate limit、User-Agent）
- [x] 解析 `full-submission.txt`（或等价原文）
- [x] **Chunk**：建议 400 tokens / 100 overlap（与旧项目一致，可改）
- [x] **Metadata**：`ticker`、`filing_id`、`section`（Item 1A、7 等，能识别多少算多少）
- [x] **Embed**：`sentence-transformers`（如 `all-MiniLM-L6-v2`）— 本地，不花钱
- [x] 写入 pgvector `documents` 表

**运行方式（目标）：**

```bash
python scripts/ingest_edgar.py --ticker AAPL
```

### C. 检索层 `app/`

- [x] `app/store.py` — DB 连接、向量查询
- [x] `app/tools.py`
  - `retrieve(query, ticker=None, top_k=5) -> list[EvidenceChunk]`
  - `get_section(filing_id, section)` — 可选 stretch（未做）
- [x] `app/config.py` — 增加 `database_url`

### D. API

- [x] `POST /retrieve` — body：`{"query": "...", "ticker": "AAPL", "top_k": 5}`
- [x] 响应：`RetrieveResponse`（`query` + `chunks: list[EvidenceChunk]`）
- [x] （可选）`/chat` 仍返回 mock `answer`，但 `evidence` 改为 `retrieve()` 真结果

### E. 测试

- [x] `tests/test_retrieve.py` — mock `app.api.retrieve`，CI 无需 Postgres
- [x] 手动 `curl` 见 [验收标准](#8-验收标准)

---

## 5. 会新增/修改哪些文件

```
sec-filings-agentic-rag-aws/
├── docker-compose.yml          # 新建 — pgvector on :5433
├── docker/init-db.sql          # 新建 — CREATE EXTENSION vector; 建表
├── scripts/ingest_edgar.py     # 新建
├── app/
│   ├── tools.py                # 新建
│   ├── store.py                # 新建
│   ├── api.py                  # 修改 — 加 POST /retrieve
│   └── config.py               # 修改 — DATABASE_URL
├── tests/test_retrieve.py      # 新建
├── pyproject.toml              # 修改 — 新依赖
└── .env.example                # 修改 — DATABASE_URL 示例
```

**Phase 1 不建：** `orchestrator.py`、`llm.py`、`agents/`（Phase 2/3）。

---

## 6. 和旧项目 SEC-10-K-RAG 的关系

> **完整对比（含路线图、面试话术）：** [OLD_VS_NEW_PROJECT.md](./OLD_VS_NEW_PROJECT.md) — 随 Phase 2–5 持续更新。

旧项目路径（本机）：`../SEC-10-K-RAG/`

| 旧文件 | Phase 1 怎么用 |
|--------|----------------|
| `scripts/download_financial_docs.py` | 参考 EDGAR 下载、User-Agent |
| `src/tiny_rag/ingest.py` | 参考 chunk、embed、pgvector 写入 |
| `src/tiny_rag/retrieve.py` | 参考向量检索 SQL |
| `docker-compose.yml` | 参考 pgvector 服务（端口 5433） |

**策略：** 逻辑**迁移/简化**到新 repo，不 fork 整个旧项目；新 repo 的 chunk 要带 **`section` metadata**（为 agent / citation 服务）。

---

## 7. 步骤顺序（建议按天）

| 顺序 | 做什么 | 预计 |
|------|--------|------|
| 1 | `.env` + `docker-compose.yml` → `docker compose up -d db` | 0.5 天 |
| 2 | `init-db.sql` + 能连上 DB | 0.5 天 |
| 3 | `ingest_edgar.py` 下载 AAPL 10-K | 0.5 天 |
| 4 | chunk + embed + 入库 | 0.5 天 |
| 5 | `store.py` + `tools.retrieve()` | 0.5 天 |
| 6 | `POST /retrieve` + tests | 0.5 天 |

合计约 **2–3 天**（含调试）；7 天计划里 Phase 1 应 **优先完成**。

---

## 8. 验收标准

### 自动测试

```bash
pytest tests/test_retrieve.py -q
```

### 手动流程

```bash
# 1. 数据库
docker compose up -d db

# 2. Ingest（需先装好依赖、配好 .env）
python scripts/ingest_edgar.py --ticker AAPL

# 3. 起 API（macOS 若 :8000 Empty reply，用 8001 + 127.0.0.1）
uvicorn app.main:app --reload --port 8001

# 4. 检索
curl http://127.0.0.1:8001/health
curl -X POST http://127.0.0.1:8001/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the main risk factors?", "ticker": "AAPL", "top_k": 5}'
```

### 通过条件

- [x] 返回 **真实** chunks（不是 `mock-chunk-1`）
- [x] 每条含 `chunk_id`、`ticker`、`section`、`excerpt`
- [x] 问 risk factors 时，top 结果与 **Item 1A / Risk** 相关
- [x] `pytest -q` 全绿（含 Phase 0 测试）

---

## 9. 和 Phase 2（Mantle）的衔接

```
Phase 1（本阶段）          Phase 2（下一步）
─────────────────          ─────────────────
EDGAR → chunk            Mantle（Qwen）根据 evidence 生成 answer
→ pgvector               app/llm.py（provider 抽象）
→ retrieve()             调用 Phase 1 的 tools，不改 schemas
```

Phase 1 把 **检索 + EvidenceChunk** 做扎实，Phase 2 只换「谁写 `answer`」。

环境切换（Phase 2 再配）：

```bash
LLM_PROVIDER=mantle
MANTLE_MODEL_ID=qwen3-coder-...
```

---

## 10. 7 天入职前优先级

| 优先级 | 内容 |
|--------|------|
| **必做** | 完成本 Phase 1 验收 |
| **必做（随后）** | Phase 2：`llm.py` + Mantle +  grounded answer |
| **必做（随后）** | Phase 3 精简 agent loop |
| **可砍** | OpenSearch、ECS/CDK — 写 README Future work |
| **不要等** | Classic Bedrock Support 才做 Phase 1 |

---

## 相关文档

- [PHASE_0.md](./PHASE_0.md) — 已完成骨架
- [PHASES.md](./PHASES.md) — 各 Phase 索引
- [ARCHITECTURE.md](./ARCHITECTURE.md) — 目标架构
- [BEDROCK_MANTLE_VS_RUNTIME.md](./BEDROCK_MANTLE_VS_RUNTIME.md) — Phase 2 LLM 路径
- [schemas.py 说明](../app/schemas.py) — `EvidenceChunk` 等契约

---

## Done notes（完成后填写）

- 日期：
- Commit：
- Ticker ingested：
- 心得：

---

## 11. 分步讲解（无代码）

> **代码在 Chat 里按 Step 给。** 下面只写概念、原因、验证；实现时打开 Chat 对应 Step。

### 数据流（Phase 1 全貌）

```
EDGAR (sec-edgar-downloader)
    → full-submission.txt
    → chunk (tiktoken) + section 猜测
    → embed (SentenceTransformers, 本地)
    → PostgreSQL + pgvector (documents 表)

用户 POST /retrieve
    → tools.retrieve()
    → embed query → SQL 向量相似度
    → list[EvidenceChunk] JSON
```

### 步骤总览

| Step | 主题 | 主要文件 | 状态 |
|------|------|----------|------|
| 1 | 依赖 + 环境变量 | `pyproject.toml`, `.env.example`, `.env` | ✅ 2026-06-08 |
| 2 | Docker pgvector | `docker-compose.yml`, `docker/init-db.sql` | ✅ 2026-06-10 |
| 3 | 配置扩展 | `app/config.py` | ✅ 2026-06-10 |
| 4 | 数据库层 | `app/store.py` | ✅ 2026-06-10 |
| 5 | 下载与入库 | `scripts/ingest_edgar.py` | ✅ 2026-06-10 |
| 6 | 检索工具 | `app/tools.py` | ✅ 2026-06-10 |
| 7 | API 契约 | `app/schemas.py` | ✅ 2026-06-10 |
| 8 | API 路由 | `app/api.py` | ✅ 2026-06-10 |
| 9 | 测试 | `tests/test_retrieve.py` | ✅ 2026-06-10 |
| 10 | 端到端验收 | curl + pytest | ✅ 2026-06-10 |

---

### Step 1 — 依赖与环境变量

**目标：** 装上 Phase 1 需要的 Python 包，并准备好 `.env`。

**为什么要做：** Phase 0 只有 FastAPI；Phase 1 需要连 Postgres、存向量、下载 SEC、按 token 切块。

**要改什么：**

- `pyproject.toml`：增加 `psycopg2-binary`、`pgvector`、`sentence-transformers`、`tiktoken`、`numpy`、`sec-edgar-downloader`
- `.env.example`：增加 `DATABASE_URL`、`EMBEDDING_MODEL`
- `.env`：复制 example，填写 **真实** `SEC_COMPANY_NAME`、`SEC_COMPANY_EMAIL`（EDGAR 强制要求）

**各包作用简述：**

| 包 | 作用 |
|----|------|
| psycopg2-binary | 连接 PostgreSQL |
| pgvector | 在 Postgres 里存/查 embedding 向量 |
| sentence-transformers | 本地生成向量（不调用 Bedrock，省钱） |
| tiktoken | 按 token 切 10-K 正文 |
| sec-edgar-downloader | 合规下载 10-K |

**验证：** `pip install -e ".[dev]"` 成功；`.env` 已存在且 SEC 字段已填。

**本步不做：** Docker、任何 `.py` 业务代码。

**实现笔记（2026-06-08）：**

- `pyproject.toml` 已追加：`psycopg2-binary`、`pgvector`、`sentence-transformers`、`tiktoken`、`numpy`、`sec-edgar-downloader`（保留 Phase 0 的 FastAPI 等依赖）。
- `.env.example` / `.env`：`DATABASE_URL=postgresql://postgres:postgres@localhost:5433/rag_db`，`EMBEDDING_MODEL=all-MiniLM-L6-v2`；SEC 姓名邮箱已填（EDGAR 合规）。
- `pip install -e ".[dev]"` 成功；`pytest -q` → **2 passed**。
- `StarletteDeprecationWarning`（`httpx` → `httpx2`）：库层面提示，可忽略；可选 `pip install httpx2` 消警告。
- 当前 venv 为 **Python 3.14**；若 Step 5 装 `sentence-transformers` 遇 wheel 问题，可改用 3.11/3.12 重建 venv。

---

### Step 2 — Docker pgvector

**目标：** 本机起一个带 `vector` 扩展的 Postgres，端口 **5433**（避免和本机 5432 冲突）。

**要新建：** `docker-compose.yml`（仅 `db` 服务）、`docker/init-db.sql`（`CREATE EXTENSION vector`）。

**为什么表不在 SQL 里建：** 表结构放 `app/store.py` 的 `init_schema()`，改字段时不用重建 Docker 卷。

**验证：** `docker compose up -d db`，`docker compose ps` 显示 healthy。

**实现笔记（2026-06-10）：**

| 子步骤 | 做了什么 | 目的 |
|--------|----------|------|
| `mkdir -p docker` | 建 `docker/` 目录 | 放数据库初始化 SQL |
| 新建 `docker-compose.yml` | 定义 `db` 服务：`pgvector/pgvector:pg16`，库名 `rag_db`，端口 `5433:5432`，卷 `pgdata`，healthcheck | 本机起一个专用向量库，和 Step 1 的 `DATABASE_URL` 对齐；**不**把 FastAPI 放进 Docker，调试更简单 |
| 新建 `docker/init-db.sql` | `CREATE EXTENSION IF NOT EXISTS vector` | 首次启动空卷时启用 pgvector；**不**在此建表（表在 Step 4 `store.py`） |
| `docker compose up -d db` | 后台拉镜像并启动容器 | 数据库常驻，供 ingest / retrieve 连接 |
| `docker compose ps` | 看 `db` 是否 **healthy** | 确认 healthcheck 通过再写 Python 连库代码 |
| `docker compose exec db psql ... SELECT version()` | 进容器查 Postgres 版本 | 端到端确认能连上、库存在 |

**验收结果：**

- `docker compose ps` → `db` **healthy**，端口 `5433`
- `SELECT version()` → **PostgreSQL 16.12**（`pgvector/pgvector:pg16` 镜像，正常）
- 终端底部 `(END)` 是 `psql` 分页器，按 **`q`** 退出即可

**本步不做：** `app/store.py` 建表、ingest、任何 API 改动。

---

### Step 3 — 配置扩展 `app/config.py`

**目标：** 让 `settings.database_url` 和 `settings.embedding_model` 从 `.env` 读取。

**原则：** 全项目 `from app.config import settings`，不散落 `os.getenv`。

**验证：** `python -c "from app.config import settings; print(settings.database_url)"` 打印 5433 连接串。

**实现笔记（2026-06-10）：**

| 子步骤 | 做了什么 | 目的 |
|--------|----------|------|
| 扩展 `Settings` | 增加 `database_url`、`embedding_model` 字段 | Phase 1 连库与 embed 统一从 `settings` 读，不散落 `os.getenv` |
| 保留 Phase 0 字段 | `app_env`、`api_key`、`sec_company_*` 等不动 | Step 5 ingest 会用 `sec_company_name/email` |
| 默认值对齐 `.env.example` | 5433 连接串、`all-MiniLM-L6-v2` | 无 `.env` 时本地默认值仍合理 |
| `python -c` 验证 | 打印 `database_url`、`embedding_model` | 确认 Pydantic 正确映射 `DATABASE_URL` / `EMBEDDING_MODEL` |
| `pytest -q` | 2 passed | 本步未改 API，回归通过 |

**本步不做：** 建表、embed、检索（Step 4 `store.py`）。

---

### Step 4 — 数据库层 `app/store.py`

**一句话：** 把 10-K 的**小段文字**变成**数字向量**存进 Postgres；用户提问时，用「向量有多像」找出最相关的原文段落。这就是 RAG 里的 **Retrieval（检索）** 的地基。

**本步在整条链路中的位置：**

```
Step 5 ingest          Step 6 retrieve         Step 8 API
     │                        │                      │
     ▼                        ▼                      ▼
insert_chunks()  ◄── store.py ──►  search_similar() ──► /retrieve
     │                        │
     └──── embed_texts()      └──── embed_query()
              │                        │
              └──────── 同一 embedding 模型 ────────┘
```

`store.py` **不负责**：下载 SEC（Step 5）、HTTP 路由（Step 8）、LLM 生成答案（Phase 2）。它只管 **数据库 + 向量**。

---

#### 为什么要单独建这个文件？

| 原因 | 说明 |
|------|------|
| **避免重复** | ingest 和 retrieve 都要连库、都要 embed；写在一起，两处调用即可 |
| **配置统一** | 全用 `settings.database_url`、`settings.embedding_model`，不散落 `os.getenv` |
| **表结构集中** | `init_schema()` 在 Python 里建表；改字段不用删 Docker 卷重建 |
| **和 schema 对齐** | 表字段对应 `EvidenceChunk`（chunk_id、ticker、section、excerpt 等） |

---

#### 两条数据流（建议对照 `app/store.py` 顶部注释读）

**路径 A — 写入（Step 5 ingest 会走这条）**

1. 10-K 全文已被切成很多 **chunk**（小段文字）
2. `embed_texts(chunks)`：每段文字 → **384 个浮点数**（一个向量）
3. `insert_chunks(...)`：向量 + 原文 + ticker/filing_id 等 → 写入 `documents` 表

**路径 B — 查询（Step 6 retrieve 会走这条）**

1. 用户问题，如 *"What are the main risk factors?"*
2. `embed_query(query)`：问题也变成 **同样长度** 的向量
3. `search_similar(...)`：在库里找和问题向量 **最接近** 的 k 条 chunk → 当作证据返回

**关键规则：** 路径 A 和 B 必须用 **同一个 embedding 模型**（`.env` 里 `EMBEDDING_MODEL=all-MiniLM-L6-v2`）。模型不一致 = 向量空间对不上 = 检索没有意义。

---

#### `documents` 表：一行是什么？

表里 **一行 = 一个 chunk**（一小段 10-K + 它的向量 + 出处）。

| 列 | 含义 | 对应 API |
|----|------|----------|
| `chunk_id` | 唯一 ID，引用时用 | `EvidenceChunk.chunk_id` |
| `content` | chunk 原文 | API 里叫 `excerpt` |
| `embedding` | `vector(384)`，pgvector 列 | 不直接返回给前端 |
| `ticker` | 如 AAPL | `EvidenceChunk.ticker` |
| `filing_id` | SEC accession 号 | `EvidenceChunk.filing_id` |
| `section` | Item 1A / Item 7 等 | `EvidenceChunk.section` |
| `source` | 来源文件路径 | 调试用，可放进 metadata |

为什么是 **384 维**？`all-MiniLM-L6-v2` 固定输出 384 个数；`CREATE TABLE` 里必须写 `vector(384)`，维度和模型不一致会 insert 失败。

---

#### 各函数干什么？（按建议阅读顺序）

| 函数 | 谁调用 | 做什么 |
|------|--------|--------|
| `get_connection()` | 内部 | 用 Step 3 的 `database_url` 连 Docker Postgres（5433） |
| `embed_texts()` | `insert_chunks` | 批量：多段文字 → 多个向量（ingest） |
| `embed_query()` | `search_similar` | 单个：问题 → 一个向量（retrieve） |
| `init_schema()` | ingest / 验证脚本 | 启用 pgvector 扩展 + 建 `documents` 表（可重复执行） |
| `infer_section()` | `insert_chunks` | 用正则看 chunk 开头像不像 Item 1A；猜不到就 `Unknown` |
| `insert_chunks()` | Step 5 | embed → INSERT；相同 `chunk_id` 会 UPSERT 更新 |
| `search_similar()` | Step 6 | 向量相似度 Top-K，返回 dict 列表 |

**懒加载模型：** `_get_embedding_model()` 只在**第一次**真正 embed 时才下载/加载 SentenceTransformer（几百 MB）。`import store` 不会立刻拖慢启动；pytest 测 API 若不碰 store 也不受影响。

---

#### 三个容易懵的概念

**1. `register_vector(conn)`**

普通 psycopg2 不知道 Postgres 的 `vector` 类型。这行告诉驱动：插入/查询时要把 Python 的 numpy 数组和数据库的 vector 列互相转换。没有它，insert 向量会报错。

**2. pgvector 的 `<=>`（余弦距离）**

- 语义相近的句子，embedding 模型会给 **相近** 的向量
- `<=>` 算两个向量有多 **不像**：**距离越小 = 越相似**（0 表示完全相同）
- SQL：`ORDER BY embedding <=> 问题向量 LIMIT k` → 取最相关的 k 段
- 返回给 API 的 `score = 1 - 距离`，**越大越相关**（方便展示）

**3. `ON CONFLICT (chunk_id) DO UPDATE`**

重复跑 ingest（相同 chunk_id）不会插重复行，而是 **更新** 内容和向量。Step 5 用 `AAPL-accession-00001` 这种稳定 ID，就是为了可重复 ingest。

---

#### 和其他 Step 的关系

| Step | 关系 |
|------|------|
| Step 2 Docker | 提供 Postgres + pgvector 扩展 |
| Step 3 config | 提供 `database_url`、`embedding_model` |
| Step 5 ingest | 下载切块后调 `insert_chunks()` |
| Step 6 tools | 调 `search_similar()`，包装成 `EvidenceChunk` |
| Step 8 api | 通过 tools 暴露 `POST /retrieve` |

---

**验证：** Docker `db` 已 healthy 时，在项目根执行 `init_schema()` 不报错；可选 `\d documents` 看到 `embedding vector(384)` 列。

**实现笔记（2026-06-10）：**

| 子步骤 | 做了什么 | 目的 |
|--------|----------|------|
| 新建 `app/store.py` | 集中 DB + embed + 检索逻辑 | ingest / retrieve 共用一层，避免重复连库代码 |
| `init_schema()` | `documents` 表：`chunk_id`, `content`, `embedding vector(384)`, `ticker`, `filing_id`, `section`, `source` | 与 `EvidenceChunk` 字段对齐；表在 Python 里建，改 schema 不用重建 Docker 卷 |
| `embed_texts` / `embed_query` | 懒加载 `sentence-transformers`，模型名来自 `settings.embedding_model` | ingest 与 retrieve 必须用同一模型 |
| `infer_section()` | 正则猜 Item 1A / 7 等 | Phase 1 粗粒度 metadata，够 demo |
| `insert_chunks()` | embed + UPSERT | Step 5 ingest 直接调用 |
| `search_similar()` | pgvector `<=>`，`score = 1 - distance` | Step 6 `tools.retrieve` 的数据来源 |
| `python -c init_schema()` | 无报错 | 确认 Docker DB 可连、表已创建 |

**本步不做：** 下载 SEC、API `/retrieve`（Step 5–8）。

---

### Step 5 — 下载与入库 `scripts/ingest_edgar.py`

**目标：** 一条命令：`AAPL` 10-K → 切块 → 向量 → 入库。

**流程：** `sec-edgar-downloader` → `full-submission.txt` → tiktoken 切块（400/100）→ embed → `insert_chunks`。

**常见问题（是否抓 SEC 网站、一家 vs 多家、`--skip-download`）：** [INGEST_EDGAR_FAQ.md](./INGEST_EDGAR_FAQ.md)

**验证：** 终端输出 `Ingested N chunks for AAPL / ...`。

**实现笔记（2026-06-10）：**

| 子步骤 | 做了什么 | 目的 |
|--------|----------|------|
| 新建 `scripts/ingest_edgar.py` | CLI：`--ticker`、`--skip-download` | 一条命令完成 download → chunk → embed → 入库 |
| `sec-edgar-downloader` | `Downloader(name, email, PROJECT_ROOT)` | SEC 合规 User-Agent；**第 3 参数是父目录**，库内会再建 `sec-edgar-filings/` |
| 路径 bug 修复 | 勿传 `FILINGS_DIR` 作第 3 参数；`find_filing_paths` 用 `rglob` | 避免 `sec-edgar-filings/sec-edgar-filings/...` 找不到文件 |
| `.env` 修正 | `SEC_COMPANY_NAME=Kelly Wu`（`=` 后无空格） | 防止 User-Agent 带前导空格 |
| `python ... --skip-download` | 读已有 `full-submission.txt` | 下载成功后重跑 embed 可跳过 EDGAR |
| 验收 | `Ingested **10834** chunks for AAPL / **0000320193-25-000079**` | 约 9MB 原文 → 10834 行 in `documents` |
| HF Hub warning | 未设 `HF_TOKEN` | 可忽略；首次下载 MiniLM 仍成功 |

**本步不做：** `app/tools.py`、`POST /retrieve`（Step 6–8）。

---

### Step 6 — 检索工具 `app/tools.py`

**一句话：** 把 Step 4 的「数据库检索」包装成 **业务层接口** — 问一句话，拿回 `EvidenceChunk` 列表（带 citation 字段）。

**本步在链路中的位置：**

```
用户问题 "What are the risk factors?"
        │
        ▼
  tools.retrieve(query, ticker="AAPL")     ← Step 6（本步）
        │
        ▼
  store.search_similar()                   ← Step 4
        │
        ▼
  list[EvidenceChunk]                      ← 给 Step 8 API / Phase 3 Researcher
```

**为什么要 `tools.py`，不直接在 API 里调 `store`？**

| 层 | 文件 | 职责 |
|----|------|------|
| 数据层 | `store.py` | SQL、向量、embed；返回 `dict` |
| 工具层 | `tools.py` | **稳定对外接口**；返回 `EvidenceChunk` |
| HTTP | `api.py`（Step 8） | 路由、状态码、JSON |
| Agent | `researcher`（Phase 3） | 调 `tools.retrieve()`，不写 SQL |

以后换 OpenSearch（Phase 4）只改 `store.py`，`tools.retrieve()` 签名不变，API 和 agent 不用动。

**`retrieve()` 做什么（三步）：**

1. 调用 `search_similar(query, ticker, top_k)`
2. 问题 embed → pgvector 找 Top-K 相似 chunk（Step 5 入库的那些）
3. 每个 `dict` 转成 `EvidenceChunk`（`excerpt`、`score`、`section` 等）

**验证：** `retrieve("risk factors", ticker="AAPL")` 非空；`pytest -q` 仍 2 passed。

**实现笔记（2026-06-10）：**

- 新建 `app/tools.py`，实现 `retrieve(query, *, ticker=None, top_k=5) -> list[EvidenceChunk]`
- 内部只调 `store.search_similar`，不做 embed/SQL（保持薄封装）
- Phase 1 建议始终传 `ticker="AAPL"`（目前只 ingest 了一家）
- `get_section()` 未实现（可选 stretch）

**本步不做：** `RetrieveRequest` schema、`POST /retrieve`（Step 7–8）。

---

### Step 7 — API 契约 `app/schemas.py`

**目标：** 增加 `RetrieveRequest`、`RetrieveResponse`。

**验证：** `python -c` import 两个 model；`pytest -q` 仍通过。

**实现笔记（2026-06-10）：**

| 子步骤 | 做了什么 | 目的 |
|--------|----------|------|
| `RetrieveRequest` | `query`, `ticker?`, `top_k`（默认 5，`ge=1, le=20`） | Step 8 `POST /retrieve` 的请求体 |
| `RetrieveResponse` | `query` + `chunks: list[EvidenceChunk]` | HTTP 响应契约；与 agent 用的 `EvidenceChunk` 一致 |
| 与 `EvidencePack` 分工 | Pack 给 agent 内部；Retrieve* 给 REST API | 边界清晰，OpenAPI 文档可读 |

**本步不做：** 路由、`curl`（Step 8–10）。

---

### Step 8 — API 路由 `app/api.py`

**目标：** `POST /retrieve`；`/health` 的 `phase` 改为 `"1"`。

**可选：** `/chat` 的 `evidence` 改用真 `retrieve()`，`answer` 仍 mock（Phase 2 再接 Mantle）。

**实现笔记（2026-06-10）：**

| 子步骤 | 做了什么 | 目的 |
|--------|----------|------|
| `POST /retrieve` | 读 `RetrieveRequest` → 调 `tools.retrieve()` → 返回 `RetrieveResponse` | Phase 1 纯检索 API，OpenAPI 有 schema |
| structlog | `api.py` / `store.py` 用 `structlog.get_logger()` | 结构化日志；避免 `logging` + kwargs 的 `TypeError` |
| `/health` | `phase: "1"` | 区分 Phase 0 mock |
| `/chat` | `evidence` 来自真 `retrieve()`；DB 空时 fallback mock chunk | 演示真 citation；无 ingest 也不 500 |
| 验证 | `curl` `:8001/health`、`POST /retrieve`（AAPL risk factors）→ 3 条真 chunk，score ~0.39–0.42 | 本地 E2E；若 `:8000` Empty reply 用 `127.0.0.1:8001` |
| IDE | basedpyright 报 `structlog` → 选解释器 `sec-filings-agentic-rag-aws/.venv` | 非运行时问题 |

**本步不做：** pytest retrieve（Step 9）、整 Phase 验收（Step 10）。

---

### Step 9 — 测试 `tests/test_retrieve.py`

**目标：** mock DB，保证 CI 无 Postgres 也能绿；本机再用 curl 做集成测。

**实现笔记（2026-06-10）：**

| 子步骤 | 做了什么 | 目的 |
|--------|----------|------|
| 5 个 pytest | health `phase`、retrieve 200/结构、默认 `top_k`、422 校验、空列表 | 覆盖 API 契约，不加载 embedding |
| mock 位置 | `monkeypatch.setattr(app.api, "retrieve", mock)` | `api.py` 用 `from tools import retrieve`，须 patch **使用方** `app.api.retrieve` |
| 验证 | `pytest -q` → **7 passed**（含 Phase 0 的 2 个） | Step 9 完成 |

**本步不做：** 真 DB 集成测（Step 10 curl）。

---

### Step 10 — 端到端验收

见 [§8 验收标准](#8-验收标准)。通过 = Phase 1 完成。

**实现笔记（2026-06-10）：**

| 子步骤 | 做了什么 | 结果 |
|--------|----------|------|
| Docker | `docker compose up -d db` → `docker compose ps` | `db` **Up (healthy)**，`:5433` |
| pytest | `pytest -q` | **7 passed**（Phase 0 ×2 + Step 9 ×5） |
| `/health` | `curl http://127.0.0.1:8001/health` | `{"status":"ok","phase":"1"}` |
| `/retrieve` | AAPL risk factors，`top_k=3` | 3 条真 chunk；例 `AAPL-0000320193-25-000079-00217`，score ~0.42 |
| `/chat` | 同 query | `evidence` 5 条真 chunk（非 mock）；`answer` 仍为 Phase 2 mock 前缀 |
| 注意 | zsh 里行尾 `# 注释` 可能不被当注释 | `docker compose ps` 单独跑，勿跟 `#` |
| 注意 | uvicorn 须在 **项目目录** 或正确 `PYTHONPATH` | 否则 watch 错目录 |

**Phase 1 完成。** 下一步 Phase 2：Bedrock Mantle 生成真答案 + grounded citations。

---

#### 附录：`tests/test_retrieve.py`（Step 9 测试代码存档）

CI 用 mock，不连 Postgres。关键：patch **`app.api.retrieve`**（不是 `app.tools.retrieve`）。

```python
"""
Tests for POST /retrieve.

CI: monkeypatch app.api.retrieve — no Postgres, no SentenceTransformer load.
Local integration: curl against running API + ingested DB (Step 10).
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import EvidenceChunk

client = TestClient(app)

SAMPLE_CHUNK = EvidenceChunk(
    chunk_id="chunk-test-1",
    filing_id="0000320193-25-000079",
    ticker="AAPL",
    section="Item 1A",
    excerpt="Risk factors include supply chain and competition.",
    score=0.85,
)


@pytest.fixture
def mock_retrieve(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace DB search with a fixed chunk — keeps CI offline."""
    from app import api

    mock = MagicMock(return_value=[SAMPLE_CHUNK])
    # api.py does `from app.tools import retrieve` — patch the name api uses.
    monkeypatch.setattr(api, "retrieve", mock)
    return mock


def test_health_phase_1() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["phase"] == "1"


def test_retrieve_returns_chunks(mock_retrieve: MagicMock) -> None:
    response = client.post(
        "/retrieve",
        json={
            "query": "What are the main risk factors?",
            "ticker": "AAPL",
            "top_k": 3,
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["query"] == "What are the main risk factors?"
    assert len(body["chunks"]) == 1

    chunk = body["chunks"][0]
    assert chunk["chunk_id"] == SAMPLE_CHUNK.chunk_id
    assert chunk["ticker"] == "AAPL"
    assert chunk["section"] == "Item 1A"
    assert "Risk factors" in chunk["excerpt"]
    assert chunk["score"] == pytest.approx(0.85)

    mock_retrieve.assert_called_once_with(
        "What are the main risk factors?",
        ticker="AAPL",
        top_k=3,
    )


def test_retrieve_defaults_top_k(mock_retrieve: MagicMock) -> None:
    response = client.post(
        "/retrieve",
        json={"query": "revenue growth"},
    )
    assert response.status_code == 200
    mock_retrieve.assert_called_once_with(
        "revenue growth",
        ticker=None,
        top_k=5,
    )


def test_retrieve_rejects_invalid_top_k() -> None:
    response = client.post(
        "/retrieve",
        json={"query": "test", "top_k": 0},
    )
    assert response.status_code == 422

    response = client.post(
        "/retrieve",
        json={"query": "test", "top_k": 21},
    )
    assert response.status_code == 422


def test_retrieve_empty_chunks(mock_retrieve: MagicMock) -> None:
    mock_retrieve.return_value = []
    response = client.post(
        "/retrieve",
        json={"query": "nonexistent topic xyz", "ticker": "AAPL"},
    )
    assert response.status_code == 200
    assert response.json()["chunks"] == []
```
