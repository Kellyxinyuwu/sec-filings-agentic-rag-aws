# Golden queries — 手动 E2E 验收

> 规格文件：`tests/golden_queries.yaml`  
> 引入阶段：Phase 3 Step 7（延续 Phase 2 的三条 QA + 新增 REFUSE 样例）  
> 与自动化测试的关系：见 [PYTEST.md §8](./PYTEST.md#8-手动-e2e-vs-pytest)

---

## 目录

1. [Golden queries 是什么？](#1-golden-queries-是什么)
2. [为什么用 YAML，而不是 pytest？](#2-为什么用-yaml-而不是-pytest)
3. [和 tests/test_*.py 的分工](#3-和-teststest_py-的分工)
4. [CI 会跑吗？](#4-ci-会跑吗)
5. [YAML 字段说明](#5-yaml-字段说明)
6. [怎么跑（手动步骤）](#6-怎么跑手动步骤)
7. [什么时候该再跑一遍](#7-什么时候该再跑一遍)
8. [以后可以怎么演进](#8-以后可以怎么演进)

---

## 1. Golden queries 是什么？

**Golden queries**（黄金问题集）是一组**固定的、有代表性的用户问题**，用来在**真实环境**下验收整条 RAG / agent 链路是否正常工作。

在本项目里：

- **文件位置：** `tests/golden_queries.yaml`
- **执行方式：** **人手动** `curl`（或 Postman），对照 YAML 里的 `expect` 检查返回
- **不是** pytest 自动收集的测试用例；当前仓库里**没有**代码去读这个 YAML

内容分两类：

| 区块 | 目的 |
|------|------|
| `golden_queries` | 3 条正常 QA（risk / revenue / business overview），应 retrieve + 生成 + verifier pass |
| `refuse_samples` | 投资建议类问题，应 `intent=refuse`、不 retrieve、固定拒答 |

Phase 2 已用同样 3 条 QA 验过「单段 RAG + Mantle」；Phase 3 用同一套题验「四 agent + orchestrator + verifier」是否仍 OK。

---

## 2. 为什么用 YAML，而不是 pytest？

### 需要测的东西不一样

| | `pytest`（`test_*.py`） | Golden（YAML + 手动 curl） |
|--|-------------------------|----------------------------|
| 依赖 | mock DB、mock LLM | 真 pgvector、真 Mantle |
| 速度 | 快（~秒级） | 慢（每条可能 10–30s） |
| 断言 | 代码里写死，自动 pass/fail | 人对照 `expect`，可看答案质量 |
| 稳定性 | 高（无网络/模型波动） | LLM 措辞会变，但 intent/verifier 应稳定 |
| 主要目的 | 逻辑、契约、编排没改坏 | **端到端真的能答、能拒、能 cite** |

pytest 保证「代码结构对」；golden 保证「接上真 DB 和真模型后，用户体验路径对」。

### 为什么放 `tests/` 下却是 YAML？

- 和 `test_*.py` 同属**质量保障**资产，放一起方便发现
- YAML 比 Python 更适合当**可读规格书**（产品/面试演示时一眼能看懂考什么）
- 刻意**不**写成 `test_golden.py`：避免有人误以为 `pytest -q` 会跑 Mantle E2E，或在 CI 里误配 Docker + API key

### 为什么不用 JSON？

YAML 支持注释（`# Requires: docker...`）、多行字符串，改 query 时 diff 更清晰；对本项目这种「人读的清单」足够。

---

## 3. 和 tests/test_*.py 的分工

```
                    ┌─────────────────────────────────────┐
                    │  golden_queries.yaml + 手动 curl     │  慢、真环境、顶层冒烟
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │  test_chat_rag / test_health         │  HTTP 契约（mock run_chat）
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │  test_orchestrator                   │  四 agent 串联（mock retrieve/llm）
                    └──────────────────┬──────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
 test_planner  test_researcher  test_writer  test_verifier   test_retrieve …
        │                              │                              │
        └──────────────────────────────┴──────────────────────────────┘
                              单模块逻辑（mock）
```

**记忆口诀：** 越往下越假、越快；越往上越真、越慢。两者互补，不互相替代。

---

## 4. CI 会跑吗？

**不会。** `.github/workflows/ci.yml` 只做：

- `ruff check app tests`
- `pytest -q`

CI 里没有 Docker DB、没有 Mantle 密钥、也不会读 `golden_queries.yaml`。

Golden eval 是**本地或大 milestone 前的手工验收**（Phase 2/3 收尾、换模型、改 prompt/verifier 后）。若以后要自动化，需要单独 workflow（secrets、compose、且断言应偏结构性，如 `intent` / `verifier_pass`，而非逐字匹配答案）。

---

## 5. YAML 字段说明

**顶层**

| 字段 | 含义 |
|------|------|
| `version` | 清单格式版本，便于以后改 schema |
| `ticker_default` | 未写 `ticker` 时的默认标的 |

**每条 `golden_queries` / `refuse_samples`**

| 字段 | 含义 |
|------|------|
| `id` | 唯一标识，日志/笔记里引用 |
| `query` | 发给 `/chat` 的 `query` |
| `ticker` | 可选，默认 `AAPL` |
| `expect.intent` | `qa` / `refuse` / …，对应 planner |
| `expect.verifier_pass` | 最终 verifier 是否应通过 |
| `expect.evidence_min` | QA 时至少几条 evidence |
| `expect.evidence_count` | REFUSE 时精确条数（常为 0） |
| `expect.answer_contains_any` | 可选，答案里应出现其一（人工扫一眼） |
| `expect.answer_prefix` | 可选，REFUSE 固定文案前缀 |
| `notes` | 给人看的说明，不参与任何自动检查 |

---

## 6. 怎么跑（手动步骤）

**前置**

```bash
cd sec-filings-agentic-rag-aws
source .venv/bin/activate
docker compose up -d db          # 已 ingest 过 AAPL 10-K
# .env 配好 MANTLE_* 
uvicorn app.main:app --reload --port 8001
```

若 `Address already in use`，说明已在跑，可直接 curl；或 `kill $(lsof -t -i :8001)` 后重启。

**1. Health**

```bash
curl -s http://127.0.0.1:8001/health
# 期望: "phase":"3"（Phase 3 完成后）
```

**2. 按 YAML 逐条 POST /chat**

打开 `tests/golden_queries.yaml`，对每条构造请求，例如：

```bash
curl -s -X POST http://127.0.0.1:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the main risk factors?", "ticker": "AAPL"}'
```

**3. 对照 `expect`**

至少检查 JSON 里：

- `plan.intent`
- `evidence` 长度（或 REFUSE 时为 0）
- `agent_steps` 最后一步 verifier 的 `detail`（如 `citations ok`）
- 可选：扫一眼 `answer` 是否符合 `notes` / `answer_contains_any`

**4. REFUSE 样例**

```bash
curl -s -X POST http://127.0.0.1:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Should I buy AAPL?"}'
```

期望：`intent=refuse`，无 evidence，答案以拒答文案开头，verifier 仍 pass。

---

## 7. 什么时候该再跑一遍

- 完成 Phase 2 / Phase 3 等大 milestone
- 更换 Mantle 模型或改 `max_tokens` / prompt
- 修改 `verifier.py`、`planner.py` 规则或 `orchestrator` 重试逻辑
- 重新 ingest 或换 ticker / filing 后
- 发 PR / demo 前做一次端到端冒烟

日常改小逻辑：**`pytest -q` 即可**；不必每条 commit 都跑 golden。

---

## 8. 以后可以怎么演进

| 方向 | 说明 |
|------|------|
| 保持现状 | Portfolio / capstone 足够：YAML + 文档 + 手工 curl |
| `scripts/run_golden.sh` | 读 YAML 发 curl，只打印 intent / verifier（仍本地、半自动） |
| `test_golden_e2e.py` + `@pytest.mark.e2e` | 默认 `pytest` 跳过；`pytest -m e2e` 才跑，需 marker 与 secrets |
| CI nightly job | 有 AWS 预算时，只断言结构性字段，不断言 LLM 全文 |

当前设计是**故意简单**：先分清「自动化回归」和「真链路验收」，避免把慢、贵、不稳定的 E2E 绑进每次 push。

---

## 相关文档

- [PYTEST.md](./PYTEST.md) — pytest、mock、测试分层  
- [PHASE_2.md §8](./PHASE_2.md#8-验收标准) — Phase 2 首次引入 3 条 golden curl  
- [PHASE_3.md](./PHASE_3.md) — Step 7 golden eval + E2E  
- [MODEL_AND_PRODUCTION_DECISIONS.md](./MODEL_AND_PRODUCTION_DECISIONS.md) — 换模型前的 eval 策略
