# Token limits & LLM cost control

> **Living doc** — started 2026-06-11 during Phase 2 Step 2.  
> Captures Chat Q&A on `max_tokens`, how this repo applies limits, and **why banks / infra teams care** (降本提效).

**Related:** [PHASE_2.md](./PHASE_2.md) · [MODEL_AND_PRODUCTION_DECISIONS.md](./MODEL_AND_PRODUCTION_DECISIONS.md) · [AWS_SETUP.md](./AWS_SETUP.md) · `app/llm_mantle.py` · `app/config.py`

---

## Why this doc exists

Cloud LLM bills scale with **tokens** (input + output). In enterprise / banking contexts, platform teams are expected to:

- **Control spend** — budgets, caps, alarms, per-request limits  
- **Control latency** — shorter outputs = faster UX  
- **Control risk** — bounded responses, less rambling / hallucination surface  

Phase 2 wires **Bedrock Mantle** (metered). This doc records what we decided in build chat and how to talk about it in interviews.

---

## 前言 — Chat 问答（原文收录）

### 问答 1：`max_tokens = 16` 是什么意思？`mantle_chat` 里已经实现了吗？

**问（你）：**

> max_tokens = 16 是不是说我这个 request 最多可以用多少 token？然后 mantle_chat 里面已经 define 了这个限制 token 的功能？

**答：**

**`max_tokens` 限制的是模型「生成出来的回答」最多多长**（completion / output tokens），不是整条 request 的总 token，也不是你 system + user 输入能写多长。

#### `max_tokens=16` 是什么意思？

在 `test_mantle.py` 里：

```python
mantle_chat(
    system="...",
    user="Say hello in one word.",
    max_tokens=16,   # ← 回答最多约 16 个 token
)
```

意思是：**模型生成的回复**最多大约 16 个 token（一个词或很短一句，比如 `Hello`）。

- **输入**（system + user）可以更长，由模型的 **context window**（Qwen3 Coder Next 是 256K）决定  
- **输出**被 `max_tokens` 卡住，避免测试时刷很长一段

#### `mantle_chat` 里怎么实现的？

是的，**已经在 `mantle_chat` 里接好了**：

```python
limit = max_tokens if max_tokens is not None else settings.mantle_max_tokens  # 默认 1024

response = _client().chat.completions.create(
    model=model,
    messages=[...],
    max_tokens=limit,   # ← 传给 Mantle / OpenAI API
)
```

| 调用方式 | 实际用的上限 |
|----------|----------------|
| `mantle_chat(..., max_tokens=16)` | **16**（测试用） |
| `mantle_chat(...)` 不传 | **`settings.mantle_max_tokens`**（默认 1024，可在 `.env` 设 `MANTLE_MAX_TOKENS`） |

#### 和 Phase 2 RAG 的关系

以后 `/chat` 写 SEC 答案时，一般会：

- **不传** `max_tokens` → 用默认 **1024**，够写一段带引用的回答  
- 或按需要传更大/更小（仍只限 **输出**长度）

**输入**里塞多少 evidence chunk，是 prompt 长度问题，不是 `max_tokens` 管的；chunk 太多可能要先截断或减 `top_k`（Step 4 prompt 会处理）。

**一句话：** `max_tokens=16` =「回答最多约 16 个 token」；`mantle_chat` 已支持每次调用覆盖，不传则用 `.env` 里的默认 1024。

---

### 问答 2：限制 token 是不是怕输出太长烧钱？

**问（你）：**

> 所以限制 token 是不是怕如果输出太多 response 太长的话会烧钱？

**答：**

**对，这是主要原因之一**，但不只是为了省钱。

#### `max_tokens` 为什么要设上限？

| 原因 | 说明 |
|------|------|
| **成本** | Mantle 按 **输出 token** 计费（Qwen3 Coder Next 大约 $1.20 / 百万 output tokens）。`max_tokens` 越大，模型**最多**能写越长，**最坏情况**下账单越高 |
| **可控** | RAG 答案通常几百字就够；不设上限时模型可能啰嗦、重复 evidence，浪费 token |
| **延迟** | 生成越长越慢；demo / API 体验更差 |
| **格式** | Phase 2 要短答 + citation；限制输出有助于不跑题 |

测试里 `max_tokens=16` 更是为了：**只验证连通**，故意要最短回复。

#### 和「输入」的关系

- **输入**（system + 很多 evidence chunk）也花钱（input 单价，例如约 $0.5 / 百万 tokens）  
- **`max_tokens` 只卡输出**，不直接限制你塞多少 evidence  
- 所以 RAG 里还要控制 **`top_k`**、chunk 长度、prompt 裁剪（Step 4），否则 **输入**也会烧钱

#### 本项目里怎么设

| 场景 | 建议 |
|------|------|
| `test_mantle.py` | `max_tokens=16` — 连通测试，几乎不花钱 |
| 正式 `/chat` | 默认 `MANTLE_MAX_TOKENS=1024` — 够写一段 grounded 答案，又避免无限拉长 |
| 需要更长摘要 | 可调大，但要意识到 **output 成本线性涨** |

**一句话：** 限制 `max_tokens` 主要是 **控制输出长度 → 省钱、更快、答案更聚焦**；输入侧要靠少塞 chunk 来控制成本。个人账号有 $20 budget，设合理上限是好习惯。

---

## How tokens map to money (this project)

### Billing model (Bedrock Mantle — illustrative)

Prices change; check the model card in Console. Example for **Qwen3 Coder Next** in `us-east-1` (2026-06):

| Direction | Approx. price | What drives it |
|-----------|---------------|----------------|
| **Input** | ~$0.50 / 1M tokens | system prompt + user query + **all evidence excerpts** |
| **Output** | ~$1.20 / 1M tokens | model answer — capped by **`max_tokens`** |

**Rough intuition:** output is often **more expensive per token** than input; unbounded `max_tokens` is a **worst-case cost leak**.

### What `max_tokens` does *not* limit

| Not limited by `max_tokens` | What limits it instead |
|-----------------------------|-------------------------|
| Size of system + user **input** | Context window (256K for Qwen3 Coder Next); our **`top_k`** and prompt builder (Phase 2 Step 4) |
| Total AWS account spend | [AWS budget](../README.md) (`sec-rag-monthly $20`); future: per-env quotas, alarms |
| Embedding cost (Phase 1) | Local MiniLM — $0 inference; **your laptop CPU**, not Mantle |

---

## Where limits live in this repo

| Layer | Mechanism | File / config |
|-------|-----------|---------------|
| **Output cap (default)** | `MANTLE_MAX_TOKENS` → `settings.mantle_max_tokens` | `.env`, `app/config.py` |
| **Output cap (per call)** | `mantle_chat(..., max_tokens=N)` | `app/llm_mantle.py` |
| **Smoke test (minimal spend)** | `max_tokens=16` | `scripts/test_mantle.py` |
| **Request timeout** | `MANTLE_TIMEOUT_SECONDS` | `app/config.py` — avoids hung calls burning $ + time |
| **Retrieval breadth** | `top_k` on `/retrieve` / `/chat` | `app/tools.py`, `schemas.py` — fewer chunks = **less input** |
| **Embed (no cloud $)** | Local MiniLM | `app/store.py` — Phase 1 choice documented in [MODEL_AND_PRODUCTION_DECISIONS.md](./MODEL_AND_PRODUCTION_DECISIONS.md) |
| **Account guardrail** | AWS Budget alerts 80% / 100% | [AWS_SETUP.md](./AWS_SETUP.md) |

```python
# app/llm_mantle.py — output limit wired here
limit = max_tokens if max_tokens is not None else settings.mantle_max_tokens
response = _client().chat.completions.create(..., max_tokens=limit)
```

---

## Cost-control checklist (Phase 2 → production mindset)

Use this as a **build log**; check items as we implement later phases.

### Already in capstone

- [x] Local embeddings (Phase 1) — no per-token embed bill on Bedrock  
- [x] `max_tokens` default + per-call override in `mantle_chat`  
- [x] Short smoke test (`max_tokens=16`)  
- [x] AWS monthly budget + email alerts  
- [x] Hybrid stack documented — not pretending everything is “free local”

### Phase 2–3 (planned)

- [ ] Grounded prompt: “be concise”; cite `chunk_id` without repeating full excerpts in the answer  
- [ ] Sensible default `top_k` (e.g. 5) on `/chat`  
- [ ] Log `output_chars` / `finish_reason` in structlog (already in `mantle_chat`) for cost debugging  
- [ ] Optional: truncate excerpt length in prompt if total input exceeds a soft budget  

### Phase 4–5 (enterprise-shaped — interview “north star”)

- [ ] CloudWatch metric: tokens / request (or proxy: latency + char counts)  
- [ ] Per-route or per-tenant quotas  
- [ ] Model routing: smaller model for simple QA, larger for diff/summary  
- [ ] Caching retrieved chunks for repeated queries  
- [ ] IAM + inference profiles / projects for cost allocation tags  

---

## Interview framing (infra / platform / “降本提效”)

Banks and prop shops rarely ask “can you call an LLM?” — they ask **how you run it safely and cheaply at scale**.

### One-liner (English)

> “I cap completion tokens per request, keep retrieval local in Phase 1–2 to avoid Titan embed charges while classic Bedrock was blocked, and bound evidence with `top_k` so input tokens stay predictable. Mantle is metered, so `max_tokens`, timeouts, and AWS budgets are part of the design—not an afterthought.”

### 一句话（中文）

> 「生成侧用 `max_tokens` 和 timeout 卡住最坏情况账单；检索侧用 `top_k` 和本地 embedding 控制输入 token；账号层有 budget 告警——这是平台思维，不是 demo 完就算。」

### If they push: “How would you do this in prod?”

| Concern | Capstone today | Enterprise typical |
|---------|----------------|-------------------|
| Runaway output | `max_tokens=1024` default | Same + per-model policies |
| Huge prompts | `top_k`, future excerpt trim | Token budget in Researcher agent |
| No visibility | structlog fields | CloudWatch, cost allocation tags |
| Model $ | Mantle on-demand | Provisioned throughput, routing, caching |
| Compliance | Public SEC data only | Allow-listed models, audit logs |

Tie to **Jefferies / banking**: regulated environments want **predictable cost**, **audit trails**, and **no unbounded external inference** — token limits are a simple, defensible first control.

---

## FAQ

### Q: Does `max_tokens=16` limit my whole request to 16 tokens?

**No.** Only the **assistant’s generated reply** is capped at ~16 tokens. Your system + user messages can be much longer.

### Q: Why not set `max_tokens` very high “to be safe”?

Higher cap raises **worst-case** output cost and latency. For RAG Q&A, 512–1024 is usually enough; tune with golden queries.

### Q: Is embedding free because it’s local?

No cloud **invoice**, but you pay in **CPU/time** on ingest. Tradeoff documented: local MiniLM for Phase 1–2, Titan + OpenSearch in Phase 4 when AWS embed is available.

### Q: Where do I change the default for `/chat`?

`.env`:

```bash
MANTLE_MAX_TOKENS=1024
```

Or pass `max_tokens=` into `mantle_chat()` from `app/llm.py` when we wire Phase 2 Step 5.

---

## Changelog

| Date | Note |
|------|------|
| 2026-06-11 | Initial doc from Phase 2 Step 2 Chat: `max_tokens` meaning, cost/latency rationale, repo mapping, interview bullets |

<!-- Add rows as we implement prompt trimming, logging, alarms, etc. -->
