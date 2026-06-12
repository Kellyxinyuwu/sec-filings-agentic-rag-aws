# SEC Filings Agentic RAG on AWS

Multi-agent RAG over SEC 10-K / 10-Q filings: **ingest → retrieve → Planner → Researcher → Writer → Verifier**, with grounded answers and `chunk_id` citations.

**Status:** Phases 0–3 complete (local pgvector + Bedrock Mantle + agent orchestrator). Phases 4–5 planned (AWS data plane + ECS deploy).

---

## Architecture

```
POST /chat
  → orchestrator.run_chat()
      → Planner      (rules: QA / REFUSE / SUMMARIZE / DIFF)
      → Researcher   (tools.retrieve — local MiniLM + pgvector)
      → Writer       (grounded prompt + Bedrock Mantle LLM)
      → Verifier     (citation check; fail-closed; max 1 writer retry)
```

| Layer | Component | Technology |
|-------|-----------|------------|
| API | FastAPI | `app/api.py`, `app/main.py` |
| Agents | planner, researcher, writer, verifier | `app/agents/` |
| Retrieval | vector search | `sentence-transformers/all-MiniLM-L6-v2` + pgvector |
| Generation | LLM | AWS Bedrock **Mantle** (`qwen.qwen3-coder-next`) |
| Storage | vectors + metadata | PostgreSQL 16 + pgvector (Docker, port **5433**) |
| CI | lint + unit tests | GitHub Actions: `ruff` + `pytest` (no live DB/LLM) |

---

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| Python 3.11+ | CI uses 3.11; 3.14 works locally |
| Docker | For pgvector database |
| AWS Bedrock Mantle | API key + model access in `us-east-1` (or your region) |
| SEC EDGAR identity | Real `SEC_COMPANY_NAME` / `SEC_COMPANY_EMAIL` in `.env` for ingest |

---

## Local environment setup

### 1. Clone and Python env

```bash
cd sec-filings-agentic-rag-aws
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Environment variables

```bash
cp .env.example .env
```

Edit `.env` — minimum for full `/chat`:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5433/rag_db` |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` |
| `SEC_COMPANY_NAME` / `SEC_COMPANY_EMAIL` | SEC User-Agent (required for downloads) |
| `LLM_PROVIDER` | `mantle` |
| `MANTLE_BASE_URL` | e.g. `https://bedrock-mantle.us-east-1.api.aws/v1` |
| `MANTLE_API_KEY` | From Mantle console |
| `MANTLE_MODEL_ID` | e.g. `qwen.qwen3-coder-next` |

Optional: `MANTLE_MAX_TOKENS=1024`, `LOG_LEVEL=INFO`.

Test Mantle only (no DB):

```bash
python scripts/test_mantle.py
```

### 3. Database

```bash
docker compose up -d db
docker compose ps   # db should be healthy
```

Postgres listens on **host port 5433** (not 5432).

### 4. Ingest sample data (first time)

```bash
python scripts/ingest_edgar.py --ticker AAPL
```

Downloads AAPL 10-K, chunks, embeds, loads into pgvector. Re-run safe; use `--skip-download` if filings already on disk.

### 5. Run API

```bash
uvicorn app.main:app --reload --port 8001
```

If `Address already in use`: `kill $(lsof -t -i :8001)` or use the existing process.

---

## Verify your environment

Quick check:

```bash
pytest -q                                    # 33 passed (mocked; CI runs this)
curl -s http://127.0.0.1:8001/health         # {"status":"ok","phase":"3"}
```

Full step-by-step checklist (Docker, ingest, Mantle, golden curl, troubleshooting): **[docs/NOTICE.md](docs/NOTICE.md)**.

Manual E2E spec: `tests/golden_queries.yaml` (not run by pytest or CI).

---

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | `status`, `phase` |
| `POST` | `/retrieve` | Vector search → `EvidenceChunk[]` |
| `POST` | `/chat` | Full agent pipeline → answer + citations + `agent_steps` + `plan` |

**Chat request body:**

```json
{
  "query": "What are the main risk factors?",
  "ticker": "AAPL",
  "filing_ids": []
}
```

---

## Project layout

```
app/
  main.py, api.py, schemas.py, config.py
  store.py, tools.py          # embed + pgvector retrieve
  llm.py, llm_mantle.py, prompts.py
  orchestrator.py
  agents/                     # planner, researcher, writer, verifier
scripts/
  ingest_edgar.py, local_dev.sh, test_mantle.py
tests/
  test_*.py                   # pytest (mocked; CI-safe)
  golden_queries.yaml         # manual E2E checklist
docker-compose.yml            # pgvector on :5433
infra/                        # Phase 5 CDK (planned)
```

**Not committed:** `.env`, `.venv/`, `data/`, `sec-edgar-filings/`, and most of `docs/` (local learning notes). On GitHub you only see **[docs/NOTICE.md](docs/NOTICE.md)** — folder notice + local env checklist.

---

## Testing strategy

| Type | Command | Needs |
|------|---------|-------|
| Unit / API (CI) | `pytest -q` | Nothing live; mocks DB + LLM |
| Manual E2E | curl + `golden_queries.yaml` | Docker DB, ingest, Mantle, uvicorn |

Golden eval is intentional manual smoke — slow, model-dependent, not wired into GitHub Actions.

---

## Roadmap

| Phase | Status | Scope |
|-------|--------|--------|
| 0–3 | Done | Skeleton, ingest, Mantle RAG, agent orchestrator + verifier |
| 4 | Planned | S3, OpenSearch, Bedrock embeddings |
| 5 | Planned | ECS Fargate, CDK, CloudWatch |

---

## License

Portfolio / educational project. SEC filings are public; respect [SEC fair access](https://www.sec.gov/os/webmaster-faq#developers) (User-Agent with contact info).
