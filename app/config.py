from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    api_key: str = "dev-key"
    log_level: str = "INFO"

    aws_region: str = "us-east-1"
    sec_company_name: str = "Your Name"
    sec_company_email: str = "you@example.com"


settings = Settings()
