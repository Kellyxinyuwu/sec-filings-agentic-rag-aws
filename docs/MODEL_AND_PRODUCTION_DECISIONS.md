# Model stack & enterprise production — capstone decision log

> File: `docs/MODEL_AND_PRODUCTION_DECISIONS.md` (renamed from `MODEL_STACK_TRADEOFFS.md` when scope grew to enterprise prod + internship mapping).

Personal decision log for this capstone (Kelly Wu, 2026-06).

**What this doc covers:**

| Topic | Question it answers |
|-------|---------------------|
| **Model stack** | Why Phase 1 embed is local, Phase 2 LLM is AWS Mantle |
| **Local vs hybrid vs AWS** | Is this project “fully local”? How does it compare to `SEC-10-K-RAG`? |
| **Enterprise production** | Model allow-list, IAM, VPC, audit logs, budgets, compliance |
| **Capstone vs internship** | What AWS/prod concepts you can touch in this repo vs on the job |

Related: [BEDROCK_MANTLE_VS_RUNTIME.md](./BEDROCK_MANTLE_VS_RUNTIME.md), [AWS_ACCOUNT_NOTES.md](./AWS_ACCOUNT_NOTES.md), [PHASE_1.md](./PHASE_1.md).

**Sections in this doc:**

| Section | Topic |
|---------|--------|
| [The choice in one table](#the-choice-in-one-table) | Phase 1 local vs Phase 2 AWS |
| [Quick reference (Q&A)](#quick-reference-qa) | Enterprise local models, prod controls, what capstone covers |
| [Do real enterprises use local models?](#do-real-enterprises-use-local-models) | Dev vs prod vs air-gap |
| [Enterprise production controls](#enterprise-production-controls-deep-dive) | Allow-list, IAM, VPC, logs, budget, compliance |
| [Capstone vs internship](#what-this-project-lets-you-touch-vs-what-needs-internship) | Honest scope |
| [Three stacks](#three-stacks-side-by-side) | Old project vs capstone vs enterprise target |

---

## The choice in one table

| Layer | Phase | What we use | Where it runs |
|-------|-------|-------------|---------------|
| **Embedding (retrieval)** | 1 | `sentence-transformers` → `all-MiniLM-L6-v2` | Local (laptop) |
| **Vector store** | 1 | PostgreSQL + pgvector (Docker) | Local |
| **LLM (generation)** | 2 | Bedrock **Mantle** (e.g. Qwen3 / MiniMax) | AWS `us-east-1` |
| **Embedding (future)** | 4+ optional | Amazon Titan / Nova embed via `bedrock-runtime` | AWS (when account allows) |
| **Vector store (future)** | 4+ | OpenSearch Serverless | AWS |

Phase 1 = **real RAG retrieval** without waiting on AWS corporate approval.  
Phase 2 = **first AWS integration** on the path that already works on this account.

**This is hybrid, not “fully local” and not “pure AWS” yet:** Phase 1 = all inference on laptop; Phase 2+ = local retrieval + cloud generation; Phase 4–5 = move embed/index/compute toward AWS prod shape.

---

## Quick reference (Q&A)

Condensed answers to common questions (expanded in sections below).

### Do enterprises avoid local models entirely?

**No — but they restrict where local is allowed.**

| Environment | Local LLM / local embed? |
|-------------|--------------------------|
| Dev laptop, fast iteration | ✅ Common (MiniLM, Ollama) |
| Production, regulated (bank) | ❌ Usually **approved cloud** only |
| Data cannot leave building | ✅ **Required** on-prem / private cluster |

Enterprises block **unmanaged** local LLMs in prod (no audit, no model approval). Your Phase 1 local MiniLM = **dev-style**, not Jefferies production — **normal and expected**.

### Six production controls in one line each

| Control | One sentence | What it does in prod |
|---------|--------------|----------------------|
| **Model allow-list** | Only approved `model_id`s may be called | IAM / config / gateway lock down Bedrock models |
| **IAM** | Services and people get **least privilege** roles | ECS task role calls Bedrock; no admin keys on app servers |
| **VPC** | Apps run in **private subnets** | Traffic to Bedrock via VPC endpoint, not public internet |
| **Audit logs** | Every model call is **traceable** | App `trace_id` + CloudWatch + Bedrock logs → S3 / SIEM |
| **Budget / quotas** | **Spend and rate** are capped | AWS Budgets, Bedrock TPM limits, team tags |
| **Compliance** | **What data** and **what answers** are allowed | Public data only, citations, refuse advice, human review |

Real firms stack **all six** around the model — not just “we use Bedrock.”

### What this capstone lets you practice (by phase)

| Phase | Mostly local or AWS? | Enterprise-shaped skills |
|-------|----------------------|---------------------------|
| **0** | AWS account setup | Budget + alerts ✅ ([AWS_SETUP.md](./AWS_SETUP.md)) |
| **1** | **Fully local** retrieval | pgvector, embed, ingest, `EvidenceChunk` contracts |
| **2** | **Hybrid** | Mantle cloud LLM, API keys, region, provider abstraction (`llm.py`) |
| **3** | Hybrid | Agents, verifier, citations, `QueryIntent.REFUSE`, golden eval |
| **4–5** | **More AWS** | S3, OpenSearch, ECS, IAM task role, VPC, CloudWatch |

### Does “having AWS in the project” = production experience?

**Partially — be precise in interviews:**

| You **do** get | You **do not** get (typical capstone) |
|----------------|--------------------------------------|
| Real cloud inference (Mantle) | Org-wide SSO, SCP, permission boundaries |
| Cost budget discipline | SIEM (Splunk), legal hold, 7-year archive |
| App-level audit (`trace_id`, agent steps) | Full Bedrock invocation logging pipeline (needs corp account) |
| Compliance-**shaped** RAG (cite, refuse, public 10-K only) | Formal model risk committee sign-off |
| Phase 5 **taste** of IAM role + VPC + ECS | Bank-grade network zoning operated by platform team |

**Enough for interviews** if you can name each layer and say what you built vs what you’d do on corporate AWS.

### Enterprise ≠ “Bedrock only”

Large shops mix **governance + network + identity + logging + cost + business rules**. Common stacks:

- **AWS-heavy:** Titan embed + OpenSearch + Bedrock Claude + IAM/VPC/CloudWatch  
- **Azure-heavy:** Azure OpenAI + AI Search  
- **Hybrid vendor:** Pinecone + OpenAI API (still with internal approval)

Your [ARCHITECTURE.md](./ARCHITECTURE.md) target is **AWS-native RAG** — a credible **north star** for a firm already on AWS. Internship is where you learn **how that firm actually implements** allow-lists and compliance process.

---

## Why Phase 1 retrieval is local

### 1. Mantle does not provide embeddings

Bedrock has two main inference paths:

| Endpoint | Typical use | Embedding models? |
|----------|-------------|-------------------|
| `bedrock-mantle` | Chat / Responses / Messages (Qwen, MiniMax, …) | **No** |
| `bedrock-runtime` | InvokeModel, Converse, Titan embed, … | **Yes** (Titan, Nova embed, Cohere embed) |

Mantle models are **chat / completion** models. They are not a replacement for `sentence-transformers` or Titan Embeddings. Using a chat model to fake “embeddings” would be slow, expensive, and unreliable for vector search.

### 2. Classic `bedrock-runtime` is blocked on this personal account

AWS Support (case ~178045111500715, 2026-06) stated that **classic Bedrock access requires corporate verification**; individual developers are not eligible without business documentation.

That blocks (for now):

- Bedrock Playground / classic Converse
- **Titan Text Embeddings** and other embed APIs on `bedrock-runtime`
- Claude on classic runtime

So “use AWS for Phase 1 embed” is not a practical option on this account **today**, even though it is the long-term target in [ARCHITECTURE.md](./ARCHITECTURE.md).

### 3. Local embed is proven and cheap for ingest

Prior project `SEC-10-K-RAG` already used the same pattern: **local MiniLM + pgvector + local LLM**. For Phase 1 we reuse the ingest/chunk/embed path and focus new learning on:

- Agentic API contracts (`EvidenceChunk`, future orchestrator)
- AWS-ready abstractions (`config`, later `llm.py`, optional `embeddings.py`)
- A portfolio narrative that separates **retrieval** from **generation**

Ingesting one 10-K produces **hundreds to thousands** of chunks. Local batch embedding is:

- **Free** (no per-token API cost)
- **Fast enough** for a single-ticker demo
- **Offline-friendly** while building the pipeline

### 4. Phase 1 goal does not require cloud LLM

Phase 1 acceptance = download AAPL 10-K → index → `POST /retrieve` returns real evidence.  
No answer generation yet. Blocking Phase 1 on AWS embed would delay the only deliverable that proves the data plane works.

---

## Why Phase 2 generation uses AWS (Mantle)

### 1. Mantle works on this account today

Console evaluation confirmed **Qwen3** and **MiniMax** on `bedrock-mantle` in `us-east-1`. That is enough to:

- Replace mock `/chat` answers with a real model
- Enforce “answer only from evidence” prompts
- Show **AWS in the stack** for interviews (Jefferies infra / platform angle)

### 2. Generation is the right place to “try AWS” first

| Concern | Local embed (Phase 1) | Mantle LLM (Phase 2) |
|---------|------------------------|----------------------|
| Account gate | N/A | Mantle ✅; classic runtime ❌ |
| Cost during dev | $0 | Low for demo traffic |
| Interview story | “Sensible default under constraints” | “Integrated cloud inference with provider abstraction” |

Retrieval quality for a capstone demo is acceptable with MiniLM on financial text; **generation** is where cloud models and AWS IAM/API keys/observability matter more for the story.

### 3. Thin abstraction keeps migration easy

Planned layout (Phase 2):

```
app/llm.py          # chat(system, user) -> str
app/llm_mantle.py   # OpenAI-compatible → bedrock-mantle
app/llm_bedrock.py  # boto3 converse → bedrock-runtime (when approved)
```

RAG tools (`retrieve`, citations, verifier) stay **unchanged** when swapping Mantle → classic Claude later.

Optional later:

```
app/embeddings.py       # embed_texts / embed_query
app/embed_local.py      # sentence-transformers (Phase 1)
app/embed_bedrock.py    # Titan (corporate account / runtime approved)
```

Switching embed backend **requires re-ingest** (e.g. MiniLM 384-dim vs Titan 1024-dim).

---

## Tradeoffs we accept

| Decision | Upside | Downside | Mitigation |
|----------|--------|----------|------------|
| Local MiniLM embed | Works now; $0; same as prior project | Not “full AWS data plane” in Phase 1 | Phase 4 OpenSearch + Titan; document in README |
| Mantle for LLM only | AWS on personal account; minimal code change (OpenAI SDK) | Not the “standard” `bedrock-runtime` Converse path | `llm_bedrock.py` when Support / corp account allows |
| pgvector on Docker | Simple debug; fast iteration | Not production topology | Phase 4–5 per [ARCHITECTURE.md](./ARCHITECTURE.md) |
| No Bedrock embed in Phase 1 | Unblocked timeline | Two vendors in stack (HF local + AWS Mantle) | Single `store.py` / future `embeddings.py` interface |

---

## What we are not doing (and why)

| Alternative | Why not now |
|-------------|-------------|
| Mantle Qwen for embeddings | Wrong API; not designed for vector search |
| Wait for corporate Bedrock before Phase 1 | Unknown timeline; blocks capstone |
| Ollama for Phase 2 instead of Mantle | Valid fallback, but user wants **AWS** experience; Mantle already works |
| OpenSearch in Phase 1 | Scope; 7-day priority is ingest + retrieve + agent skeleton |

---

## Future path when AWS embed unlocks

Typical order:

1. **Corporate AWS** (e.g. internship) or personal account approved for `bedrock-runtime`
2. Enable **Titan Text Embeddings v2** (or Nova embed) in `us-east-1`
3. Implement `app/embed_bedrock.py`; set `EMBEDDING_PROVIDER=bedrock` in `.env`
4. **Re-run ingest** (dimension + model change)
5. Phase 4: move vectors to OpenSearch; keep same tool interface

Until then, Phase 1 local retrieval + Phase 2 Mantle generation is an intentional, documented split—not a gap we forgot to fix.

---

## Is this project “fully local” or “partially AWS”?

**Short answer:** It is **not** fully local end-to-end, and it is **not** pure AWS yet either. It is a **deliberate hybrid** that changes by phase.

| Phase | Local | AWS / cloud | “Fully local”? |
|-------|-------|-------------|----------------|
| **1** (now) | Embed (MiniLM), pgvector (Docker), FastAPI, SEC download | None for inference | **Yes** — retrieval only, no LLM |
| **2** (planned) | Embed + pgvector unchanged | **Mantle** for answer generation | **No** — hybrid |
| **4–5** (target) | Optional dev fallback | Titan embed, OpenSearch, ECS, classic Bedrock | **Mostly AWS** for prod path |

So:

- **Phase 1** = you can develop on a laptop with **zero** AWS inference calls (only your AWS account exists for future work / billing setup).
- **Full capstone (Phase 2+)** = **partial AWS**: cloud **generation**, local (or later cloud) **retrieval**.
- **“Pure AWS”** in the sense of Bedrock embed + OpenSearch + Fargate = **Phase 4–5 goal**, not what we ship on day 3 of Phase 1.

This is a common pattern when a personal account cannot open all Bedrock APIs: **build the RAG data plane locally, plug cloud LLM where the account allows.**

---

## Comparison: this capstone vs old project `SEC-10-K-RAG`

The prior repo (`SEC-10-K-RAG`) was **essentially 100% local** for model inference:

| Layer | Old project (`SEC-10-K-RAG`) | This capstone (`sec-filings-agentic-rag-aws`) |
|-------|------------------------------|-----------------------------------------------|
| **Embedding** | Local `sentence-transformers` (`all-MiniLM-L6-v2`) | Same — local MiniLM |
| **Vector DB** | pgvector in Docker (port 5433) | Same pattern |
| **LLM (answers)** | **Ollama** (`llama3.2`) on localhost | **Bedrock Mantle** (Qwen / MiniMax) in Phase 2 |
| **Agents** | Single RAG Q&A path | Multi-agent orchestrator (Phase 3) |
| **Cloud** | None required | AWS for generation; future S3/OpenSearch/ECS |
| **SEC download** | `sec-edgar-downloader` | Same |

**If you wanted “pure local” like the old project:** keep Phase 1 as-is and implement Phase 2 with **`app/llm_ollama.py`** instead of Mantle — same architecture, different provider. We chose Mantle for this repo because the goal is **AWS + infra interview story**, not because local LLM failed.

**What stayed the same on purpose:** ingest, chunk size (400/100 tokens), MiniLM, pgvector — so learning transfers and Phase 1 is not reinvented.

**What’s new:** agent contracts, citation/verifier, AWS abstraction, path to enterprise OpenSearch/Bedrock.

---

## Personal laptop + personal AWS — can you use Bedrock?

Developing on your **own computer** is fine. The blocker is usually **account type and product line**, not “home vs office network.”

### What we see in practice (2025–2026)

| Scenario | Classic Bedrock (`bedrock-runtime`, Claude, Titan embed) | Bedrock Mantle (Qwen, MiniMax, …) |
|----------|----------------------------------------------------------|-----------------------------------|
| New **personal** AWS account | Often **blocked** or needs corporate verification | **Sometimes works** (this project) |
| **Student** / credits account | Mixed; same corporate gate reported often | Mixed |
| **Company** AWS (bank, broker-dealer) | Enabled via **procurement + security + model allow-lists** | May or may not be enabled separately |
| **IAM user** vs Root | Same account-level gates | Same |

So: **personal account → do not assume full Bedrock.** Plan for **local retrieval + Mantle or external API for generation**, or wait for a corporate account.

### What people use instead of Ollama (and instead of blocked Bedrock)

When Bedrock classic is unavailable, common substitutes for **generation** (not embedding):

| Option | Type | Notes |
|--------|------|-------|
| **Ollama** | Local LLM | Old project default; free; `llama3.2`, `qwen2.5`, etc. |
| **LM Studio / llama.cpp** | Local LLM | GUI or CLI; GGUF models |
| **OpenAI API** | Cloud | GPT-4o; most RAG tutorials |
| **Anthropic API** | Cloud | Claude direct (not via AWS) |
| **Google Gemini API** | Cloud | Free tier often used by students |
| **Groq / Together / Fireworks** | Cloud | Hosted open weights; fast inference |
| **Hugging Face Inference API** | Cloud | Pairs with local HF embed workflow |
| **Bedrock Mantle** | AWS cloud | This capstone’s Phase 2 choice |
| **Azure OpenAI** | Cloud | Common in enterprises already on Azure |

For **embedding / retrieval**, local **sentence-transformers** (or **bge**, **e5**) remains extremely common in side projects and even in prod dev environments — it is not a “lesser” choice.

**Typical student / indie stack:** local MiniLM + Chroma/pgvector + **Gemini or OpenAI API** for answers — no AWS at all.

**This capstone stack:** local MiniLM + pgvector + **Mantle** for answers — **partial AWS**, optimized for “I need AWS on the resume” under personal-account limits.

---

## How do real enterprises use models? Is it “pure AWS”?

**Usually not one vendor for everything.** Even AWS-heavy shops mix components. Finance and regulated industries add **governance**, not just “pick Bedrock.”

### Common enterprise patterns

| Pattern | Who | Retrieval | Generation | Why |
|---------|-----|-----------|------------|-----|
| **AWS-native RAG** | Cloud-first teams | Bedrock Titan embed + **OpenSearch Serverless** | Bedrock Claude / Nova via `bedrock-runtime` | Single cloud bill, IAM, VPC endpoints, audit logs |
| **Azure-native** | Microsoft shops | Azure AI Search + Azure OpenAI embeddings | GPT-4 via Azure OpenAI | Existing EA with Microsoft |
| **Best-of-breed APIs** | Many startups / product teams | Pinecone / Weaviate + OpenAI embed | OpenAI or Anthropic API | Speed to market |
| **Hybrid** | Large banks, Jefferies-scale infra | Internal vector store + **approved** model route | Mix: Bedrock **or** vendor API per use case | Risk, legal, and model approval committees |
| **On-prem / air-gap** | Defense, some banking | Local embed + internal index | Self-hosted Llama / vLLM | Data cannot leave network |

### What “enterprise” adds beyond model choice

Enterprises rarely stop at “call Bedrock.” Typical layers:

1. **Model allow-list** — only approved model IDs (e.g. Claude Haiku prod, Opus forbidden).
2. **IAM + VPC** — no public API keys on laptops; roles, privateLink, secrets manager.
3. **Logging & retention** — CloudWatch, prompt/response audit, PII redaction.
4. **Cost controls** — budgets, quotas, per-team chargeback.
5. **Human review** — for high-risk answers (investment advice, client-facing).
6. **Evaluation** — golden questions, regression when models change.

So the **target architecture** in [ARCHITECTURE.md](./ARCHITECTURE.md) (OpenSearch + S3 + Bedrock + ECS) is an **enterprise-shaped** north star — not what most individuals run on day one.

### Jefferies / sell-side infra angle (interview-relevant)

You will often hear:

- **Research or internal tools** — grounded Q&A on filings, transcripts, CRM data; citations matter.
- **Not** “let traders chat with GPT freely” — guardrails, entitlements, data boundaries.
- **Platform team** owns: ingestion pipelines, vector indexes, API gateways, **which** model endpoint apps may call.
- **AWS Bedrock** is popular when the firm is already on AWS — but **Anthropic/OpenAI enterprise contracts** still exist in parallel.

Your capstone narrative fits: *“I built the retrieval and agent loop; generation plugs into Mantle now and bedrock-runtime Converse in prod.”*

---

## Do real enterprises use local models?

**Not never — but prod paths for customer-facing or regulated workloads rarely rely on “Ollama on a laptop.”**

| Context | Local models? | Examples |
|---------|---------------|----------|
| **Developer laptop** | **Often yes** | Local MiniLM for fast ingest tests; Ollama to debug prompts before cloud deploy |
| **CI / unit tests** | **Yes** | Mock LLM; no real inference |
| **Staging (small teams)** | Sometimes | Cost saving; not representative of prod security |
| **Production (bank, broker-dealer)** | **Usually no** for LLM | Approved cloud endpoints (Bedrock, Azure OpenAI) with contracts and logging |
| **Air-gapped / on-prem** | **Yes — required** | Self-hosted Llama on internal GPU cluster; no data leaves the building |
| **Embedding in prod** | **Mostly cloud** at AWS shops | Titan / Cohere embed on Bedrock; local embed more common in **dev** and indie projects |

**Takeaway:** Enterprises **discourage** “each team runs their own unchecked local LLM” for **production**. They **allow** local models for **development velocity**. Your Phase 1 local MiniLM mirrors **dev/staging**, not what Jefferies prod would run — and that is normal.

---

## Enterprise production controls (deep dive)

These are the layers platform / infra teams add **around** the model. You do not get all of them from “calling Mantle once” — but you **can** touch slices in this project and more on internship.

### 1. Model allow-list (model governance)

**What it is:** A fixed set of `model_id` values that applications may call. Security and legal approve the list; apps cannot invoke arbitrary models.

| Where it lives | Example |
|----------------|---------|
| IAM policy | `bedrock:InvokeModel` only on `arn:...:foundation-model/anthropic.claude-3-5-haiku-*` |
| SCP (org level) | Deny all Bedrock except approved regions/models |
| App config | `BEDROCK_CHAT_MODEL_ID` from Parameter Store — not hardcoded in repo |
| Gateway / proxy | Internal API strips requests to non-approved model IDs |

**Why:** Prevent engineers from sending client data to Opus “just testing,” or to unaudited open-weight models.

**In this project today:** `.env.example` comments for `BEDROCK_CHAT_MODEL_ID` — **concept only**. Phase 2 Mantle: you pick Qwen/MiniMax manually; no central allow-list.

**You can practice:** Document approved models in README; read-only env var from config; **interview talk** about IAM resource ARNs per model.

**Full allow-list:** Corporate AWS org + platform team — **internship**.

---

### 2. IAM (Identity and Access Management)

**What it is:** Who (user / role / service) can do what on which AWS resource.

| Pattern | Prod meaning |
|---------|--------------|
| **No long-lived keys on laptops** | Developers assume **IAM roles** (SSO) |
| **ECS task role** | Fargate task may call Bedrock + read S3; **no** blanket admin |
| **Least privilege** | App role: `bedrock:InvokeModel` + `s3:GetObject` on one bucket — not `*` |
| **Separate roles** | Ingest job role ≠ API role ≠ human admin |

**In this project today:**

| Done / planned | Phase |
|--------------|-------|
| Personal root / IAM user for console | Phase 0 |
| API key for Mantle (Bedrock API keys) | Phase 2 |
| **ECS task IAM role** in CDK | Phase 5 |
| **No keys in git** — `.env` gitignored | Phase 0 |

**You can practice:** Phase 5 CDK — task role with minimal Bedrock + S3 policy; explain in interview why the API container should not use your personal user credentials.

**Corporate SSO, permission boundaries, cross-account roles:** **internship**.

---

### 3. VPC (network isolation)

**What it is:** Private network in AWS. Prod services often have **no public IP**; they reach Bedrock via **VPC endpoint** (PrivateLink) so traffic stays on AWS backbone.

```
[User/VPN] → ALB (public) → ECS tasks (private subnets)
                                ↓ VPC endpoint
                           bedrock-runtime (no internet egress)
```

**Why:** Reduce attack surface; satisfy “data path must not traverse public internet” policies.

**In this project today:** Phase 1–2 run on **localhost** → Docker pgvector → Mantle over **public HTTPS**. No VPC yet — normal for local dev.

**You can practice:** Phase 5 CDK — VPC with public + private subnets, ECS in private, NAT or endpoints; diagram in ARCHITECTURE.

**Full PrivateLink + network firewall rules:** Often **platform team** owns — you **design** and **document** in capstone; deep ops on internship.

---

### 4. Audit logging & observability

**What it is:** Record **who** called **which model**, with **what** inputs/outputs (often redacted), for compliance and incident response.

| Layer | Tool | What gets logged |
|-------|------|------------------|
| **Application** | structlog + `trace_id` | Query, ticker, agent steps, latency (this project Phase 0+) |
| **Bedrock** | **Model invocation logging** → S3 / CloudWatch | Prompts, completions (enterprise config) |
| **API** | ALB access logs, API Gateway | IP, route, status |
| **Infra** | CloudWatch metrics/alarms | Error rate, latency, throttling |

**Compliance angle:** FINRA/SEC/internal policy may require **retention** (e.g. 7 years for certain comms) and **no PII** in logs without masking.

**In this project today:**

| Item | Status |
|------|--------|
| `structlog`, `trace_id` in `/chat` | ✅ Phase 0 |
| `agent_steps` with latency | ✅ Phase 0 mock → real in Phase 3 |
| CloudWatch log group for ECS | 📋 Phase 5 |
| Bedrock invocation logging to S3 | 📋 Mention in docs; full setup needs corp account + bucket policy |

**You can practice:** JSON logs, trace IDs, log **retrieval** events (chunk_ids, scores) without logging full 10-K text; Phase 5 ship logs to CloudWatch.

**Enterprise log archive, SIEM (Splunk), legal hold:** **internship**.

---

### 5. Budgets, quotas, and cost controls

**What it is:** Prevent surprise bills and allocate spend per team.

| Control | Purpose |
|---------|---------|
| **AWS Budgets** | Email at 80%/100% of $X/month |
| **Bedrock service quotas** | Max TPM/RPM per model |
| **Per-env tags** | `Project=sec-rag`, `Env=dev` for cost allocation |
| **Alerts** | CloudWatch alarm on anomaly |

**In this project today:** Budget **`sec-rag-monthly` $20** + alerts — ✅ you already did this ([AWS_SETUP.md](./AWS_SETUP.md)).

**You can practice:** Tag CDK resources; document estimated cost per 1k queries; rate-limit `/chat` in API (optional Phase 5).

**Chargeback to business lines:** Enterprise finance process — **awareness** from budget exercise is enough for capstone.

---

### 6. Compliance (governance, not one checkbox)

**What it is:** Rules for **what data** can enter **which model** and **what answers** may go to users.

| Theme | Enterprise example | This project analogue |
|-------|-------------------|------------------------|
| **Data classification** | Public 10-K OK; client portfolio **not** in prompt | Only SEC **public** filings — safe for demo |
| **No investment advice** | Disclaimers; refuse intent | `QueryIntent.REFUSE` in schemas (Phase 3) |
| **Grounded answers** | Must cite source | `EvidenceChunk`, Verifier agent |
| **Human review** | Analyst approves draft | Out of scope; mention in interview |
| **Vendor DPAs** | Contract with Anthropic/AWS | N/A on personal account |
| **Model risk** | Eval suite before model swap | `golden_queries.yaml` (Phase 3) |

**You can practice:** Refuse path, citations-only answers, eval harness — **these are compliance-shaped engineering**, not just ML.

---

## What this project lets you touch vs what needs internship

| Enterprise control | Touch in capstone? | How |
|--------------------|-------------------|-----|
| Model allow-list | **Concept + partial** | Config-driven `MODEL_ID`; IAM policy in CDK example |
| IAM least privilege | **Partial** | Phase 5 ECS task role |
| VPC / private subnets | **Partial** | Phase 5 CDK skeleton |
| App audit logs (`trace_id`) | **Yes** | Phase 0–3 |
| CloudWatch | **Partial** | Phase 5 |
| Bedrock invocation logging | **Read/docs** | Enable when runtime access exists |
| AWS Budgets | **Yes** | Already set up |
| Compliance-shaped RAG | **Yes** | Citations, verifier, public data only |
| SSO, SCP, SIEM, legal review | **No** | Learn on job; speak to them in interviews |

**Honest answer to “does AWS in my project mean I’ll experience prod?”**

- **Phase 2 Mantle** → real **cloud inference**, API keys, region, latency, quotas — **yes, valuable**.
- **Phase 5 CDK/ECS** → **taste** of how prod is wired; not bank-grade hardening.
- **Full production** → **team + org policies + months of operational learning** — internship and first job.

That is enough for interviews if you can **name** each layer and say **what you built vs what you’d do next on corp AWS**.

### Learning path: capstone → internship

```
Capstone (this repo)          Internship / first job
─────────────────────         ──────────────────────
Local embed + pgvector   →    Titan embed + OpenSearch (maybe)
Mantle LLM               →    bedrock-runtime Claude + allow-list
trace_id, citations      →    + Bedrock invocation logs, SIEM
Budget $20               →    Team chargeback, quotas
CDK ECS sketch (Ph 5)    →    VPC endpoints, SSO roles, change control
Public 10-K only         →    Data classification, legal, DPAs
```

You are not behind if you have not operated SIEM or SCPs — you are **prepared** if you know they exist and how your code would fit under them.

---

## Three stacks side-by-side

| | Old `SEC-10-K-RAG` | This capstone (Phase 2) | Enterprise target (Phase 4–5) |
|--|-------------------|-------------------------|-------------------------------|
| **Embed** | Local MiniLM | Local MiniLM | Bedrock Titan (typical) |
| **Index** | pgvector Docker | pgvector Docker | OpenSearch Serverless |
| **LLM** | Ollama local | Mantle AWS | Bedrock Claude / Nova |
| **Compute** | uvicorn on laptop | uvicorn on laptop → ECS later | ECS Fargate |
| **AWS required?** | No | Partial (inference) | Yes |
| **Offline dev?** | Yes | Phase 1 yes; Phase 2 needs network | Staging in VPC |

---

## FAQ

### Q: If I only cared about learning RAG, should I have stayed on Ollama?

**Yes, that would be enough.** The old project already proved ingest → retrieve → answer. This repo adds **agents + AWS path** for internship positioning.

### Q: Is hybrid “worse” than pure local or pure AWS?

**No — it is a normal stepping stone.** Pure local is fastest to build; pure AWS is the production target; hybrid matches **real account constraints**.

### Q: Will Jefferies use exactly Bedrock + OpenSearch?

**Maybe, maybe not** — firms differ. The transferable skills are: RAG design, citations, IAM, observability, provider abstraction — not memorizing one model ID.

### Q: Can I switch this repo back to full local (Ollama) for Phase 2?

**Yes.** Implement `app/llm_ollama.py`, set `LLM_PROVIDER=ollama` in `.env`. Retrieval unchanged. Documented as a valid fallback in [BEDROCK_MANTLE_VS_RUNTIME.md](./BEDROCK_MANTLE_VS_RUNTIME.md).

### Q: Will this project alone teach me enterprise IAM/VPC/compliance?

**Partially.** You get budgets, cloud LLM, logging patterns, citation compliance, and (Phase 5) IAM roles + VPC-shaped deploy. You will **not** get org-wide SCPs, SSO, or SIEM — expect those on a platform team. Use this repo to **speak the vocabulary** and show **one vertical slice**; use internship to see **how a firm applies** it.

### Q: Do banks never use local models?

They use them **in controlled places** (dev, research sandboxes, on-prem clusters). They rarely use **unmanaged** local LLMs for **regulated production** paths without the same logging and approval as cloud.

---

## How to explain this in an interview

**30 seconds:**

> “Phase 1 proves grounded retrieval: SEC 10-K into pgvector with local embeddings because Titan embed sits on classic Bedrock runtime, which my personal account couldn’t open without corporate verification. Phase 2 adds generation on Bedrock Mantle, which was available on the same account. I kept `llm` and embedding behind small provider modules so we can switch to Titan embed and Claude on `bedrock-runtime` once on a corporate AWS account—without rewriting the agent or citation flow.”

**If asked “local vs AWS?”:**

> “Phase 1 is fully local for retrieval — same as my earlier SEC-10-K-RAG project with MiniLM and pgvector. Phase 2 is hybrid: local index, cloud LLM on Mantle. Production at a bank would likely move embed and index to Bedrock Titan and OpenSearch with IAM and logging — that’s Phase 4–5 in my roadmap, not what a personal account could unblock in week one.”

**If asked “enterprise prod controls?”:**

> “Production adds model allow-lists, IAM least privilege, VPC private connectivity, audit logging, budgets, and compliance rules around what data can hit which model. My capstone practices budgets, structured logs, grounded citations, and cloud inference on Mantle; Phase 5 adds ECS with a task IAM role and VPC-shaped deploy. Org-wide SSO and SIEM I’d expect to learn on the platform team — but I know how my app would plug into those layers.”

---

## References

- [BEDROCK_MANTLE_VS_RUNTIME.md](./BEDROCK_MANTLE_VS_RUNTIME.md) — two endpoints, what works on this account
- [AWS_ACCOUNT_NOTES.md](./AWS_ACCOUNT_NOTES.md) — Root vs IAM; account-level gates
- [PHASE_1.md](./PHASE_1.md) — Step 4 `store.py`; why `all-MiniLM-L6-v2`
- AWS: [Endpoints supported by Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/endpoints.html)
- Prior art: `SEC-10-K-RAG` (local pgvector + Ollama)
