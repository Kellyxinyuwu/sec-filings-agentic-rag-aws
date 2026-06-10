# Architecture

## High level

```
Client → FastAPI → Orchestrator
                      ├─ Planner
                      ├─ Researcher (tools: retrieve, get_section, …)
                      ├─ Writer (Bedrock, grounded on evidence)
                      └─ Verifier (citations, fail-closed)

Tools → OpenSearch (vectors) + S3 (documents) + Bedrock (LLM / embeddings)
```

## Agents (target)

| Agent | Role |
|-------|------|
| Planner | Intent, retrieval need, ticker / filing filters |
| Researcher | Fetch evidence via tools only |
| Writer | Answer with mandatory citations |
| Verifier | Reject unsupported claims; one retry max |

## Deployment (target)

- **Compute:** ECS Fargate
- **IaC:** AWS CDK (Python) under `infra/` (added in Phase 5)

## Code layout (`app/`)

| File / folder (later) | Role |
|-----------------------|------|
| `main.py` | FastAPI entry |
| `api.py` | HTTP routes |
| `schemas.py` | Request/response models |
| `config.py` | Settings from `.env` |
| `orchestrator.py` | Agent loop (Phase 3) |
| `agents/` | Planner, Researcher, Writer, Verifier (Phase 3) |
| `tools.py` or `tools/` | RAG tools: retrieve, get_section (Phase 1–2) |
| `aws.py` or `aws/` | Bedrock, S3, OpenSearch clients (Phase 2–4) |
- **Observability:** CloudWatch logs + metrics

## Model stack (current capstone path)

| Phase | Retrieval (embed) | Generation (LLM) |
|-------|-------------------|------------------|
| 1 | Local `all-MiniLM-L6-v2` + pgvector | — |
| 2 | Local (unchanged) | Bedrock **Mantle** (Qwen / MiniMax) |
| 4+ | Optional Titan embed on `bedrock-runtime` | Classic Bedrock when account allows |

Model stack & prod path (local vs AWS, enterprise controls): **[MODEL_AND_PRODUCTION_DECISIONS.md](./MODEL_AND_PRODUCTION_DECISIONS.md)**.

Diagram and deployment detail will be expanded in Phase 3–5.
