# AWS setup

> Phase 0: account + billing + budget + Support cases.  
> Phase 2+: Bedrock invoke in code. See also [PHASE_0.md](./PHASE_0.md) section 10.  
> **Root vs IAM / 红条原因：** [AWS_ACCOUNT_NOTES.md](./AWS_ACCOUNT_NOTES.md)

## 1. Account and region

- Personal AWS account; enable **MFA** on root.
- **Default region: `us-east-1`** (N. Virginia) for Bedrock and this project.
- Do **not** rely on Sydney (`ap-southeast-2`) for Bedrock tutorials.

## 2. Billing

1. **Billing and Cost Management** → **Payment preferences** → add credit/debit card.
2. **Budgets** → create e.g. `sec-rag-monthly` **$20/month**.
3. Add alerts: **80%** and **100%** actual costs → your email.

Budget applies to **total account spend** unless you add service filters.

## 3. Bedrock access (2024+ console — important)

### Model access page is retired

**Bedrock → Configure and learn → Model access** may show *"Model access page has been retired"*.  
Serverless models are often **enabled on first invoke** — you do not manually tick boxes there anymore.

### Anthropic (Claude)

- **Claude** models are made by **Anthropic** (company ≠ model name).
- First-time use may require **use case details** (console form).
- If form fails with *"not authorized to perform this action"* → open a **Support case** (below).

### Account-level block (Playground grey / ValidationException)

If Playground shows:

> *To access Amazon Bedrock, you must provide further information so we can verify you are a corporate customer...*

Your **whole Bedrock** access is pending — not just Claude. Open **AWS Support** (do not only retry the form).

### Playground tips

- Use **Chat** tab, not **Image** (Titan Image Generator is not for text chat).
- Try **Amazon Nova** or **Titan Text** after access is granted — not Claude until Anthropic is approved.

## 4. Support case template (copy-paste)

**Support Center** → Create case → Service: **Amazon Bedrock** / Account.

```
Account ID: YOUR_ACCOUNT_ID
Region: us-east-1

I cannot use Amazon Bedrock Playground or invoke models. Errors include:
1) "Your account is not authorized" when submitting Anthropic use case details
2) ValidationException: must verify corporate customer...

I am a student (The University of Hong Kong), personal capstone: agentic RAG over 
public SEC EDGAR filings only. No confidential data. Low-volume dev/demo.

GitHub: https://github.com/Kellyxinyuwu/sec-filings-agentic-rag-aws

Please enable Amazon Bedrock for this account (Nova/Titan for dev, Anthropic Claude when eligible).

Payment method and monthly budget are configured.
```

Wait for email (often hours to a few business days). **Continue Phase 1 locally** while waiting.

## 5. CLI (optional in Phase 0)

```bash
aws configure sso   # or aws configure for dev IAM user
aws sts get-caller-identity
aws bedrock list-foundation-models --region us-east-1 --output table | head
```

## 6. Permissions (later phases)

| Phase | Typical permissions |
|-------|---------------------|
| 2 | `bedrock:InvokeModel`, `bedrock:Converse` |
| 4 | S3 bucket, OpenSearch Serverless |
| 5 | ECS, ECR, CloudWatch Logs; IAM task role (least privilege) |

Dev learning: broader policies OK; **document tightening** in README for interviews.

## 7. Cost notes

- **OpenSearch Serverless** — often the largest cost; create late, tear down after demos.
- Use **Haiku** / smaller models for dev when Claude is available.
- Phase 1 local pgvector + Docker — near **$0** on AWS.

## 8. While Bedrock is pending

| Work | Needs Bedrock? |
|------|----------------|
| Phase 1 ingest + retrieve | No |
| Phase 2 with **Ollama** fallback | No |
| Phase 2 with Bedrock | Yes — after Support |

Design code with `LLM_PROVIDER=ollama|bedrock` (Phase 2 doc).
