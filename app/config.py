"""
Central settings from .env — single source of truth for all phases.

Pydantic Settings 会把环境变量名自动映射到字段：
  VECTOR_BACKEND  →  vector_backend
  S3_BUCKET       →  s3_bucket
  （大写 + 下划线 ↔ 小写 snake_case）

Import: from app.config import settings
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # .env 里多写的 key 不报错（方便提前写 Phase 5 变量）
    )

    # -------------------------------------------------------------------------
    # App / logging
    # -------------------------------------------------------------------------
    app_env: str = "local"
    api_key: str = "dev-key"
    log_level: str = "INFO"

    # -------------------------------------------------------------------------
    # AWS（区域 — S3 / OpenSearch / 日后 classic Bedrock 共用）
    # 凭证不进 config：用 AWS_PROFILE 或 ~/.aws/credentials（boto3 自动读）
    # -------------------------------------------------------------------------
    aws_region: str = "us-east-1"

    # -------------------------------------------------------------------------
    # SEC EDGAR（ingest 下载 10-K 必填 — SEC 要求 User-Agent 含联系邮箱）
    # -------------------------------------------------------------------------
    sec_company_name: str = "Kelly Wu"
    sec_company_email: str = "kellywuxinyu@gmail.com"

    # -------------------------------------------------------------------------
    # Retrieval — 向量从哪搜、embedding 从哪算
    #
    # Phase 1–3 默认：local pgvector + 本地 MiniLM
    # Phase 4+：VECTOR_BACKEND=opensearch 时 retrieve 读 AWS；embed 仍 local（hybrid）
    # ingest 写 OpenSearch 看 --index-opensearch，与此字段无关
    # -------------------------------------------------------------------------
    database_url: str = "postgresql://postgres:postgres@localhost:5433/rag_db"
    embedding_model: str = "all-MiniLM-L6-v2"  # 384-dim；须与 ingest / retrieve 一致

    vector_backend: str = "local"  # local=pgvector | opensearch=云 k-NN；改后重启 uvicorn
    embedding_provider: str = "local"  # local | bedrock（future Titan）
    embedding_dimensions: int = 384  # MiniLM 输出维度；OpenSearch mapping 须一致

    # -------------------------------------------------------------------------
    # Object storage — 原始 / 处理后的 filing（Phase 4 Step 2+）
    # -------------------------------------------------------------------------
    s3_bucket: str = ""  # 空 = 尚未建 bucket；Step 2 前不要求填
    s3_prefix: str = "filings"  # 对象 key 前缀，如 filings/AAPL/...

    # -------------------------------------------------------------------------
    # OpenSearch Serverless — k-NN 向量索引（Phase 4 Step 3+）
    # -------------------------------------------------------------------------
    opensearch_endpoint: str = ""  # 控制台复制的 collection endpoint（URL 或 host）
    opensearch_index: str = "sec-chunks"
    opensearch_timeout_seconds: float = 30.0

    # -------------------------------------------------------------------------
    # Generation — LLM 答案从哪来（Phase 2+）
    #
    # 当前 capstone：Mantle only（personal account Support 未过 classic Bedrock）
    # -------------------------------------------------------------------------
    llm_provider: str = "mantle"  # mantle | bedrock | ollama
    mantle_base_url: str = "https://bedrock-mantle.us-east-1.api.aws/v1"
    mantle_api_key: str = ""
    mantle_model_id: str = ""
    mantle_max_tokens: int = 1024
    mantle_timeout_seconds: float = 60.0

    # Classic bedrock-runtime — future（Support / 公司账号开通后）
    bedrock_chat_model_id: str = ""  # e.g. anthropic.claude-3-5-haiku-...
    bedrock_embed_model_id: str = ""  # e.g. amazon.titan-embed-text-v2:0


settings = Settings()
