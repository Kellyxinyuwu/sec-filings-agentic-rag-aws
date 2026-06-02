# SEC Filings Agentic RAG on AWS

Agentic research assistant over public SEC filings (10-K / 10-Q): **ingest → retrieve → multi-agent answer with citations**, deployed on AWS (Bedrock, OpenSearch, S3, ECS).

**Current status:** Phase 0 complete — skeleton + mock API.

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
| [ ] **1** | — | EDGAR ingest + chunk + local retrieval |
| [ ] **2** | — | Bedrock generation + grounded citations |
| [ ] **3** | — | Agent orchestrator + verifier |
| [ ] **4** | — | S3 + OpenSearch + embeddings on AWS |
| [ ] **5** | — | ECS Fargate + CDK + CloudWatch |

### Phase 0 — Skeleton + mock API ✅

**Goal:** Runnable repo, clear contracts, no AWS yet.

**What we did:**

- Flat `app/` layout (`api.py`, `schemas.py`, `config.py`, …) — removed empty placeholder packages.
- `GET /health`, `POST /chat` returning mock answer + citations + `trace_id`.
- Pydantic models: `Plan`, `EvidenceChunk`, `ChatRequest`, `ChatResponse`, etc.
- `pyproject.toml`, pytest, GitHub Actions (ruff + pytest), `.env.example`.
- Docs: [ARCHITECTURE.md](docs/ARCHITECTURE.md), [AWS_SETUP.md](docs/AWS_SETUP.md).

**Key files:** `app/main.py`, `app/api.py`, `app/schemas.py`, `tests/test_health.py`

**How to verify:** `pytest -q` and `curl` commands in Quick start above.

**Done notes:** _(add date / commit hash when you push, e.g. 2026-06-02 — initial scaffold)_

---

### Phase 1 — EDGAR ingest + local retrieval

**Goal:** Download 1–3 tickers from EDGAR, chunk with metadata, retrieve locally (pgvector Docker or similar).

**Planned work:**

- [ ] `scripts/ingest_edgar.py` — download + parse + chunk (reuse ideas from `SEC-10-K-RAG`)
- [ ] `app/tools.py` — `retrieve()`, `get_section()`
- [ ] Local vector store + `POST /retrieve` or retrieval inside `/chat` prep
- [ ] Fill `SEC_COMPANY_NAME` / `SEC_COMPANY_EMAIL` in `.env`

**Key files to add/change:** `scripts/ingest_edgar.py`, `app/tools.py`, `docker-compose.yml` (optional)

**How to verify:** Ingest AAPL 10-K → query returns real chunks with `ticker` / `section` metadata.

**Done notes:** _…_

---

### Phase 2 — Bedrock RAG + citations

**Goal:** Replace mock answers with Bedrock; every answer cites evidence chunks.

**Planned work:**

- [ ] `app/aws.py` — Bedrock client (chat + optional embed)
- [ ] Prompt template: answer only from evidence; citation format
- [ ] Retries, timeouts, token limits
- [ ] AWS: enable models per [AWS_SETUP.md](docs/AWS_SETUP.md)

**Key files:** `app/aws.py`, `app/api.py` (wire RAG path)

**How to verify:** Same 3 golden questions return answers with valid `chunk_id` citations.

**Done notes:** _…_

---

### Phase 3 — Agent orchestrator + verifier

**Goal:** Multi-agent loop from scratch; fail-closed if citations missing.

**Planned work:**

- [ ] `app/orchestrator.py` — Planner → Researcher → Writer → Verifier (max 1 retry)
- [ ] `app/agents/` — `planner.py`, `researcher.py`, `writer.py`, `verifier.py`
- [ ] `/chat` calls orchestrator instead of mock
- [ ] `tests/golden_queries.yaml` + basic eval

**How to verify:** Verifier rejects unsupported claims; logs show `agent_steps` with latencies.

**Done notes:** _…_

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
├── tests/               # pytest; golden_queries.yaml later
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

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system diagram and agent roles
- [docs/AWS_SETUP.md](docs/AWS_SETUP.md) — account, Bedrock access, budgets

## Related work

Prior learning project: `SEC-10-K-RAG` (pgvector + Ollama + FastAPI) — reuse ingest/chunk patterns in Phase 1.
