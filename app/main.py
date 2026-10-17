from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import settings
from app.logging_setup import configure_logging

configure_logging(settings.log_level)

app = FastAPI(
    title="SEC Filings Agentic RAG",
    description="Agentic RAG over SEC EDGAR filings (AWS-backed)",
    version="0.1.0",
)

# Local React (Vite) + optional production frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
