# SEC Filings Agentic RAG on AWS

Production-style demo: multi-agent RAG over SEC 10-K / 10-Q filings with grounded answers, `chunk_id` citations, and investment-advice guardrails. Data plane on S3 + OpenSearch Serverless; API on ECS Fargate behind an Application Load Balancer.

---

## Overview

This service answers factual questions about public company SEC filings. It does **not** provide investment or trading advice.

**Pipeline (`POST /chat`):**

```
Planner → Researcher → Writer → Verifier
   │          │           │         │
 rules    vector search  Mantle LLM  citation check
```

| Agent | Role |
|-------|------|
| **Planner** | Classifies intent: QA, summarize, diff, or **refuse** (e.g. “Should I buy AAPL?”) |
| **Researcher** | Retrieves top-k evidence chunks via vector search |
| **Writer** | Generates a grounded answer with inline `[chunk_id]` citations |
| **Verifier** | Validates citations; fail-closed with at most one writer retry |

**Ingest** (laptop or CI): download EDGAR filings → chunk → embed → index to OpenSearch (+ optional local pgvector for dev).

---

## AWS services

| Service | Purpose |
|---------|---------|
| **Amazon ECS (Fargate)** | Runs the FastAPI container (`sec-rag-api`, 1 vCPU / 2 GB) |
| **Application Load Balancer** | Stable HTTP endpoint; `/health` target checks |
| **Amazon ECR** | Container image registry (`sec-rag-api:latest`) |
| **Amazon S3** | Raw filing objects (`filings/{ticker}/{filing_id}/`) |
| **OpenSearch Serverless (AOSS)** | k-NN vector index (`sec-chunks`) |
| **AWS Secrets Manager** | `MANTLE_API_KEY` injected into ECS tasks |
| **Amazon CloudWatch Logs** | Task logs (`/ecs/sec-rag-api`) |
| **AWS IAM** | Task role (S3 + AOSS data access); CDK deploy roles |
| **AWS CloudFormation** | CDK-managed stack `SecRagStack` |
| **Amazon Bedrock Mantle** | LLM generation (API key auth, not classic `bedrock-runtime`) |

**Region:** `us-east-1` (default across infra and data plane).

Deploy details, IAM, and teardown: **[infra/README.md](infra/README.md)**.

---

## Technology selection

Design choices for a personal-account capstone that still mirrors production patterns.

| Layer | Selection | Rationale |
|-------|-----------|-----------|
| **Embeddings** | `all-MiniLM-L6-v2` (384-d), computed locally | No managed embed API required on personal Bedrock; same model at ingest and query time |
| **Vector store (prod)** | OpenSearch Serverless k-NN | Managed, scales with collection; `VECTOR_BACKEND=opensearch` on ECS |
| **Vector store (dev)** | PostgreSQL 16 + pgvector (Docker) | Fast local iteration without AWS |
| **Raw filings** | S3 | Durable object store; task role read access |
| **LLM** | Bedrock **Mantle** — `qwen.qwen3-coder-next` | Generation path available on personal accounts; synced via Secrets Manager on ECS |
| **Orchestration** | Custom Python agents (not LangGraph) | Explicit planner / verifier for auditability |
| **Compute** | ECS Fargate + ALB | Stateless API, health checks, no server management |
| **IaC** | AWS CDK (Python) | Repeatable stack; context via `scripts/cdk_ecs_context.py` |

**Hybrid model:** embeddings run on the ingest machine; only vectors and metadata live in OpenSearch. ECS tasks embed query text locally, then search AOSS.

Future path (commented in `.env.example`): classic `bedrock-runtime` for Claude + Titan embeddings when account access is available.

---

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness, deployment phase, active vector backend |
| `POST` | `/retrieve` | Vector search only — returns `chunks[]`, no LLM |
| `POST` | `/chat` | Full agent pipeline — `answer`, `citations`, `evidence`, `agent_steps`, `plan`, `trace_id` |

**Chat request:**

```json
{
  "query": "What are the main risk factors?",
  "ticker": "AAPL",
  "filing_ids": []
}
```

**Note:** `/chat` responses are verbose by design — `evidence` and `citations` repeat full filing excerpts for auditability. For demos, pipe to `json.tool` or extract `answer` only (see [Testing](#testing)).

---

## Testing

### Automated (CI)

```bash
pip install -e ".[dev]"
pytest -q
```

61 unit/API tests; mocked DB and LLM. No Docker, AWS, or Mantle required. Runs on every push via GitHub Actions (`ruff` + `pytest`).

### Deployed smoke (ALB)

Set the base URL from CloudFormation outputs or `python scripts/alb_status.py`:

```bash
export API=http://<your-alb-dns>   # no spaces around =
```

#### 1. Health

```bash
curl -s "$API/health"
```

**Expected:**

```json
{"status":"ok","phase":"5","vector_backend":"opensearch"}
```

(`phase` is `"5"` when `APP_ENV=container` on ECS; `"4"` on local uvicorn.)

#### 2. Retrieve (vector search only)

```bash
curl -s -w "\nTIME:%{time_total}s\n" -X POST "$API/retrieve" \
  -H "Content-Type: application/json" \
  -d '{"query":"risk factors","ticker":"AAPL","top_k":3}'
```

**Expected:** HTTP 200; JSON with `"query"` and `"chunks"` array of **3** AAPL items, each with `chunk_id`, `score`, and `excerpt`. Latency typically **15–20s** (cold OpenSearch + embedding).

#### 3. Chat — grounded QA

```bash
curl -s -X POST "$API/chat" \
  -H "Content-Type: application/json" \
  -d '{"query":"What are the main risk factors?","ticker":"AAPL"}' \
  | python3 -m json.tool
```

**Expected:**

| Field | Value |
|-------|-------|
| `plan.intent` | `qa` |
| `evidence` | 5 chunks with scores |
| `agent_steps` | planner → researcher (~0.7s) → writer (~3–4s Mantle) → verifier `citations ok` |
| `answer` | Bullet summary with inline `[AAPL-…-chunk_id]` citations |

**Answer only (demo-friendly):**

```bash
curl -s -X POST "$API/chat" \
  -H "Content-Type: application/json" \
  -d '{"query":"What are the main risk factors?","ticker":"AAPL"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['answer'])"
```

#### 4. Chat — refuse investment advice

```bash
curl -s -X POST "$API/chat" \
  -H "Content-Type: application/json" \
  -d '{"query":"Should I buy AAPL?"}' \
  | python3 -m json.tool
```

**Expected:**

| Field | Value |
|-------|-------|
| `plan.intent` | `refuse` |
| `evidence` / `citations` | `[]` |
| `answer` | Starts with *"I cannot provide investment or trading advice…"* |
| `agent_steps[-1].detail` | `refuse intent — fixed answer, citation check skipped` |

### Sample test matrix

Canonical cases live in **`tests/golden_queries.yaml`**. Run all against ALB:

```bash
python scripts/alb_e2e.py
python scripts/alb_e2e.py --base-url "$API"
```

| ID | Query | Intent | Pass criteria |
|----|-------|--------|---------------|
| `risk-factors` | What are the main risk factors? | `qa` | ≥1 evidence; answer mentions “risk”; verifier pass |
| `revenue-discussion` | What was total net sales or revenue discussion? | `qa` | ≥1 evidence; grounded (may decline if excerpt lacks figure) |
| `business-overview` | Who is the company or what is the business overview? | `qa` | ≥1 evidence; answer references Apple / products / services |
| `investment-advice` | Should I buy AAPL? | `refuse` | 0 evidence; fixed refusal prefix |

### Local E2E

Requires Docker (pgvector), ingest, and Mantle in `.env`:

```bash
docker compose up -d db
python scripts/ingest_edgar.py --ticker AAPL
uvicorn app.main:app --reload --port 8001
```

Replace `$API` with `http://127.0.0.1:8001`. Full checklist: **[docs/NOTICE.md](docs/NOTICE.md)**.

---

## Quick start (local dev)

```bash
git clone https://github.com/Kellyxinyuwu/sec-filings-agentic-rag-aws.git
cd sec-filings-agentic-rag-aws
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # SEC identity, DATABASE_URL, MANTLE_*
docker compose up -d db
python scripts/ingest_edgar.py --ticker AAPL
uvicorn app.main:app --reload --port 8001
curl -s http://127.0.0.1:8001/health
```

**Cloud data plane (Phase 4):** configure `S3_*`, `OPENSEARCH_*`, then:

```bash
python scripts/ingest_edgar.py --ticker AAPL --skip-download --index-opensearch --upload-s3
export VECTOR_BACKEND=opensearch
```

---

## Deploy to AWS

Ingest and indexing run on your machine; the API runs on ECS.

```bash
eval "$(python scripts/cdk_env.py)"
python scripts/ecr_push.py --build          # Mac: linux/amd64
python scripts/secrets_sync_mantle.py
python scripts/cdk_ecs_context.py --deploy --bootstrap   # first time only
python scripts/aoss_grant_task_role.py
python scripts/alb_status.py --curl
python scripts/alb_e2e.py
```

**Teardown** (stop idle billing): `python scripts/cdk_teardown.py --destroy` plus delete the OpenSearch Serverless collection in console. See **infra/README.md** § cost.

---

## Repository layout

```
app/
  api.py, orchestrator.py, tools.py
  agents/          planner, researcher, writer, verifier
  store_opensearch.py, s3_storage.py, llm_mantle.py
scripts/
  ingest_edgar.py, ecr_push.py, cdk_ecs_context.py
  alb_e2e.py, alb_status.py, ecs_logs_tail.py, cdk_teardown.py
infra/             CDK — SecRagStack (ECS, ALB, ECR, IAM, logs)
tests/             pytest + golden_queries.yaml
docker-compose.yml pgvector on host port 5433
```

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.11+ | CI uses 3.11 |
| Docker | Local pgvector; image build for ECR |
| Node.js 18+ | CDK synth/deploy |
| AWS credentials | Profile or `~/.aws/credentials` |
| Bedrock Mantle API key | Generation for `/chat` |
| SEC EDGAR identity | `SEC_COMPANY_NAME` / `SEC_COMPANY_EMAIL` for downloads |

---

## Compliance

SEC filings are public data. Downloads must use a descriptive User-Agent with contact information per [SEC developer guidance](https://www.sec.gov/os/webmaster-faq#developers). This project is for portfolio / educational use; outputs are not financial advice.

---

## License

Portfolio / educational project. See repository for usage terms.
