# pytest 测试指南（本项目）

> 本文收录 Phase 3 Step 1 之后关于 **pytest、mock、全量回归** 的 Q&A，并索引 `tests/` 下每个文件测什么。  
> 配置见根目录 `pyproject.toml` → `[tool.pytest.ini_options]`（`testpaths = ["tests"]`）。

---

## 目录

1. [pytest 是什么？等于开发时 mock test 吗？](#1-pytest-是什么等于开发时-mock-test-吗)
2. [只跑一个文件 vs 跑全量](#2-只跑一个文件-vs-跑全量)
3. [pytest 文件怎么被「定义」](#3-pytest-文件怎么被定义)
4. [mock 与 monkeypatch：patch 路径为什么是 api.retrieve](#4-mock-与-monkeypatchpatch-路径为什么是-apiretrieve)
5. [本项目的测试分层](#5-本项目的测试分层)
6. [tests/ 文件索引](#6-tests-文件索引)
7. [常用命令](#7-常用命令)
8. [手动 E2E vs pytest](#8-手动-e2e-vs-pytest)

---

## 1. pytest 是什么？等于开发时 mock test 吗？

**pytest** 是 Python 的**自动化测试框架**。开发时或 CI（`.github/workflows/ci.yml`）里跑一遍，确认代码行为符合预期。

测试不只有 mock，常见几类：

| 类型 | 干什么 | 本项目例子 |
|------|--------|------------|
| **单元测试** | 测一个函数/模块 | `test_researcher.py` — 只测 `run_research()` |
| **API 测试** | 测 HTTP 路由与 JSON 契约 | `test_health.py`、`test_retrieve.py`、`test_chat_rag.py` |
| **带 mock 的测试** | 外部依赖换成假的 | mock `retrieve`、`llm_chat` — 不连 DB、不调 Mantle |
| **集成 / E2E** | 真 DB + 真 LLM | 终端里 `curl /chat`、ingest 后手测 — **不在 pytest 里** |

所以：**mock 是 pytest 里很常用的一种手段**，不是 pytest 的全部。  
目标：**快、稳、不依赖 Docker/Mantle/embedding 模型**，同时仍能验证逻辑和 API 契约。

---

## 2. 只跑一个文件 vs 跑全量

```bash
# 只跑 Researcher 的 3 个用例（改完 Step 1 时用）
pytest tests/test_researcher.py -q

# 跑 tests/ 下全部用例（提交前 / 做完一步后的回归）
pytest -q
```

| 命令 | 何时用 |
|------|--------|
| `pytest tests/test_xxx.py -q` | 刚改完某个模块，快速确认 |
| `pytest -q` | **回归** — 新代码有没有弄坏旧功能 |

全量通过 = 新测试 **和** 旧测试都过。例如 Phase 3 Step 1 后：`11 + 3 = 14 passed`。

**注意：** 必须在项目根目录 `sec-filings-agentic-rag-aws/` 下跑。在父目录 `AI learning` 跑会误收集旧项目 `SEC-10-K-RAG/tests`。

---

## 3. pytest 文件怎么被「定义」

### 命名规则（自动发现，不用写 main）

| 规则 | 例子 |
|------|------|
| 文件 | `test_*.py` 或 `*_test.py` |
| 函数 | `def test_something():` — 必须以 `test_` 开头 |

### assert

```python
assert len(chunks) == 1   # 对 → 通过；错 → 失败并打印实际值
```

### @pytest.fixture（夹具）

测试前准备的共用逻辑。下面函数参数名与 fixture 同名时，pytest **先跑 fixture**，再注入：

```python
@pytest.fixture
def mock_retrieve(monkeypatch):
    ...

def test_xxx(mock_retrieve):  # 自动拿到 fixture 返回值
    ...
```

每个 `test_` 函数都会拿到**新的** fixture 实例，测试之间互不污染。

### monkeypatch

在**单次测试运行期间**临时替换模块属性，测完自动恢复。

### MagicMock

假函数，且可检查「被怎么调的」：

```python
mock.assert_called_once_with("query", ticker="AAPL", top_k=5)
mock.assert_not_called()
```

比「返回值碰巧对」更严 — 能验证**调用参数**是否正确。

---

## 4. mock 与 monkeypatch：patch 路径为什么是 api.retrieve

`api.py` 里是：

```python
from app.tools import retrieve
```

在 **api 模块命名空间**里，名字是 `retrieve`。因此要 patch：

```python
from app import api
monkeypatch.setattr(api, "retrieve", mock)   # ✅
# monkeypatch.setattr("app.tools.retrieve", mock)  # ❌ 常常无效
```

原因：`api` 已经 `import` 了一份 `retrieve` 引用；改 `tools` 里的对象，**不会**改变 `api` 里已绑定的名字。

同一套路：

| 被测代码 | patch 路径 |
|----------|------------|
| `api.py` 里的 retrieve | `app.api.retrieve` |
| `researcher.py` 里的 retrieve | `app.agents.researcher.retrieve` |
| `api.py` 里的 llm_chat | `app.api.llm_chat` |

---

## 5. 本项目的测试分层

```
                    ┌─────────────────────────────────────┐
                    │  手动 E2E：curl /chat, ingest, DB   │
                    └─────────────────────────────────────┘
                                      ▲
                    ┌─────────────────┴───────────────────┐
                    │  API 测试（TestClient + mock）       │
                    │  test_health, test_retrieve,        │
                    │  test_chat_rag                      │
                    └─────────────────┬───────────────────┘
                                      ▲
                    ┌─────────────────┴───────────────────┐
                    │  单元测试（直接调函数 + mock）        │
                    │  test_researcher, test_planner,     │
                    │  test_writer, test_verifier          │
                    └─────────────────────────────────────┘
```

- **越往下**：越快、越 isolated、越适合 CI  
- **越往上**：越接近真实环境，越慢，通常手动做

---

## 6. tests/ 文件索引

| 文件 | Phase | 测什么 | Mock 什么 |
|------|-------|--------|-----------|
| [test_health.py](../tests/test_health.py) | 0+ | `GET /health`；`POST /chat` 最小契约 | `/chat` 时 mock `api.retrieve` + `api.llm_chat` |
| [test_retrieve.py](../tests/test_retrieve.py) | 1+ | `POST /retrieve` 请求/响应、top_k 校验 | `app.api.retrieve` |
| [test_chat_rag.py](../tests/test_chat_rag.py) | 2+ | `POST /chat` 全路径：answer、citations、agent_steps、plan | `app.api.retrieve` + `app.api.llm_chat` |
| [test_researcher.py](../tests/test_researcher.py) | 3+ | `run_research()` 单元逻辑 | `app.agents.researcher.retrieve` |
| [test_planner.py](../tests/test_planner.py) | 3+ | `run_planner()` 规则：QA / REFUSE / summarize / diff | 无（纯规则） |
| [test_writer.py](../tests/test_writer.py) | 3+ | `run_writer()`：LLM 路径 + REFUSE 跳过 LLM | `app.agents.writer.llm_chat` |
| [test_verifier.py](../tests/test_verifier.py) | 3+ | `verify_answer()`：citation / fail-closed | 无（纯规则） |

Phase 3 后续还会增加：`test_orchestrator.py` 等。全量当前 **29 passed**（Step 4 后）。

---

## 7. 常用命令

```bash
cd sec-filings-agentic-rag-aws
source .venv/bin/activate

pytest -q                              # 全量
pytest tests/test_researcher.py -q     # 单文件
pytest tests/test_researcher.py -v     # _verbose：列出每个 test_ 函数名
pytest -k "retrieve" -q                # 只跑名字里含 retrieve 的用例
pytest --collect-only                  # 只看会收集哪些测试，不执行
```

---

## 8. 手动 E2E vs pytest

| | pytest（CI） | 手动 E2E |
|--|--------------|----------|
| 数据库 | mock，不连 | `docker compose up -d db` + ingest |
| LLM | mock，不调 Mantle | `.env` 配好 key，`uvicorn` + `curl` |
| 目的 | 契约 + 逻辑回归 | 真 RAG 质量、延迟、golden queries |
| 何时跑 | 每次 commit / CI | Phase 每步验收、发 PR 前 |

两者**都要**：pytest 保证「没改坏」；curl 保证「真的好使」。  
Golden 问题清单、字段含义、何时重跑：见 **[GOLDEN_QUERIES.md](./GOLDEN_QUERIES.md)**。

---

## 相关文档

- [GOLDEN_QUERIES.md](./GOLDEN_QUERIES.md) — `tests/golden_queries.yaml`、手动 E2E、为何不进 CI  
- [PHASE_1.md](./PHASE_1.md) — Step 9 测试说明  
- [PHASE_2.md](./PHASE_2.md) — Step 6 `test_chat_rag`、patch 注意  
- [PHASE_3.md](./PHASE_3.md) — Step 1 `test_researcher`  
- 根目录 [README.md](../README.md) — `pytest -q` Quick start
