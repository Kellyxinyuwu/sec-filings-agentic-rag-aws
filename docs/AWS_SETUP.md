# AWS setup (do before Phase 2)

## 1. Account and region

- Use a personal AWS account with a **billing budget** (e.g. $20/month alert).
- Default region: **`us-east-1`** (Bedrock model availability).

## 2. CLI

```bash
aws configure sso   # or access keys for dev only
aws sts get-caller-identity
```

## 3. Bedrock model access

In console: **Amazon Bedrock → Model access**

- Enable a **chat** model (e.g. Claude 3.5 Sonnet or Haiku for dev).
- Enable an **embedding** model (e.g. Titan Embed Text v2).

## 4. Permissions (dev user — tighten later for ECS task role)

Minimum for later phases:

- `bedrock:InvokeModel`
- `s3:*` on your project bucket (or scoped bucket ARN)
- OpenSearch Serverless APIs (Phase 4)
- `logs:*` for CloudWatch (Phase 5)

## 5. Cost notes

- **OpenSearch Serverless** can dominate cost — create only when needed; tear down after demos.
- Prefer **Haiku** / smaller models during development.
