# Notice — `docs/` folder

**This is the only file under `docs/` published to GitHub.**

Everything else in this folder (phase build guides, architecture notes, AWS setup logs, pytest Q&A, etc.) stays **on my machine** for learning — not tracked in git. If you clone the repo, you will only see this notice plus an otherwise empty `docs/` directory.

For project overview, architecture, and quick start, see the root **[README.md](../README.md)**.

The sections below also serve as a **local environment verification checklist** when running this project on my machine.

---

## What lives locally (not on GitHub)

Typical files I keep here while building — you will not get them from `git clone`:

| File | Purpose |
|------|---------|
| `PHASE_0.md` … `PHASE_3.md` | Step-by-step build logs per phase |
| `PHASES.md` | Index of phase guides |
| `ARCHITECTURE.md` | Diagrams and design notes |
| `PYTEST.md` | Mock / patch conventions |
| `GOLDEN_QUERIES.md` | Manual E2E eval explained |
| `AWS_SETUP.md`, `AWS_ACCOUNT_NOTES.md` | Account, Bedrock, budget |
| `BEDROCK_MANTLE_VS_RUNTIME.md` | Mantle vs classic Runtime |
| `MODEL_AND_PRODUCTION_DECISIONS.md` | Model stack tradeoffs |
| `TOKEN_AND_COST_CONTROL.md` | `max_tokens`, billing |
| `INGEST_EDGAR_FAQ.md` | SEC download FAQ |
| `OLD_VS_NEW_PROJECT.md` | vs prior `SEC-10-K-RAG` repo |
| `SOURCE_CONTROL_SETUP.md` | Cursor SCM 嵌套 git / 父 folder 踩坑与修复 |
| `GIT_COMMIT_AND_SYNC.md` | Commit vs Sync（Push）左下角圈圈箭头 |
| `REST_API_AND_CURL.md` | REST API 是什么、curl 测什么、三个 endpoint 示例 |
| `PHASE_4_STEP_8.md` | Phase 4 Step 8 实现前指南（README Done + teardown） |
| `PHASE_5.md` | Phase 5 部署面规划（Docker + ECS + CDK）— Step 1 ✅ |

---

## Prerequisites

| Requirement | Check |
|-------------|--------|
| **Python 3.11+** | `python3 --version` |
| **Docker Desktop** | `docker compose version` |
| **venv + deps** | `pip install -e ".[dev]"` from repo root |
| **`.env`** | Copied from `.env.example`, filled in (see below) |
| **Bedrock Mantle** | API key + model in Mantle console (`us-east-1` or your region) |
| **SEC identity** | Real name + email for EDGAR User-Agent |

---

## Environment variables (`.env`)

Minimum to run full `/chat` (retrieve + Mantle + agents):

```bash
# Database (docker-compose maps host 5433 → container 5432)
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/rag_db
EMBEDDING_MODEL=all-MiniLM-L6-v2

# SEC (required for ingest downloads)
SEC_COMPANY_NAME=Your Name
SEC_COMPANY_EMAIL=you@example.com

# LLM — Bedrock Mantle (OpenAI-compatible)
LLM_PROVIDER=mantle
MANTLE_BASE_URL=https://bedrock-mantle.us-east-1.api.aws/v1
MANTLE_API_KEY=<from Mantle console>
MANTLE_MODEL_ID=qwen.qwen3-coder-next
```

Optional: `MANTLE_MAX_TOKENS=1024`, `LOG_LEVEL=INFO`, `APP_ENV=local`.

**Mantle-only smoke test** (no database):

```bash
source .venv/bin/activate
python scripts/test_mantle.py
```

---

## Setup sequence

Run from repo root with venv activated.

### 1. Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# edit .env
```

### 2. PostgreSQL + pgvector

```bash
docker compose up -d db
docker compose ps
```

Wait until `db` is **healthy**. Postgres is on **localhost:5433** (not 5432).

### 3. Ingest AAPL 10-K (first time)

**Local (pgvector only):**

```bash
python scripts/ingest_edgar.py --ticker AAPL
```

**Phase 4 — also index OpenSearch and/or upload S3** (optional):

```bash
python scripts/ingest_edgar.py --ticker AAPL --skip-download --index-opensearch --upload-s3
```

Expect thousands of chunks indexed. Re-run is safe; use `--skip-download` if filings already on disk under `sec-edgar-filings/`.

Cloud retrieve smoke (after `--index-opensearch`):

```bash
export VECTOR_BACKEND=opensearch
python -c "from app.store import search_similar; print(len(search_similar('risk factors', ticker='AAPL', top_k=3)))"
```

Expect `3` (or `top_k`) when index is populated.

### 4. Start API

```bash
uvicorn app.main:app --reload --port 8001
```

**Port already in use?** Another uvicorn may still be running:

```bash
lsof -i :8001
kill $(lsof -t -i :8001)   # if you need a clean restart
```

---

## Verification checklist

Run top to bottom. Mark each when output matches.

### A. Automated tests (offline — no Docker / Mantle)

```bash
pytest -q
```

| Expected | |
|----------|--|
| `61 passed` | All agent + API + Phase 4 tests green |
| CI | Same on GitHub Actions (`ruff` + `pytest`) |

These tests **mock** DB and LLM. Passing pytest does **not** prove Mantle or pgvector work.

### B. Health

```bash
curl -s http://127.0.0.1:8001/health
```

| Expected | |
|----------|--|
| `"status":"ok"` | API up |
| `"phase":"4"` | AWS data plane wired (S3 + OpenSearch) |
| `"vector_backend"` | `local` (pgvector) or `opensearch` — matches `.env` at server start |

### C. Retrieve (real DB + embedding model)

```bash
curl -s -X POST http://127.0.0.1:8001/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "risk factors", "ticker": "AAPL", "top_k": 3}' | python3 -m json.tool
```

| Expected | |
|----------|--|
| HTTP 200 | |
| `chunks` non-empty | Ingest completed |
| Real `chunk_id` | e.g. `AAPL-0000320193-25-000079-...` |
| `score` floats | Vector similarity |

First retrieve after restart may be slow (~10–20s) while MiniLM loads; OpenSearch first call can be slower.

**Phase 4 verified (2026-06-13, `VECTOR_BACKEND=opensearch`):** 3 chunks; top `AAPL-0000320193-25-000079-00209` score ~0.72.

### C2. Retrieve — OpenSearch backend (Phase 4)

Set in `.env`: `VECTOR_BACKEND=opensearch`, restart uvicorn. Same curl as §C; data comes from AWS OpenSearch index `sec-chunks` (not pgvector).

---

### D. Chat — REFUSE (no retrieve, no Mantle)

```bash
curl -s -X POST http://127.0.0.1:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Should I buy AAPL?"}' | python3 -m json.tool
```

| Field | Expected |
|-------|----------|
| `plan.intent` | `refuse` |
| `evidence` | `[]` (length 0) |
| `answer` | Starts with investment-advice refusal |
| `agent_steps` | verifier `citations ok` |

### E. Chat — golden queries (manual E2E)

Spec file: `tests/golden_queries.yaml` (also not auto-run by pytest).

```bash
# 1 — Risk factors
curl -s -X POST http://127.0.0.1:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the main risk factors?", "ticker": "AAPL"}'

# 2 — Revenue
curl -s -X POST http://127.0.0.1:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What was total net sales or revenue discussion?", "ticker": "AAPL"}'

# 3 — Business overview
curl -s -X POST http://127.0.0.1:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Who is the company or what is the business overview?", "ticker": "AAPL"}'
```

| Expected (each QA query) | |
|--------------------------|--|
| `plan.intent` | `qa` |
| `evidence` | Non-empty (typically ~5 chunks) |
| `agent_steps[-1]` | verifier, `detail`: `citations ok` |
| `answer` | Grounded on excerpts; cites `chunk_id` in text |

**Phase 4 verified (2026-06-13, opensearch backend):** QA risk factors → 5 evidence chunks, verifier `citations ok`, Mantle answer with `[AAPL-...]` refs.

Revenue query may **honestly decline** to state a total figure if excerpts lack it — that is correct grounding behavior.

---

## Phase 5 Step 1 — Docker local smoke (verified 2026-06-02)

Containerized FastAPI on port **8000** (local uvicorn stays on **8001**).

```bash
cd sec-filings-agentic-rag-aws
docker build -t sec-rag-api:local .
docker rm -f sec-rag-api-smoke 2>/dev/null
docker run --rm -p 127.0.0.1:8000:8000 --env-file .env \
  -v "$HOME/.aws:/root/.aws:ro" \
  --name sec-rag-api-smoke \
  sec-rag-api:local
```

Second terminal:

```bash
curl -s http://127.0.0.1:8000/health
python scripts/docker_smoke.py
docker ps --filter name=sec-rag-api-smoke
```

| Check | Expected |
|-------|----------|
| `/health` | `status: ok`, `phase: 4`, `vector_backend: opensearch` |
| `docker_smoke.py` | `OK: container health check passed` |
| `docker ps` PORTS | `127.0.0.1:8000->8000/tcp` |

**macOS gotcha:** `-p 8000:8000` may leave `PORTS` as bare `8000/tcp` and curl returns empty reply; use `-p 127.0.0.1:8000:8000`.

**Image size:** ~8.8 GB (`sentence-transformers` + PyTorch CPU). Optional build-time MiniLM warmup is commented out in `Dockerfile`.

---

## Phase 5 Step 2 — CDK skeleton (verified 2026-06-02)

**What we built:** Python CDK app under `infra/` — `SecRagStack` empty skeleton + `StackPhase` output; no AWS deploy yet.

**Prerequisite:** Node.js 18+ on PATH (`brew install node` if missing). CDK Python (jsii) needs Node even for `python3 app.py`.

```bash
node --version
cd sec-filings-agentic-rag-aws
source .venv/bin/activate
cd infra
pip install -r requirements.txt
python3 app.py
```

| Check | Expected |
|-------|----------|
| Terminal | `OK: synth complete → .../cdk.out/` |
| `cdk.out/SecRagStack.template.json` | Exists |
| CloudFormation Outputs | `StackPhase` = `5-step2-skeleton` |

**Issues fixed during Step 2:**

| Issue | Fix |
|-------|-----|
| `No such file or directory: 'node'` | `brew install node`; `app.py` preflight with install hint |
| `Unable to parse aws:///us-east-1` | `cdk.Aws.ACCOUNT_ID` fallback when `CDK_DEFAULT_ACCOUNT` unset |
| Synth output in `/tmp` only | `app.py` copies assembly to `infra/cdk.out/` |
| Node v26 jsii warning banner | `JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1` in `app.py` |

No `cdk deploy` yet. Step 3: `npm install -g aws-cdk` + ECR push.

---

## Phase 5 Step 3 — ECR + push image (verified 2026-06-13)

**Goal:** Push Step 1 Docker image to private ECR so Step 4 ECS can pull `sec-rag-api:latest`.

**Path used:** AWS Console create repo + IAM policy + `scripts/ecr_push.py` (CDK `cdk deploy` skipped — no CloudFormation/SSM on dev-kelly).

### A. AWS Console — ECR

1. **ECR** → **us-east-1** → **Create repository** → Private
2. Name: `sec-rag-api` | Tag mutability: **Mutable** | Encryption: **AES-256**

### B. AWS Console — IAM (dev-kelly)

1. **IAM** → **Users** → **dev-kelly** → **Add permissions**
2. Attach **`AmazonEC2ContainerRegistryPowerUser`** (recommended), or inline JSON in `docs/PHASE_5.md` Step 3.3

### C. Local commands (repo root)

```bash
cd sec-filings-agentic-rag-aws
source .venv/bin/activate
eval "$(python scripts/cdk_env.py)"    # not aws sts (pyexpat broken locally)

python3 -c "
import boto3
ecr = boto3.client('ecr', region_name='us-east-1')
print(ecr.describe_repositories(repositoryNames=['sec-rag-api'])['repositories'][0]['repositoryUri'])
"

python scripts/ecr_push.py             # reuse sec-rag-api:local; no --build
```

### D. Verified

| Check | Result |
|-------|--------|
| Push | `OK: pushed 449873021145.dkr.ecr.us-east-1.amazonaws.com/sec-rag-api:latest` |
| Digest | `sha256:9565933ef560...` |
| ECR size | ~3139 MB compressed (~8.8 GB local) |

### E. Code added

| File | Purpose |
|------|---------|
| `infra/stacks/sec_rag_stack.py` | CDK `ecr.Repository` (optional deploy) |
| `scripts/ecr_push.py` | login → tag → push |
| `scripts/cdk_env.py` | export `CDK_DEFAULT_ACCOUNT` via boto3 |
| `scripts/ensure_ecr_repo.py` | boto3 create repo fallback |

### F. Troubleshooting (summary)

| Issue | Fix |
|-------|-----|
| `aws sts` pyexpat error | `eval "$(python scripts/cdk_env.py)"` |
| `cdk_env.py` not found | Run from **repo root**, not `infra/` |
| Layers Pushed, manifest **403** | Add `ecr:PutImage` + attach **AmazonEC2ContainerRegistryPowerUser** |
| First push slow (~1h) | Normal — PyTorch layer ~3GB; retry is fast (`Layer already exists`) |

Full Q&A (layers, what is pushed, etc.): local `docs/PHASE_5.md` Step 3.7.

---

## Phase 4 teardown (save AWS cost after demo)

OpenSearch Serverless bills by **OCU** while the collection exists — delete it when not actively developing.

| Step | Action |
|------|--------|
| 1 | AWS Console → **OpenSearch Serverless** → collection `kelly-sec-rag-vectors` → **Delete** |
| 2 | Optional: S3 → bucket `kelly-sec-rag-filings-wxy` → empty `filings/` prefix or delete bucket |
| 3 | Optional: IAM → remove inline policy `sec-rag-aoss-dev` and data access policy `sec-rag-data-access` |
| 4 | Local: `docker compose down` stops pgvector |

To resume later: recreate collection + index (`scripts/opensearch_create_index.py`), re-run ingest with `--index-opensearch`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `pytest` fails | Code regression | Read failure; fix tests or code |
| `connection refused` on 8001 | API not running | `uvicorn app.main:app --port 8001` |
| `Address already in use` | Old uvicorn | Use existing server or `kill $(lsof -t -i :8001)` |
| Empty `chunks` on `/retrieve` | DB empty or wrong URL | `docker compose ps`; re-run ingest |
| DB connection error | Docker down | `docker compose up -d db` |
| Mantle 401 / 403 | Bad key or region | Check `MANTLE_*` in `.env` |
| Mantle timeout | Cold start / long answer | Retry; raise `MANTLE_TIMEOUT_SECONDS` |
| Slow first `/chat` | MiniLM + Mantle load | Normal; check `agent_steps` latencies |

---

## What CI does vs what you run locally

| | GitHub Actions CI | This checklist |
|--|-----------------|----------------|
| `ruff` | Yes | Optional locally |
| `pytest -q` | Yes | Yes |
| Docker + ingest | No | Yes for `/retrieve` / `/chat` |
| Mantle live calls | No | Yes for `/chat` QA |
| `golden_queries.yaml` | No | Manual curl |

**Both matter:** pytest catches broken logic on every push; this checklist catches broken real dependencies before a demo.
