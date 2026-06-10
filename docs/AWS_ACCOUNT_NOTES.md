# AWS 账号笔记：Root vs IAM、Bedrock 开通

个人学习记录（Phase 0 同期整理）。遇到 Playground 红条 / Support 等待时可回看。

---

## Root vs IAM 是什么？

| | **Root（根用户）** | **IAM User（子用户）** |
|---|-------------------|------------------------|
| **是什么** | 注册 AWS 时自带的「主账号」（你的邮箱那个） | 在 IAM 里创建的开发者身份 |
| **权限** | 默认拥有账号内**全部**权限 | 需管理员挂 IAM policy，可最小权限 |
| **日常开发** | ❌ 不推荐长期用（泄露风险大） | ✅ 推荐（实习/公司常规做法） |
| **能否用 Bedrock** | 能（账号开通后） | 能，但需 `bedrock:*` 等权限 |

**注册 AWS 后先只有 Root，这是正常的**，不是「开错账号类型」。

---

## 用 Root 会导致 Bedrock 红条吗？

**不会。** Root 权限比 IAM 更大，不是 Bedrock 被拦的原因。

若 Playground 出现：

> *To access Amazon Bedrock, you must provide further information so we can verify you are a corporate customer...*

或 Anthropic use case 表单：

> *Your account is not authorized to perform this action*

这是 **AWS 对新账号的账号级审核**（需 **Support case**），与 Root / IAM **无关**。  
在账号未放行前，**换 IAM 用户通常仍会同样报错**。

---

## Bedrock：整账号 vs 单个模型

两层限制要分开看：

| 层级 | 典型现象 | 影响 |
|------|----------|------|
| **1. 账号级** | 上面 ValidationException；Nova / Titan / Claude **都**不行 | 整个 Bedrock 待 AWS 放行 |
| **2. 模型级（Anthropic）** | 仅 Claude 报错；Model catalog 黄条 | 账号已开，还需 **FTU use case** 表单 |

**如何自测（us-east-1，Playground → Chat）：**

1. 试 **Amazon Nova** 或 **Titan Text**
2. 再试 **Claude Haiku**

- 全部红条 → 等 Support（**bedrock-runtime** 账号级）
- 仅 Claude 不行 → 填/重试 Anthropic use case
- **Mantle 里 Qwen/MiniMax 能用、Playground 仍红** → 见 [BEDROCK_MANTLE_VS_RUNTIME.md](./BEDROCK_MANTLE_VS_RUNTIME.md)（两条线路）

---

## 官方文档（Model access 已改版）

- [Request access to models](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)

要点：

1. 商业区多数模型 **首次 invoke 自动开通**，旧「Model access 勾选页」已废弃。
2. **前提**：有效付款方式、（部分第三方模型）Marketplace 订阅权限。
3. **Anthropic**：每账号一次 **use case**；学生可用 **GitHub 项目链接** 当 website。
4. **Amazon / Meta / Mistral 等**：不经过 Marketplace product ID，账号放行后往往更容易先试通。

---

## 建议做法（本项目）

| 事项 | 状态 / 建议 |
|------|-------------|
| 付款方式 + Budget | 已配置则保持 |
| Support cases | 等待；可在原 case **Reply**，勿重复开很多 |
| 日常登录 | 可选：建 IAM user `dev-kelly` + `AmazonBedrockFullAccess`（习惯用，不替代 Support） |
| 项目进度 | **Bedrock 未通 → 先做 Phase 1**（本地 EDGAR + pgvector） |
| Support 通过后 | 先试 Nova/Titan → 再 Claude → Phase 2 |

---

## Support case 回复模板（可选）

在已有 case 里 Reply：

```
Account ID: 449873021145
Payment method and monthly budget are configured.
Playground still shows ValidationException for Bedrock models.
Please enable Amazon Bedrock access for this account.
GitHub: https://github.com/Kellyxinyuwu/sec-filings-agentic-rag-aws
Thank you.
```

---

## 相关文档

- [AWS_SETUP.md](./AWS_SETUP.md) — 操作 checklist
- [PHASE_0.md](./PHASE_0.md) — Phase 0 步骤 H（AWS 准备）
- [BEDROCK_MANTLE_VS_RUNTIME.md](./BEDROCK_MANTLE_VS_RUNTIME.md) — Mantle vs classic Playground、7 天路径选择
