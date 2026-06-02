from fastapi import FastAPI

from app.api import router
from app.config import settings
from app.logging_setup import configure_logging

configure_logging(settings.log_level)

app = FastAPI(
    title="SEC Filings Agentic RAG",
    description="Agentic RAG over SEC EDGAR filings (AWS-backed)",
    version="0.1.0",
)
app.include_router(router)
