# SEC Filings Agentic RAG on AWS

Multi-agent RAG over SEC 10-K / 10-Q filings: **ingest → retrieve → Planner → Researcher → Writer → Verifier**, with grounded answers and `chunk_id` citations.

**Status:** Phases 0–5 complete. **Phase 4:** S3 + OpenSearch Serverless data plane. **Phase 5:** ECS Fargate + ALB + CDK (`infra/`), task IAM, Secrets Manager, CloudWatch — live API on ALB.

---

## Architecture

```
POST /chat
  → orchestrator.run_chat()
      → Planner      (rules: QA / REFUSE / SUMMARIZE / DIFF)
      → Researcher   (tools.retrieve — MiniLM + pgvector or OpenSearch)
      → Writer       (grounded prompt + Bedrock Mantle LLM)
      → Verifier     (citation check; fail-closed; max 1 writer retry)
```

| Layer | Component | Technology |
|-------|-----------|------------|
| API | FastAPI | `app/api.py`, `app/main.py` |
| Agents | planner, researcher, writer, verifier | `app/agents/` |
| Retrieval | vector search | `all-MiniLM-L6-v2` + pgvector (default) or **OpenSearch Serverless** (`VECTOR_BACKEND=opensearch`) |
| Generation | LLM | AWS Bedrock **Mantle** (`qwen.qwen3-coder-next`) |
| Storage | vectors + metadata | PostgreSQL 16 + pgvector (Docker, port **5433**); optional **S3** filings + **OpenSearch** index |
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

**Phase 4 (AWS data plane)** — add when using S3 / OpenSearch:

| Variable | Purpose |
|----------|---------|
| `AWS_REGION` | e.g. `us-east-1` |
| `S3_BUCKET` / `S3_PREFIX` | Raw filing upload target |
| `OPENSEARCH_ENDPOINT` / `OPENSEARCH_INDEX` | OpenSearch Serverless collection |
| `VECTOR_BACKEND` | `local` (default, pgvector) or `opensearch` |

AWS credentials: `~/.aws/credentials` (not committed). See `.env.example`.

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

**Local only** (pgvector):

```bash
python scripts/ingest_edgar.py --ticker AAPL
```

**Phase 4 — dual-write to OpenSearch + S3** (needs AWS creds + `.env`):

```bash
python scripts/ingest_edgar.py --ticker AAPL --skip-download --index-opensearch --upload-s3
```

| Flag | Effect |
|------|--------|
| `--skip-download` | Use filings already under `sec-edgar-filings/` |
| `--index-opensearch` | Bulk-index chunks to OpenSearch (embed once, shared with pgvector) |
| `--upload-s3` | Upload `full-submission.txt` to S3 |

Verify cloud retrieve:

```bash
export VECTOR_BACKEND=opensearch
python -c "from app.store import search_similar; print(len(search_similar('risk factors', ticker='AAPL', top_k=3)))"
```

Downloads AAPL 10-K, chunks (400 tokens / 100 overlap), embeds with MiniLM, loads into pgvector. Re-run is safe (stable `chunk_id` upsert).

### 5. Run API

```bash
uvicorn app.main:app --reload --port 8001
```

If `Address already in use`: `kill $(lsof -t -i :8001)` or use the existing process.

---

## Verify your environment

Quick check:

```bash
pytest -q                                    # 61 passed (mocked; CI runs this)
curl -s http://127.0.0.1:8001/health         # {"status":"ok","phase":"4","vector_backend":"local"}
```

Full step-by-step checklist (Docker, ingest, Mantle, golden curl, troubleshooting): **[docs/NOTICE.md](docs/NOTICE.md)**.

Manual E2E spec: `tests/golden_queries.yaml` (not run by pytest or CI).

---

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | `status`, `phase`, `vector_backend` (`local` or `opensearch`) |
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
  main.py, api.py, schemas.py, config.py, aws.py
  store.py, store_opensearch.py, s3_storage.py, opensearch_schema.py
  tools.py                    # retrieve — routes local vs OpenSearch
  llm.py, llm_mantle.py, prompts.py
  orchestrator.py
  agents/                     # planner, researcher, writer, verifier
scripts/
  ingest_edgar.py             # --index-opensearch --upload-s3
  opensearch_create_index.py, s3_smoke_upload.py
  local_dev.sh, test_mantle.py
  ecr_push.py, cdk_ecs_context.py, alb_e2e.py, cdk_teardown.py  # Phase 5
tests/
  test_*.py                   # pytest (mocked; CI-safe)
  golden_queries.yaml         # manual E2E checklist
docker-compose.yml            # pgvector on :5433
infra/                        # CDK: ECS Fargate + ALB + IAM + logs
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
| 4 | **Done** | S3 filings, OpenSearch Serverless k-NN, hybrid embed (local MiniLM) + cloud retrieve |
| 5 | **Done** | ECS Fargate, ALB, CDK, CloudWatch, task IAM, Secrets Manager |

### Phase 5 deploy (summary)

Ingest still runs on your laptop; the API runs on AWS:

```bash
python scripts/ecr_push.py --build
python scripts/secrets_sync_mantle.py
python scripts/cdk_ecs_context.py --deploy
python scripts/aoss_grant_task_role.py
python scripts/alb_e2e.py
```

Details: **[infra/README.md](infra/README.md)** · teardown: `python scripts/cdk_teardown.py`

### Phase 4 hybrid stack (capstone)

| Component | Choice | Why |
|-----------|--------|-----|
| Embeddings | Local `all-MiniLM-L6-v2` (384-d) | No classic Bedrock embed on personal account |
| Vector index | OpenSearch Serverless `sec-chunks` | Cloud k-NN; switch via `VECTOR_BACKEND=opensearch` |
| Raw filings | S3 `filings/{ticker}/{filing_id}/` | Durable object storage |
| LLM | Bedrock **Mantle** | Generation path that works today |
| Agents | Unchanged from Phase 3 | `tools.retrieve()` abstracts backend |

Manual E2E: `docs/NOTICE.md` checklist · local guide `docs/REST_API_AND_CURL.md` (not on GitHub).

---

## License

Portfolio / educational project. SEC filings are public; respect [SEC fair access](https://www.sec.gov/os/webmaster-faq#developers) (User-Agent with contact info).
