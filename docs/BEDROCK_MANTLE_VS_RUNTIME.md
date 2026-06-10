# Bedrock Mantle vs Classic Runtime（Playground 红条但 Mantle 能用）

个人笔记：2026-06 实测现象 + 对 capstone **7 天冲刺** 的路径选择。

---

## 你观察到的现象

| 入口 | 结果 |
|------|------|
| **Test → Playground → Chat**（经典 Background） | 红条 ValidationException / Run 不可用 → **像整线路都不能用** |
| **Overview → Try Bedrock Mantle Console → Evaluate** | **MiniMax M2.5、Qwen3 Coder Next** ✅ 有回复 |
| Mantle 里 **Claude Opus 4.7** | ❌ 403 `permission_error` — 该模型对此账号不可用 |

**结论：不是「AWS 上所有 AI 都挂了」，而是两条不同的 Bedrock 推理线路，开关和模型池不一样。**

---

## 两条线路对比

官方：[Endpoints supported by Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/endpoints.html)

```
你的 AWS 账号
│
├── bedrock-runtime（经典）
│   ├── Console: Playground / Chat
│   ├── API: InvokeModel, Converse
│   ├── 模型: Nova, Titan, Claude（经典 catalog）
│   └── 你的状态: ❌ 账号级仍 blocked（Support 在跟）
│
└── bedrock-mantle（Mantle）
    ├── Console: Try Bedrock Mantle
    ├── API: OpenAI Chat Completions / Anthropic Messages（兼容层）
    ├── 模型: 很多开放权重 — Qwen, MiniMax, Kimi 等
    └── 你的状态: ✅ 部分模型已可用；Claude Opus 仍要单独权限
```

| | **Path A — Classic Runtime** | **Path B — Mantle（临时）** |
|---|------------------------------|------------------------------|
| **Endpoint** | `bedrock-runtime.{region}.amazonaws.com` | `bedrock-mantle.{region}.api.aws` |
| **SDK** | `boto3` `bedrock-runtime` `converse()` | OpenAI Python SDK（改 `base_url` + API key） |
| **和本项目 README 原计划** | ✅ 一致 | ⚠️ 生成层不同，需抽象 |
| **你现在的可用性** | ❌ 等 Support | ✅ Qwen / MiniMax |
| **Embedding（Titan）** | 经典 runtime | Mantle **不负责** embed → 仍要本地/pgvector 或 classic 开通后 |

---

## Path B 效果会不会差？

**对「学习 + 7 天 demo」：够用，不必等 classic 才开工。**

| 维度 | Mantle（Qwen3 等） | Classic（Claude / Nova） |
|------|-------------------|---------------------------|
| **带 citation 的 RAG 问答** | 证据给全时 **可以**；遵守 prompt 即可 | 通常 **略稳**，长文/金融表述更好 |
| **SEC filing 复杂推理** | 中等；demo 级 OK | 更强 |
| **面试叙事** | 「Mantle 过渡 + provider 抽象，classic 开通后切换」 | 「标准 Bedrock Converse」 |
| **Jefferies infra 味** | 仍可做 Phase 1 本地 + 部分 AWS | S3/OpenSearch/ECS 与用哪条 LLM 线 **无关** |

**建议模型（Mantle 临时）：** `qwen3-coder-*` 或文档里 Evaluate 能跑通的那个 ID — 偏指令跟随，适合「只根据 evidence 回答」。

**不要指望 Mantle 临时路径在 7 天内 beat Claude**；要的是 **agent loop + RAG + 可切换架构**。

---

## 改用 Mantle 后，难不难改回 Path A？

**不难 — 前提是 Phase 2 就加一层 thin abstraction，不要把 OpenAI SDK 写满 `api.py`。**

### 推荐结构（Phase 2 第一天就做）

```
app/llm.py          # 唯一对外: chat(system, user, ...) -> str
app/llm_mantle.py   # Mantle / OpenAI-compatible
app/llm_bedrock.py  # classic Converse（Support 通过后实现）
app/llm_ollama.py   # 可选本地 fallback
```

`.env`:

```bash
LLM_PROVIDER=mantle    # mantle | bedrock | ollama
MANTLE_BASE_URL=...
MANTLE_API_KEY=...     # Bedrock API keys（Mantle console）
MANTLE_MODEL_ID=qwen3-coder-...
# Support 通过后:
# LLM_PROVIDER=bedrock
# BEDROCK_CHAT_MODEL_ID=anthropic.claude-3-5-haiku-...
```

**改回 Path A 时通常只动：**

1. 实现/启用 `llm_bedrock.py`（boto3 `converse`）
2. `.env` 改 `LLM_PROVIDER=bedrock`
3. **不动** `orchestrator`、tools、schemas、API 路由

| 若这样做 | 迁移成本 |
|----------|----------|
| ✅ 所有生成走 `app/llm.py` | **几小时** |
| ❌ Mantle SDK 散落在 agents 里 | **重写多处** — 避免 |

RAG **检索 / chunk / citation** 与 LLM 后端 **无关**；Phase 1 照常做。

---

## 7 天入职前 — 推荐优先级

假设 **classic Bedrock 仍未开通**：

| 天 | 重点 | LLM |
|----|------|-----|
| 1–2 | **Phase 1** ingest + pgvector + `retrieve` | 不需要 |
| 3–4 | **Phase 2/3 精简**：`llm.py` + Mantle **或** Ollama + 简单 agent loop + citation | Mantle **或** Ollama |
| 5–6 | README demo + eval 3 条 golden query | 同上 |
| 7 | Support follow-up；若 classic 通了 → 切 `LLM_PROVIDER=bedrock` 写进 Done notes | 可选切换 |

**可以放弃或缩水的（7 天内）：** OpenSearch、ECS/CDK 全量 — 写在 README「Future work」，面试诚实说 timeline。

**不要做的：** 为 Mantle 重写整套架构；在 Mantle 里死磕 Claude Opus（你已 403）。

---

## 常见问题（入职前 7 天）

下面三个问题是 path 选择时的核心决策；和上文各节对应，方便快速扫一眼。

### Q1：临时用 Path B（Mantle），和直接用 Classic Bedrock 区别大吗？

**API 层有差别，业务层可以不大。**

| 层 | Classic（Path A） | Mantle（Path B） |
|----|-------------------|------------------|
| 调用方式 | `boto3` → `bedrock-runtime` → `converse()` | OpenAI SDK + `bedrock-mantle` endpoint |
| 模型 | Nova / Titan / Claude | Qwen、MiniMax 等（你已能用） |
| RAG / agent / citation | 同一套 | **同一套**（检索、schemas、orchestrator 不变） |

差别主要在 **「谁生成最后一句话」**，不在整个项目架构。  
Embedding 仍建议 Phase 1 用 **本地 / pgvector**（Mantle 不负责 Titan embed）。

---

### Q2：先用 Mantle，效果会不会不好？

**对 7 天 demo + 学习：够用，不必等 classic 才开工。**

- RAG 质量更多取决于 **检索 + citation prompt**，不是只有 Claude 才行。
- **Qwen3** 在「只根据 evidence 回答」这类任务上可以；复杂金融表述可能略逊于 Claude，但 **portfolio 级 OK**。
- Mantle 里的 **Claude Opus 你已 403** — 临时别押 Opus，用 **Qwen / MiniMax** 即可。
- **不要指望** Mantle 在 7 天内 beat Claude；目标是 **agent loop + RAG + 可切换架构**。

---

### Q3：之后改回 Path A（Classic）难吗？代码会不会很难改？

**不难 — 前提是 Phase 2 就做 `app/llm.py` 抽象，不要把 Mantle SDK 写满各个 agent。**

业务代码只调：

```python
from app.llm import chat

answer = chat(system=..., user=..., evidence=...)
```

Support 通过后：

```bash
LLM_PROVIDER=bedrock   # 原来是 mantle
```

通常 = **实现 `llm_bedrock.py` + 改一行 `.env`**，**不用重写** orchestrator / tools / schemas。

| 做法 | 改回 Path A 的成本 |
|------|-------------------|
| ✅ 所有生成走 `app/llm.py` | **几小时** |
| ❌ Mantle SDK 散落在 agents 里 | **重写多处** — 避免 |

---

### 7 天怎么排（摘要）

| 优先级 | 做什么 | LLM |
|--------|--------|-----|
| **必做** | Phase 1：EDGAR + retrieve + citation 格式 | 不需要 Bedrock |
| **必做** | Phase 2/3 **精简版**：`llm.py` + agent loop | **Mantle（Qwen）或 Ollama** |
| **可选** | Support 批了 → `LLM_PROVIDER=bedrock` | Classic |
| **可砍** | OpenSearch、ECS/CDK 全量 | 写进 Future work |

**不要** 等 classic 才开工；**不要** 7 天内为 Mantle 重写架构。

**一句话：** 临时 Mantle 可以，效果对 demo 够用；用 `app/llm.py` 包一层，改回 classic 是 **换 backend**，不是重写项目。

---

## Support case 可补充一句

```
Classic bedrock-runtime Playground still blocked (ValidationException).
However bedrock-mantle works for open-weight models (Qwen, MiniMax).
Please enable bedrock-runtime / standard Bedrock Playground for account 
449873021145 for Converse API and Titan embeddings.
```

---

## 相关文档

- [AWS_ACCOUNT_NOTES.md](./AWS_ACCOUNT_NOTES.md) — Root/IAM、Support
- [AWS_SETUP.md](./AWS_SETUP.md) — 开通 checklist
- [ARCHITECTURE.md](./ARCHITECTURE.md) — agent 目标架构
