# SEC Filings Agentic RAG on AWS

Agentic research assistant over public SEC filings (10-K / 10-Q): **ingest → retrieve → multi-agent answer with citations**, deployed on AWS (Bedrock, OpenSearch, S3, ECS).

**Current status:** Phase 3 complete — four-agent orchestrator + verifier — [PHASE_3.md](docs/PHASE_3.md).

> **How we build:**  
> - **Chat** → full code each step (you paste into files)  
> - **[docs/PHASE_1.md](docs/PHASE_1.md)** → concepts + per-step **implementation notes** (no code)  
> - **README** → phase-level status only (check when a whole phase finishes)  
> - Phase 0 archive: **[docs/PHASE_0.md](docs/PHASE_0.md)** · Index: **[docs/PHASES.md](docs/PHASES.md)**

## Goals

- Build a **multi-agent orchestrator from scratch** (Planner → Researcher → Writer → Verifier).
- Productionize RAG on **AWS** (not local Ollama/pgvector only).
- Portfolio piece for **infra / platform + AI** interviews (IAM, observability, cost, IaC).

## Quick start (local)

```bash
cd sec-filings-agentic-rag-aws
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the main risk factors?", "ticker": "AAPL"}'
```

Or: `./scripts/local_dev.sh`

Run tests: `pytest -q`

---

## Phase progress (update as you go)

Use this section as a **build log**. When you finish a phase, check the box and fill in **Done** notes (date, PR, anything you learned).

| Phase | Status | Summary |
|-------|--------|---------|
| [x] **0** | Done | Project skeleton, schemas, mock `/chat`, CI |
| [x] **1** | Done | EDGAR ingest + chunk + local retrieval — [PHASE_1.md](docs/PHASE_1.md) |
| [x] **2** | Done | Bedrock Mantle grounded `/chat` — [PHASE_2.md](docs/PHASE_2.md) |
| [x] **3** | Done | Agent orchestrator + verifier + golden eval — [PHASE_3.md](docs/PHASE_3.md) |
| [ ] **4** | — | S3 + OpenSearch + embeddings on AWS |
| [ ] **5** | — | ECS Fargate + CDK + CloudWatch |

### Phase 0 — Skeleton + mock API ✅

**Goal:** Runnable repo, clear contracts; Bedrock optional (Support pending OK).

**Detailed guide (all steps + copy-paste code):** **[docs/PHASE_0.md](docs/PHASE_0.md)**

**Summary of what we did:**

| # | Step |
|---|------|
| 1 | GitHub repo `sec-filings-agentic-rag-aws`, clone locally |
| 2 | Remove mistaken nested `app/app/` folder |
| 3 | Flat `app/`: `main.py`, `api.py`, `schemas.py`, `config.py`, `logging_setup.py` |
| 4 | Mock `GET /health`, `POST /chat` (citations, `trace_id`, `agent_steps`, `plan`) |
| 5 | `pyproject.toml`, `.gitignore`, `.env.example`, `scripts/local_dev.sh` |
| 6 | `tests/test_health.py`, `.github/workflows/ci.yml` |
| 7 | Docs: ARCHITECTURE, AWS_SETUP, PHASE_0, PHASES index |
| 8 | Git commit `047641a` — `feat(phase-0): project skeleton and mock agentic RAG API` |
| 9 | AWS (parallel): account, **us-east-1**, credit card, budget **sec-rag-monthly $20** (80%+100% alerts), **2 Support cases** for Bedrock + Anthropic (waiting) |

**Key files:** `app/main.py`, `app/api.py`, `app/schemas.py`, `tests/test_health.py`

**How to verify:** `pytest -q` and `curl` in Quick start; see [PHASE_0.md §11](docs/PHASE_0.md#11-验收清单).

**Done notes:** 2026-06-03 — commit `047641a`; AWS billing+budget done; Bedrock pending Support.

---

### Phase 1 — EDGAR ingest + local retrieval ✅

**Goal:** AAPL 10-K → pgvector → `POST /retrieve` returns real `EvidenceChunk` (no Mantle yet).

**Build guide + step notes:** **[docs/PHASE_1.md](docs/PHASE_1.md)** (concepts, checklist, implementation log).

**Summary of what we did:**

| # | Step |
|---|------|
| 1 | deps + `.env` (SEC identity, `DATABASE_URL`, MiniLM) |
| 2 | Docker pgvector on `:5433` |
| 3 | `app/config.py` — `database_url`, `embedding_model` |
| 4 | `app/store.py` — embed, pgvector, `search_similar` |
| 5 | `scripts/ingest_edgar.py` — AAPL 10-K, 10,834 chunks |
| 6 | `app/tools.py` — `retrieve()` → `EvidenceChunk` |
| 7 | `RetrieveRequest` / `RetrieveResponse` in `schemas.py` |
| 8 | `POST /retrieve`, `/health` phase `"1"`, `/chat` real evidence |
| 9 | `tests/test_retrieve.py` — mock `app.api.retrieve`, CI offline |
| 10 | E2E: `pytest -q` 7 passed + curl retrieve/chat on `:8001` |

**Key files:** `app/store.py`, `scripts/ingest_edgar.py`, `app/tools.py`, `app/api.py`, `tests/test_retrieve.py`

**How to verify:** `docker compose up -d db` → `pytest -q` → `uvicorn app.main:app --port 8001` → curl `/health`, `/retrieve`, `/chat`; see [PHASE_1.md §8](docs/PHASE_1.md#8-验收标准).

**Done notes:** 2026-06-10 — AAPL `0000320193-25-000079` ingested; real vector retrieval works; `/chat` answer still mock until Phase 2.

---

### Phase 2 — Bedrock Mantle RAG + citations ✅

**Goal:** Replace mock answers with AWS Mantle; every answer grounded on retrieved evidence + `chunk_id` citations.

**Build guide + step notes:** **[docs/PHASE_2.md](docs/PHASE_2.md)**

**Summary of what we did:**

| # | Step |
|---|------|
| 1 | `openai` + `.env` / `config.py` — `LLM_PROVIDER`, `MANTLE_*` |
| 2 | `app/llm_mantle.py` + `scripts/test_mantle.py` |
| 3 | `app/llm.py` — provider abstraction (`chat`) |
| 4 | `app/prompts.py` — grounded RAG system/user messages |
| 5 | `app/api.py` — `/chat` real answer; `/health` phase `"2"` |
| 6 | `tests/test_chat_rag.py` + mock fixes in `test_health.py` |
| 7 | E2E: `pytest -q` 11 passed + 3 golden curl on `:8001` |

**Key files:** `app/llm_mantle.py`, `app/llm.py`, `app/prompts.py`, `app/api.py`, `tests/test_chat_rag.py`

**Stack:** local MiniLM + pgvector (retrieve) · **Bedrock Mantle** Qwen3 Coder Next (generation)

**How to verify:** `docker compose up -d db` → `pytest -q` → `uvicorn app.main:app --port 8001` → curl `/chat`; see [PHASE_2.md §8](docs/PHASE_2.md#8-验收标准).

**Done notes:** 2026-06-11 — Mantle `qwen.qwen3-coder-next`; grounded answers with real citations; revenue query correctly refuses when excerpt lacks total figure.

---

### Phase 3 — Agent orchestrator + verifier ✅

**Goal:** Multi-agent loop from scratch; fail-closed if citations missing.

**Build guide + step notes:** **[docs/PHASE_3.md](docs/PHASE_3.md)**（含 §0 架构 Q&A）

**Summary of what we did:**

| # | Step |
|---|------|
| 1 | `app/agents/researcher.py` + `test_researcher.py` |
| 2 | `app/agents/planner.py` + `test_planner.py` |
| 3 | `app/agents/writer.py` + `test_writer.py` |
| 4 | `app/agents/verifier.py` + `test_verifier.py` |
| 5 | `app/orchestrator.py` + `test_orchestrator.py` |
| 6 | `api.py` → orchestrator; `/health` phase `"3"` |
| 7 | `tests/golden_queries.yaml` + E2E curl; [GOLDEN_QUERIES.md](docs/GOLDEN_QUERIES.md) |

**Key files:** `app/orchestrator.py`, `app/agents/*`, `app/api.py`, `tests/golden_queries.yaml`

**Stack:** MiniLM retrieve · Mantle Writer · rule-based Planner/Verifier

**How to verify:** `docker compose up -d db` → `pytest -q` → `uvicorn app.main:app --port 8001` → curl `/health` + golden queries in `tests/golden_queries.yaml`; see [PHASE_3.md](docs/PHASE_3.md) and [GOLDEN_QUERIES.md](docs/GOLDEN_QUERIES.md).

**Done notes:** 2026-06-12 — 33 passed; REFUSE skips retrieve; 3 golden QA + verifier `citations ok` on `:8001`.

---

### Phase 4 — AWS data plane

**Goal:** S3 for documents; OpenSearch for vectors; Bedrock embeddings (or hybrid with local dev fallback).

**Planned work:**

- [ ] S3 buckets + upload from ingest pipeline
- [ ] OpenSearch Serverless index + metadata filters
- [ ] Switch `app/tools.py` retrieval to OpenSearch via env flag

**How to verify:** Re-index on AWS → query from local API against cloud index.

**Done notes:** _…_

---

### Phase 5 — Deploy + platform hardening

**Goal:** One-command deploy; observability and cost awareness.

**Planned work:**

- [ ] `infra/` — CDK (ECS Fargate, IAM task role, ECR)
- [ ] CloudWatch logs + 1–2 alarms
- [ ] README: cost estimate, security notes, 3-min demo script

**How to verify:** `cdk deploy` → `curl` production `/health` and `/chat`.

**Done notes:** _…_

---

## Folder layout — what each part does

Principle: **add folders only when a module grows large** (e.g. `app/agents/` in Phase 3). Until then, keep files flat under `app/`.

```
sec-filings-agentic-rag-aws/
├── app/                 # All importable application code
│   ├── main.py          # FastAPI entry: app instance, logging, routers
│   ├── api.py           # HTTP routes (/health, /chat, …)
│   ├── schemas.py       # Pydantic models (API + agent contracts)
│   ├── config.py        # Settings from .env (AWS region, SEC identity, API key)
│   ├── logging_setup.py # structlog configuration
│   ├── tools.py         # (Phase 1+) RAG tools: retrieve, get_section, diff
│   ├── aws.py           # (Phase 2+) Bedrock, S3, OpenSearch clients
│   ├── orchestrator.py  # (Phase 3+) Agent loop wiring
│   └── agents/          # (Phase 3+) planner, researcher, writer, verifier
├── scripts/             # CLI scripts (not imported as package)
│   ├── local_dev.sh     # venv + uvicorn on :8000
│   └── ingest_edgar.py  # (Phase 1+) download, chunk, index
├── tests/               # pytest + tests/golden_queries.yaml (manual E2E spec)
├── docs/                # Human-readable design + AWS setup
├── infra/               # (Phase 5+) AWS CDK stacks
├── .github/workflows/   # CI on push (ruff + pytest)
├── pyproject.toml       # Dependencies and tool config
├── .env.example         # Template — copy to .env (never commit .env)
└── README.md            # This file — goals, phases, folder guide
```

| Path | Purpose | When you touch it |
|------|---------|-------------------|
| `app/main.py` | Create FastAPI app, mount routes, init logging | Rarely |
| `app/api.py` | Request handlers; calls orchestrator or RAG | Often |
| `app/schemas.py` | Shared types: `ChatRequest`, `Plan`, `EvidenceChunk`, … | When API/agent contract changes |
| `app/config.py` | `Settings` from environment variables | New secrets or AWS settings |
| `app/logging_setup.py` | Structured logs for debugging / demo | Rarely |
| `app/tools.py` | Functions agents call to fetch evidence | Phase 1–4 |
| `app/aws.py` | AWS SDK wrappers (Bedrock, S3, OpenSearch) | Phase 2–4 |
| `app/orchestrator.py` | Run agent pipeline end-to-end | Phase 3 |
| `app/agents/` | One file per agent role | Phase 3 |
| `scripts/` | One-off commands (ingest, local dev) | Phase 1+ |
| `tests/` | Automated checks; keep fast, no AWS in CI unless mocked | Every phase |
| `docs/` | Architecture diagrams, AWS checklist, demo script | End of each phase |
| `infra/` | Infrastructure as code | Phase 5 |

**Not in git (see `.gitignore`):** `.venv/`, `.env`, downloaded filings under `data/` or `sec-edgar-filings/`.

---

## Further reading

- [docs/OLD_VS_NEW_PROJECT.md](docs/OLD_VS_NEW_PROJECT.md) — how this repo differs from prior `SEC-10-K-RAG` (living doc)
- [docs/PHASES.md](docs/PHASES.md) — index of phase build guides (paste-friendly)
- [docs/PHASE_0.md](docs/PHASE_0.md) — Phase 0 full walkthrough + all source code
- [docs/PHASE_1.md](docs/PHASE_1.md) — Phase 1: ingest + local retrieval
- [docs/PHASE_2.md](docs/PHASE_2.md) — Phase 2: Mantle LLM + grounded citations
- [docs/PHASE_3.md](docs/PHASE_3.md) — Phase 3: agent orchestrator + verifier
- [docs/PYTEST.md](docs/PYTEST.md) — pytest、mock、tests/ 文件索引
- [docs/GOLDEN_QUERIES.md](docs/GOLDEN_QUERIES.md) — golden_queries.yaml 是什么、为何手动 E2E、与 CI 的关系
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system diagram and agent roles
- [docs/AWS_SETUP.md](docs/AWS_SETUP.md) — account, Bedrock Support, budgets
- [docs/AWS_ACCOUNT_NOTES.md](docs/AWS_ACCOUNT_NOTES.md) — Root vs IAM, why Bedrock may be blocked
- [docs/BEDROCK_MANTLE_VS_RUNTIME.md](docs/BEDROCK_MANTLE_VS_RUNTIME.md) — Mantle vs classic Runtime, 7-day path
- [docs/MODEL_AND_PRODUCTION_DECISIONS.md](docs/MODEL_AND_PRODUCTION_DECISIONS.md) — model stack (local vs AWS), enterprise prod controls, capstone vs internship
- [docs/TOKEN_AND_COST_CONTROL.md](docs/TOKEN_AND_COST_CONTROL.md) — `max_tokens`, input vs output billing, cost controls (living doc)
- [docs/INGEST_EDGAR_FAQ.md](docs/INGEST_EDGAR_FAQ.md) — SEC download, one vs many tickers, `--skip-download`

## Related work

Prior learning project: `SEC-10-K-RAG` (pgvector + Ollama + FastAPI). See **[docs/OLD_VS_NEW_PROJECT.md](docs/OLD_VS_NEW_PROJECT.md)** for what we reused vs what this repo adds (agents, AWS).
