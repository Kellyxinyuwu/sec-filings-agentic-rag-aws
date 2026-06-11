# Phase 2 — Bedrock Mantle 生成 + grounded citations

> **状态：** ✅ 已完成（2026-06-11）  
> **LLM：** Phase 2 用 **AWS Bedrock Mantle**（Qwen / MiniMax）根据 Phase 1 的 `EvidenceChunk` 写真 `answer`；**embedding 仍本地 MiniLM**（Mantle 不做 embed）。  
> **路径选择：** Path A = Mantle（本 Phase 默认）；classic `bedrock-runtime` 等 Support 通过后再加 `llm_bedrock.py`。

### 怎么用这个文档（和 Chat 分工）

| 在哪 | 内容 |
|------|------|
| **Chat（Cursor）** | 每一步的 **完整代码** + 行内讲解 → 你复制粘贴到文件 |
| **本文 PHASE_2.md** | 前言 Q&A + 每一步 **做什么、为什么、验证什么**（**不放代码**）+ 做完后的 **实现笔记** |
| **README.md** | 仅 **整 Phase 完成** 时更新状态（不在 README 里记逐步笔记） |

流程：读本文 §0 前言 + 对应 Step → Chat 拿代码 → 粘贴 → 验证 → 在本文该 Step 下写 **实现笔记**、更新 §11 步骤总览表 → 下一步 Chat。

---

## 目录

0. [前言 — Phase 2 开工前的两个问答](#0-前言--phase-2-开工前的两个问答)
1. [Phase 1 回顾 vs Phase 2 目标](#1-phase-1-回顾-vs-phase-2-目标)
2. [Phase 2 一句话](#2-phase-2-一句话)
3. [要做什么 / 不做什么](#3-要做什么--不做什么)
4. [任务清单（checkbox）](#4-任务清单checkbox)
5. [会新增/修改哪些文件](#5-会新增修改哪些文件)
6. [模型栈：谁负责 embed、谁负责 LLM](#6-模型栈谁负责-embed谁负责-llm)
7. [步骤顺序（建议按天）](#7-步骤顺序建议按天)
8. [验收标准](#8-验收标准)
9. [和 Phase 3（Agent）的衔接](#9-和-phase-3agent-的衔接)
10. [相关文档](#10-相关文档)
11. [分步讲解（无代码）](#11-分步讲解无代码)

---

## 0. 前言 — Phase 2 开工前的两个问答

开工 Phase 2 前在 Chat 里确认过的两个问题与回答（原文收录，便于以后复习）。

---

### 问答 1

**问（你）：**

> 对，我想尽可能可以用 aws 就用 aws 的 model，那你选 a 吧，是不是 phase2 这个是用 aws 的 model 根据 retrive 到的 evidence trunk，去写真 answer？phase2 有用到 llm，phase1 没有？

**答：**

你的理解基本对，我帮你把边界说清楚：

---

#### Phase 1 vs Phase 2：有没有 LLM？

| | Phase 1 | Phase 2 |
|--|---------|---------|
| **生成答案的 LLM** | ❌ 没有 | ✅ 有 — **AWS Bedrock Mantle**（Qwen / MiniMax） |
| **`/chat` 的 `answer`** | mock 字符串 | 根据 evidence **真生成** |
| **`/retrieve`** | 真 chunk | 不变，还是 Phase 1 那套 |
| **用的「模型」** | 只有 **embedding 模型**（本地 MiniLM） | embedding 仍本地 + **云端 LLM 写答案** |

所以：

- **Phase 1**：有模型，但是 **embedding 模型**（把文字变成向量去搜），**不**负责写人话答案。
- **Phase 2**：加上 **LLM**（AWS Mantle），读 retrieve 到的 `EvidenceChunk`，写出 grounded 的 `answer`，并带上 citation。

---

#### Phase 2 数据流（Path A = Mantle）

```
用户问题
    ↓
retrieve()  →  top-k EvidenceChunk（Phase 1，本地 pgvector + MiniLM）
    ↓
拼进 prompt（「只根据下面 evidence 回答，要引用 chunk_id」）
    ↓
AWS Bedrock Mantle（Qwen3 等）→ 真 answer
    ↓
POST /chat 返回 answer + citations + evidence
```

**Phase 2 只换「谁写 answer」**；检索、`schemas`、`tools.retrieve()` 都不推倒重来。

---

#### 「尽可能用 AWS」在 Phase 2 里指什么？

| 层 | Phase 2 计划 | 是否 AWS |
|----|--------------|----------|
| **答案生成（LLM）** | Bedrock **Mantle** | ✅ AWS |
| **向量检索（embed + index）** | 仍本地 MiniLM + pgvector | ❌ 本机（Titan embed 在 classic runtime，你账号还没开） |

这是文档里定的 **hybrid**：Phase 2 先把 **云 LLM** 接上；embed / 向量库迁到 AWS 是 **Phase 4**（OpenSearch + 可选 Titan embed）。

Classic Playground（Claude / Nova）仍 blocked 也没关系 — **Mantle 是另一条 AWS 线路**，你 Evaluate 里能用的 Qwen / MiniMax 就够 Phase 2。

---

#### 一句话

> **Phase 2 = 用 AWS Mantle LLM，根据 retrieve 到的 evidence chunk 写真 answer；Phase 1 只有检索，没有生成式 LLM。**

---

### 问答 2

**问（你）：**

> 是不是 embedding 无法用 mantle 啊所以我们本地用的是 ollama 还是？

**答：**

**对，Mantle 做不了 embedding。** 它只管 **聊天 / 生成文字**，不负责把句子变成检索用的向量。

---

#### 本项目现在用的是什么？（不是 Ollama）

| 用途 | 用什么 | 在哪 |
|------|--------|------|
| **Embedding（向量化）** | **`sentence-transformers`** → `all-MiniLM-L6-v2` | 本地 Python 库，跑在笔记本上 |
| **向量库** | **pgvector**（Docker Postgres） | 本地 `:5433` |
| **写答案的 LLM** | Phase 1：**没有**；Phase 2：**AWS Mantle** | 云端 |

**Embedding 既不是 Mantle，也不是 Ollama。**

`store.py` 里用的是：

```python
SentenceTransformer(settings.embedding_model)  # all-MiniLM-L6-v2 → 384 维向量
```

ingest 和 retrieve 都用同一套 MiniLM，所以能搜到 chunk。

---

#### Ollama 在哪？

**只在旧项目 `SEC-10-K-RAG` 里**，用来 **生成答案**（例如 `llama3.2`），**不是**用来做 embedding。

旧项目典型分工：

```
MiniLM（sentence-transformers）→ embedding + pgvector 检索
Ollama（llama3.2）              → 根据 chunk 写答案
```

**新项目 Phase 1** 只做了左边（MiniLM + pgvector），右边还没接 LLM。  
**Phase 2** 会用 **AWS Mantle** 替代旧项目的 Ollama 来写答案。

---

#### 为什么 embedding 不用 AWS？

| 选项 | 现状 |
|------|------|
| **Bedrock Titan Embed** | 在 **classic `bedrock-runtime`** 上；你账号 Playground 还被 block |
| **Mantle** | 没有 embedding API，不能当向量模型用 |
| **本地 MiniLM** | ✅ Phase 1 已用；免费、快、够 demo |

所以是 **hybrid**：

```
Phase 1–2：本地 MiniLM embed + 本地 pgvector 检索
Phase 2：  AWS Mantle 写 answer
Phase 4：  再考虑 Titan embed + OpenSearch（上 AWS）
```

用 chat 模型硬当 embedding 会又慢又贵，检索质量也差，所以不这么做。

---

#### 一张表总结

| 层 | 旧项目 | 新项目 Phase 1 | 新项目 Phase 2 |
|----|--------|----------------|----------------|
| Embed | 本地 MiniLM | 本地 MiniLM | 仍本地 MiniLM |
| 检索 | pgvector | pgvector | 不变 |
| 写答案 | **Ollama** | mock | **AWS Mantle** |

---

#### 一句话

> Mantle 只负责 Phase 2 的 **LLM 答案**；embedding 一直是本地 **MiniLM**（`sentence-transformers`），不是 Ollama。Ollama 是旧项目写答案用的，新项目用 Mantle 替代它。

---

## 1. Phase 1 回顾 vs Phase 2 目标

### Phase 1 你已经有什么？

| 类别 | 已完成 |
|------|--------|
| **数据** | AAPL 10-K ingested，~10k chunks in pgvector |
| **检索** | `app/store.py`、`app/tools.retrieve()`、`POST /retrieve` |
| **API** | `/health` phase `"1"`；`/chat` 真 `evidence`，**mock `answer`** |
| **测试** | `tests/test_retrieve.py`（mock `app.api.retrieve`） |
| **Embed** | 本地 `all-MiniLM-L6-v2`，384 维 |

### Phase 1 还没有什么？

- 生成式 LLM 答案
- `app/llm.py` provider 抽象
- Grounded prompt + citation 校验
- AWS API 调用（除账号准备笔记外）

### Phase 2 要补上什么？

**第一次 `/chat` 返回由 AWS Mantle 写的、基于 evidence 的真答案。**

---

## 2. Phase 2 一句话

Phase 1 的 **`retrieve()` 不变** → 把 top-k `EvidenceChunk` 塞进 prompt → **Bedrock Mantle** 生成 `answer` → `/chat` 返回 grounded 回答 + citations。

---

## 3. 要做什么 / 不做什么

### ✅ Phase 2 要做

| # | 事项 |
|---|------|
| 1 | `.env` + `config.py` — `LLM_PROVIDER=mantle`，`MANTLE_*` |
| 2 | `pyproject.toml` — `openai` SDK（Mantle OpenAI-compatible API） |
| 3 | `app/llm_mantle.py` — 调 Mantle chat completions |
| 4 | `app/llm.py` — 统一 `chat(system, user) -> str`，按 provider 分发 |
| 5 | `app/prompts.py` — RAG system prompt：只根据 evidence 答、引用 `chunk_id` |
| 6 | `app/api.py` — `/chat`：`retrieve` → LLM → 真 `answer`；`/health` phase `"2"` |
| 7 | `tests/test_chat_rag.py` — mock LLM，CI 不花钱、不联网 |
| 8 | （可选）`scripts/test_mantle.py` — 一条命令测 Mantle 连通 |
| 9 | 手动 curl — 3 条 golden query 验收 |

### ❌ Phase 2 不做

| 事项 | 放到哪 |
|------|--------|
| 换 embedding 到 Titan | Phase 4 |
| OpenSearch / S3 | Phase 4 |
| Planner / Researcher / Writer / Verifier 多 agent 循环 | Phase 3 |
| `orchestrator.py` | Phase 3 |
| Classic `bedrock-runtime` Converse（Claude） | Support 通过后加 `llm_bedrock.py` |
| Ollama fallback | 可选 stretch；架构预留 `LLM_PROVIDER=ollama` |

**LLM 模型：** 用你在 Mantle Console **Evaluate 能跑通**的 ID（如 Qwen3 Coder Next）；不要用已 403 的 Claude Opus。

---

## 4. 任务清单（checkbox）

完成一项勾一项；逐步 **实现笔记** 写在本文 §11 各 Step 下（整 Phase 验收通过后再填 `README.md` Phase 2 的 Done notes）。

### A. 环境与配置

- [x] Mantle Console 生成 **API key**（Bedrock API keys）
- [x] `.env` 填写 `LLM_PROVIDER=mantle`、`MANTLE_BASE_URL`、`MANTLE_API_KEY`、`MANTLE_MODEL_ID`
- [x] `pyproject.toml` 增加 `openai`（Mantle 兼容层）
- [x] `app/config.py` 增加 LLM 相关 settings

### B. LLM 层

- [x] `app/llm_mantle.py`
- [x] `app/llm.py` — provider 工厂 / 统一入口
- [x] `app/prompts.py` — grounded RAG prompt

### C. API

- [x] `app/api.py` — `/chat` 调 LLM，去掉 mock answer 前缀
- [x] `/health` → `phase: "2"`

### D. 测试与验收

- [x] `tests/test_chat_rag.py` — mock `app.api.retrieve` + `app.api.llm_chat`
- [x] `tests/test_health.py` — `test_chat_mock` 同样 mock
- [x] `scripts/test_mantle.py`（可选）— 本地一条 ping Mantle
- [x] `pytest -q` 全绿（11 passed）
- [x] curl 3 条 golden query — risk / revenue / business overview ✅

---

## 5. 会新增/修改哪些文件

```
sec-filings-agentic-rag-aws/
├── app/
│   ├── llm.py              # 新建 — 唯一对外 chat 入口
│   ├── llm_mantle.py       # 新建 — Mantle / OpenAI-compatible
│   ├── prompts.py          # 新建 — RAG + citation 模板
│   ├── config.py           # 修改 — LLM_PROVIDER, MANTLE_*
│   └── api.py              # 修改 — /chat 真答案, /health phase 2
├── scripts/
│   └── test_mantle.py      # 新建（可选）— 连通性
├── tests/
│   └── test_chat_rag.py    # 新建
├── pyproject.toml          # 修改 — openai
├── .env.example            # 修改 — MANTLE_* 示例
└── docs/PHASE_2.md         # 本文
```

**Phase 2 不建：** `orchestrator.py`、`agents/`、`app/aws.py`（可 Phase 2 末或 Phase 4 再 Consolidate；Mantle 走 `llm_mantle.py` + OpenAI SDK 即可）。

**Phase 2 不改：** `store.py` ingest/retrieve 逻辑、`tools.retrieve()` 签名、Phase 1 的 `documents` 表结构。

---

## 6. 模型栈：谁负责 embed、谁负责 LLM

```
┌─────────────────────────────────────────────────────────┐
│  Phase 2 运行时                                          │
├─────────────────────────────────────────────────────────┤
│  检索路径（Phase 1，不变）                                │
│    query → MiniLM embed → pgvector → EvidenceChunk[]     │
├─────────────────────────────────────────────────────────┤
│  生成路径（Phase 2，新增）                                │
│    EvidenceChunk[] + user query → prompt → Mantle → answer │
└─────────────────────────────────────────────────────────┘
```

| 组件 | 技术 | 位置 |
|------|------|------|
| Embedding | `sentence-transformers` / `all-MiniLM-L6-v2` | 本地 |
| Vector DB | pgvector | Docker `:5433` |
| LLM（答案） | Bedrock Mantle（Qwen / MiniMax） | AWS `us-east-1` |

详见 [MODEL_AND_PRODUCTION_DECISIONS.md](./MODEL_AND_PRODUCTION_DECISIONS.md)、[BEDROCK_MANTLE_VS_RUNTIME.md](./BEDROCK_MANTLE_VS_RUNTIME.md)。

---

## 7. 步骤顺序（建议按天）

| 顺序 | 做什么 | 预计 |
|------|--------|------|
| 1 | `.env` + `config.py` + `openai` 依赖 | 0.5 天 |
| 2 | `llm_mantle.py` + `scripts/test_mantle.py` 连通 | 0.5 天 |
| 3 | `llm.py` + `prompts.py` | 0.5 天 |
| 4 | `api.py` 接 `/chat` | 0.5 天 |
| 5 | `test_chat_rag.py` + E2E curl | 0.5 天 |

合计约 **2–3 天**（含 Mantle key、prompt 调试）。

---

## 8. 验收标准

### 自动测试

```bash
pytest -q
```

须包含 Phase 0/1 测试 + `tests/test_chat_rag.py`（mock LLM，不调用 AWS）。

### 手动流程

```bash
# 1. DB + ingest 仍可用（Phase 1）
docker compose up -d db

# 2. .env 已配 MANTLE_*
source .venv/bin/activate
pip install -e ".[dev]"

# 3. （可选）测 Mantle
python scripts/test_mantle.py

# 4. 起 API
uvicorn app.main:app --reload --port 8001

# 5. /chat 真答案
curl -X POST http://127.0.0.1:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the main risk factors?", "ticker": "AAPL"}'
```

### 通过条件

- [x] `answer` **不是** `[Mock response] Phase 2 will...` 前缀
- [x] `citations` / `evidence` 含真 `chunk_id`（如 `AAPL-0000320193-25-000079-...`）
- [x] 答案内容与 risk / SEC filing 相关，且明显来自 retrieval（非胡编）
- [x] `GET /health` → `"phase": "2"`
- [x] `pytest -q` 全绿（11 passed）

### Golden queries（建议 3 条）

1. What are the main risk factors?（AAPL）
2. What was total net sales / revenue discussion?（AAPL）
3. Who is the company / business overview?（AAPL）

---

## 9. 和 Phase 3（Agent）的衔接

```
Phase 2（本阶段）              Phase 3（下一步）
─────────────────              ─────────────────
api.py 里：retrieve → LLM    orchestrator.py：
单段 RAG prompt              Planner → Researcher → Writer → Verifier
                             Researcher 仍调 tools.retrieve()
                             Writer 仍调 app/llm.chat()
```

Phase 2 把 **LLM + grounded prompt** 做扎实；Phase 3 把 `/chat` 里的线性流程拆成 agent，**不改** `llm.py` / `tools.py` 对外接口。

---

## 10. 相关文档

- [PHASE_1.md](./PHASE_1.md) — 已完成检索链路
- [BEDROCK_MANTLE_VS_RUNTIME.md](./BEDROCK_MANTLE_VS_RUNTIME.md) — Mantle vs classic、`.env` 示例、`llm.py` 结构
- [MODEL_AND_PRODUCTION_DECISIONS.md](./MODEL_AND_PRODUCTION_DECISIONS.md) — hybrid 栈、面试话术
- [AWS_SETUP.md](./AWS_SETUP.md) — 账号、region、budget
- [OLD_VS_NEW_PROJECT.md](./OLD_VS_NEW_PROJECT.md) — Ollama vs Mantle 对比
- [TOKEN_AND_COST_CONTROL.md](./TOKEN_AND_COST_CONTROL.md) — `max_tokens`、降本提效、面试话术

---

## 11. 分步讲解（无代码）

### 步骤总览

| Step | 主题 | 主要文件 | 状态 |
|------|------|----------|------|
| 1 | 依赖 + LLM 环境变量 | `pyproject.toml`, `.env.example`, `.env`, `config.py` | ✅ 2026-06-11 |
| 2 | Mantle 客户端 | `app/llm_mantle.py`, `scripts/test_mantle.py` | ✅ 2026-06-11 |
| 3 | LLM 抽象层 | `app/llm.py` | ✅ 2026-06-11 |
| 4 | RAG Prompt | `app/prompts.py` | ✅ 2026-06-11 |
| 5 | 接 `/chat` | `app/api.py` | ✅ 2026-06-11 |
| 6 | 测试 | `tests/test_chat_rag.py` | ✅ 2026-06-11 |
| 7 | 端到端验收 | curl + pytest | ✅ 2026-06-11 |

---

### Step 1 — 依赖与 LLM 环境变量

**目标：** 装上 OpenAI SDK（调 Mantle 兼容 API），并在 `settings` 里读 `LLM_PROVIDER`、`MANTLE_*`。

**为什么要做：** Phase 1 的 `config.py` 只有 DB/embed；Phase 2 生成答案需要云端凭证与模型 ID。

**要改什么：**

- `pyproject.toml`：增加 `openai>=1.0.0`
- `.env.example`：`LLM_PROVIDER`、`MANTLE_BASE_URL`、`MANTLE_API_KEY`、`MANTLE_MODEL_ID`
- `.env`：从 Mantle Console 复制真实 key 与你在 Evaluate 里能用的 model id
- `app/config.py`：对应字段；`extra="ignore"` 保持即可

**验证：** `pip install -e ".[dev]"`；`python -c "from app.config import settings; print(settings.llm_provider)"` 打印 `mantle`。

**本步不做：** 调 API、改 `/chat`。

**实现笔记（2026-06-11）：**

| 子步骤 | 做了什么 | 目的 |
|--------|----------|------|
| `openai` 依赖 | `pyproject.toml` | Mantle OpenAI-compatible API |
| `config.py` | `llm_provider`, `mantle_*` 字段 | 全项目从 `settings` 读 LLM 配置 |
| `.env` | 真实 key + `MANTLE_MODEL_ID=qwen.qwen3-coder-next` | **读 `.env` 不是 `.env.example`** |
| 验证 | OpenAI SDK one-liner → 输出 `Hello` | Mantle 连通 OK |
| 注意 | Live API docs 的 model 不跟 Evaluate 同步 | 以 AWS model card ID 为准 |
| 注意 | API key 只放 `.env`，`.env.example` 用占位符 | 避免 commit 泄露 |

---

### Step 2 — Mantle 客户端 `app/llm_mantle.py`

**目标：** 用 OpenAI Python SDK，`base_url` 指向 Mantle endpoint，`api_key` 用 Bedrock API key，实现一次 `chat.completions.create`。

**为什么要做：** 先 isolated 测通 Mantle，再接到 `/chat`；失败时容易区分是 key/模型还是 RAG prompt 问题。

**要新建：**

- `app/llm_mantle.py` — 例如 `mantle_chat(system: str, user: str) -> str`
- `scripts/test_mantle.py`（可选）— `python scripts/test_mantle.py` 打印一句回复

**验证：** 脚本或 `python -c` 能收到 Mantle 非空回复；无 401/403。

**本步不做：** retrieve、FastAPI 路由。

**实现笔记（2026-06-11）：**

| 子步骤 | 做了什么 | 目的 |
|--------|----------|------|
| `llm_mantle.py` | OpenAI SDK + `settings.mantle_*` → `mantle_chat()` | 专门和 AWS Mantle 说话 |
| `test_mantle.py` | 一行脚本测连通 | 改 key/model 时快速验证 |
| `max_tokens` | 默认 1024，测试用 16 | 控制输出长度与成本（见 [TOKEN_AND_COST_CONTROL.md](./TOKEN_AND_COST_CONTROL.md)） |

---

### Step 3 — LLM 抽象 `app/llm.py`

**目标：** 全项目 **唯一** 对外：`chat(system_prompt, user_message) -> str`；内部按 `settings.llm_provider` 调 `llm_mantle`（日后加 `llm_bedrock`、`llm_ollama`）。

**为什么要做：** [BEDROCK_MANTLE_VS_RUNTIME.md](./BEDROCK_MANTLE_VS_RUNTIME.md) — Support 通过后只改 provider，不动 orchestrator / api 主流程。

**验证：** `LLM_PROVIDER=mantle` 时 `from app.llm import chat` 能返回字符串（可薄包装 Step 2）。

**本步不做：** evidence 格式化（Step 4）。

#### Step 3 在干什么？（通俗版）

可以把它想成 **「总机 / 前台」**：

- **Step 2**（`llm_mantle.py`）= 只会打 **Mantle 这一条线** 的分机，懂 AWS endpoint、API key、OpenAI SDK。
- **Step 3**（`llm.py`）= **总机**：业务代码（以后的 `api.py`、Phase 3 的 Writer agent）**只拨总机号码** `chat()`，总机看 `.env` 里 `LLM_PROVIDER` 决定转接到哪条分机。

```
没有 Step 3 时（不好）：
  api.py ──直接──► OpenAI SDK / mantle_chat
  orchestrator ──又写一遍──► 另一套调用
  → 换 Bedrock classic 要改很多文件

有 Step 3 时（我们要的）：
  api.py ──┐
  Writer ──┼──► app.llm.chat()  ◄── 只认这一个入口
  Verifier ─┘         │
                      ├─ mantle  → llm_mantle.mantle_chat()   ✅ 现在
                      ├─ bedrock → llm_bedrock（以后）
                      └─ ollama  → llm_ollama（可选）
```

**类比投行/公司：** 业务组不直接打供应商电话，走 **采购/平台统一接口** — 换模型供应商时，改配置和适配层，业务流程（RAG、agent、citation）不用重写。这就是 backend 里常说的 **provider abstraction / 适配器模式**。

#### `chat()` 的两个参数先记什么？

| 参数 | 装什么（Step 4 会具体写） | 比喻 |
|------|---------------------------|------|
| `system` | 规则：「只根据 evidence 答」「要引 chunk_id」「不要投资建议」 | 员工手册 / 合规须知 |
| `user` | 用户问题 + 检索到的 SEC 原文片段 | 分析师递过来的材料和问题 |

Step 3 **只负责把这两段文字送给模型并拿回答案**；**怎么拼**这两段文字是 Step 4 `prompts.py` 的事。

#### 代码里几个细节

| 细节 | 含义 |
|------|------|
| `settings.llm_provider` | 读 `.env` 的 `LLM_PROVIDER=mantle`，决定走哪条分机 |
| `mantle` 用 **函数内 import** | 只有真正 `chat()` 时才加载 `llm_mantle`；单纯 `import app.llm` 不会立刻要求 Mantle key |
| `bedrock` / `ollama` 抛 `NotImplementedError` | 占位：以后加文件，**不改** `chat()` 的函数签名 |
| `max_tokens` 原样往下传 | 总机不重新定义规则，交给具体 provider（Mantle）执行 |

#### Step 2 vs Step 3 分工（一句话）

| 文件 | 职责 |
|------|------|
| `llm_mantle.py` | **怎么连 AWS Mantle**（技术细节） |
| `llm.py` | **业务该找谁要答案**（统一入口 + 换供应商） |

和 Phase 1 对照：`tools.retrieve()` 是检索的总机，`store.py` 是 pgvector 分机；`llm.chat()` 是生成的总机，`llm_mantle` 是 Mantle 分机。

**实现笔记（2026-06-11）：**

| 子步骤 | 做了什么 | 目的 |
|--------|----------|------|
| `app/llm.py` | `chat(system, user, max_tokens?)` | api / agent 唯一 LLM 入口 |
| provider 分支 | `mantle` → `mantle_chat`；其余 NotImplemented | 换 `.env` 即可切换后端（日后） |
| 验证 | `from app.llm import chat` → 输出 Hello | 总机转 Mantle 分机成功 |
| `pytest -q` | 仍 7 passed | 未动 `/chat`，Phase 1 无回归 |

---

### Step 4 — RAG Prompt `app/prompts.py`

**目标：** 把 `list[EvidenceChunk]` + 用户 `query` 格式化成 system/user 消息；规则：只根据 evidence 回答、不知道就说不知道、引用 `chunk_id`、不要投资建议。

**为什么要做：** Grounding 质量主要靠 prompt；Phase 3 Verifier 会在此基础上再加一层检查。

**验证：** 单元测试或 `python -c` 打印 prompt 字符串，含 chunk excerpt 与 id。

**本步不做：** HTTP。

#### Step 4 在干什么？（通俗版）

Step 3 的 `chat(system, user)` 需要两段文字；**Step 4 负责「怎么写这两段」**：

| 消息 | 内容 | 比喻 |
|------|------|------|
| `system` | 固定规则（`RAG_SYSTEM_PROMPT`） | 合规手册：只许根据 evidence、要引 chunk_id、不许投资建议 |
| `user` | 用户问题 + 每块 evidence 的 chunk_id / section / excerpt | 把分析师问题和 SEC 摘录装订成册递给模型 |

```
retrieve() → [EvidenceChunk, ...]
       ↓
build_rag_prompt(query, chunks) → (system, user)
       ↓
llm.chat(system, user)   ← Step 5 在 api.py 里接这一行
```

**和 Step 3 的分工：** Step 3 = **送信**；Step 4 = **写信**（信里写什么）。

#### 代码里几个细节

| 函数 / 常量 | 作用 |
|-------------|------|
| `RAG_SYSTEM_PROMPT` | 6 条 grounding 规则，所有 `/chat` 共用 |
| `format_evidence_block()` | 单块 chunk 格式：`[chunk_id: ...]` + ticker/section + excerpt |
| `_truncate()` + `DEFAULT_MAX_EXCERPT_CHARS=1000` | 每块 excerpt 最多约 1000 字符，**控制 input token / 成本**（见 [TOKEN_AND_COST_CONTROL.md](./TOKEN_AND_COST_CONTROL.md)） |
| `build_rag_prompt()` | 入口：空 chunks 时 user 里写明无 evidence，让模型拒答 |

#### 验证时注意

- 演示脚本 `print(system[:200], '...')` **故意只打前 200 字**，后面的 `...` 不是 prompt 缺内容。
- 可选 E2E：`retrieve` → `build_rag_prompt` → `chat`；若 `max_tokens=256` 过小，日志会出现 `finish_reason=length`，答案中途截断 — 用默认 1024 或更大即可。

**实现笔记（2026-06-11）：**

| 子步骤 | 做了什么 | 目的 |
|--------|----------|------|
| `app/prompts.py` | `build_rag_prompt`, `format_evidence_block`, `RAG_SYSTEM_PROMPT` | 统一 RAG 信笺格式 |
| excerpt 截断 | 每 chunk 默认 1000 字符 | 降 input token；SEC 原文/HTML 可能很长 |
| 假 chunk 验证 | `python -c` 打印 system/user | user 含 `chunk_id` 与 excerpt |
| E2E 预演 | AAPL risk factors + `top_k=3` + Mantle | 真 citation（如 `00217`）；`finish_reason=length` 时用更大 `max_tokens` |
| `pytest -q` | 仍 7 passed | 未改 `api.py` |

---

### Step 5 — 接 `/chat` `app/api.py`

**目标：** `retrieve()` → `build_rag_prompt()` → `llm.chat()` → 填 `ChatResponse.answer`；`/health` 的 `phase` 改为 `"2"`。

**可选：** DB 空时仍保留 Phase 1 的 mock evidence fallback，但 answer 也应说明无数据（或拒答）。

**验证：** curl `/chat` 返回非 mock 前缀的 answer；`evidence` 仍为真 chunk。

**本步不做：** pytest mock（Step 6）。

#### Step 5 在干什么？（通俗版）

把 Step 1–4 的零件在 **`POST /chat` 里串成一条流水线**：

```
用户 JSON → retrieve(5 chunks) → build_rag_prompt → llm_chat → ChatResponse
```

| 改动 | 说明 |
|------|------|
| `llm_chat` | `from app.llm import chat as llm_chat`，避免和路由函数同名 |
| 去掉 mock answer | `answer` 来自 Mantle |
| 去掉 mock evidence | DB 空则 `evidence=[]`，由 prompt 让模型拒答 |
| `writer_ms` / `researcher_ms` | `agent_steps` 里记录真实耗时（首次 retrieve 可能含加载 MiniLM） |
| `/health` `phase: "2"` | `test_retrieve.py` 里断言改为 `"2"` |

**实现笔记（2026-06-11）：**

| 子步骤 | 做了什么 | 结果 |
|--------|----------|------|
| `api.py` `/chat` | retrieve → prompt → `llm_chat` | 真 grounded 答案 |
| curl `/health` | | `{"status":"ok","phase":"2"}` |
| curl `/chat` AAPL risk | | 无 `[Mock response]`；answer 含真 chunk_id（00217 等）；writer `detail: mantle` |
| 耗时 | researcher ~9s（含首次 embed 加载），writer ~23s | 正常；第二次会快很多 |
| excerpt | citations 里仍有 HTML/`&#8217;` | Phase 1 原文如此；prompt 已提示忽略格式 |
| `pytest` | 须在 **项目目录** 跑：`cd sec-filings-agentic-rag-aws && pytest -q` | 在父目录 `AI learning` 会误收集 `SEC-10-K-RAG/tests` |
| `test_chat_mock` | Step 5 后 `/chat` 会真调 DB+Mantle | Step 6 用 mock 修 |

#### `/chat` 响应里的 `agent_steps` 和 `plan` 是啥？（Step 5 后）

Phase 0 就定了 **agent 形状的 JSON**；Phase 2 里**只有中间两步是真活**，两头是 Phase 3 占位：

| step | Phase 2 真/假 | 实际在干什么 |
|------|---------------|--------------|
| `planner` | 假（~1ms） | 固定返回 `plan`（intent=qa, ticker=AAPL） |
| `researcher` | **真** | `retrieve()` → `detail: "5 chunks"`，耗时含向量检索 |
| `writer` | **真** | `llm_chat()` → Mantle 写 `answer`，`detail: "mantle"` |
| `verifier` | 假（mock pass） | Phase 3 才验 citation |

`plan` = 将来 Planner 的输出；现在 `api.py` **写死**一份合理计划。用户主要看 **`answer` + `evidence`/`citations`**；`agent_steps` 是 demo / 可观测性 / Phase 3 接口预览。

---

### Step 6 — 测试 `tests/test_chat_rag.py`

**目标：** mock `retrieve` + `llm_chat`；断言 200、answer 结构、citations；**CI 不调用 Mantle / 不连 DB**。

**注意：** `api.py` 里是 `from app.llm import chat as llm_chat` → patch **`app.api.retrieve`** 和 **`app.api.llm_chat`**（不是 `app.tools.retrieve` / `app.llm.chat`）。

同时修 **`tests/test_health.py::test_chat_mock`**，用同样 mock，避免 pytest 触发真实 RAG。

**验证：** 在项目根 `pytest -q` 全绿（勿在父目录 `AI learning` 跑，会误收集旧项目 tests）。

**实现笔记（2026-06-11）：**

| 子步骤 | 做了什么 | 目的 |
|--------|----------|------|
| `test_chat_rag.py` | 4 个测试：answer、citations、agent_steps、plan | Phase 2 `/chat` 契约 |
| mock 位置 | `app.api.retrieve` + `app.api.llm_chat` | 与 Step 5 import 方式一致 |
| `test_health.py` | `test_chat_mock` 加同一套 mock | 避免 pytest 真调 DB+Mantle |
| 验证 | `pytest -q` → **11 passed** | 7 旧 + 4 新 |
| 注意 | 须在 `sec-filings-agentic-rag-aws/` 目录跑 pytest | 父目录会误收集 `SEC-10-K-RAG` |

---

### Step 7 — 端到端验收

见 [§8 验收标准](#8-验收标准)。通过 = Phase 2 完成 → 更新 `README.md`、`PHASES.md`、`OLD_VS_NEW_PROJECT.md` Changelog。

**实现笔记（2026-06-11）：**

| 子步骤 | 结果 |
|--------|------|
| `pytest -q` | **11 passed** |
| Golden #1 risk factors | 真 citation（00217 等），grounded 列表 |
| Golden #2 revenue | 诚实拒答式回答：excerpt 无总收入数字 →「do not state total directly」✅ grounding |
| Golden #3 business overview | 引用 `00198`：hardware / OS / software / services |
| 端口 | 8001 已占用时直接用现有 uvicorn 或 `kill $(lsof -t -i :8001)` |

**Phase 2 完成。** 下一步 Phase 3：真 orchestrator + verifier。

---

## Done notes（Phase 2 全部完成后填写）

- **日期：** 2026-06-11
- **Mantle model id：** `qwen.qwen3-coder-next`（us-east-1）
- **pytest / curl：** 11 passed；3 golden queries on `:8001`
- **学到的点：** hybrid 栈（本地 MiniLM + Mantle LLM）；`llm.py` provider 抽象；prompt grounding 会让模型在 evidence 不足时拒答；`max_tokens` / excerpt 截断控成本；`agent_steps` 中 researcher/writer 为真、planner/verifier 待 Phase 3
