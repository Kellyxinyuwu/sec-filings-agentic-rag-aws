from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Load .env from project root; ignore unknown keys (Phase 2+ vars can sit in .env early).
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Phase 0: app / API ---
    app_env: str = "local"
    api_key: str = "dev-key"
    log_level: str = "INFO"

    # --- Phase 0: AWS / SEC (SEC used in Step 5 ingest) ---
    aws_region: str = "us-east-1"
    sec_company_name: str = "Kelly Wu"
    sec_company_email: str = "kellywuxinyu@gmail.com"

    # --- Phase 1: local RAG ---
    # Postgres + pgvector (docker-compose db on host port 5433)
    database_url: str = "postgresql://postgres:postgres@localhost:5433/rag_db"
    # sentence-transformers model id — must match ingest AND retrieve (384-dim for MiniLM)
    embedding_model: str = "all-MiniLM-L6-v2"

    # --- Phase 2: LLM generation (Bedrock Mantle default) ---
    # mantle | bedrock | ollama — Step 2 wires mantle first
    llm_provider: str = "mantle"
    mantle_base_url: str = "https://bedrock-mantle.us-east-1.api.aws/v1"
    mantle_api_key: str = ""
    mantle_model_id: str = ""
    mantle_max_tokens: int = 1024
    mantle_timeout_seconds: float = 60.0

    # Classic bedrock-runtime Converse (after Support — llm_bedrock.py later)
    bedrock_chat_model_id: str = ""


# Singleton: import as `from app.config import settings`
settings = Settings()