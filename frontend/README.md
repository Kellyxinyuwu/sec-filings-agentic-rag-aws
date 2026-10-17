# FilingDesk frontend

React (Vite) chat UI for the SEC Filings Agentic RAG API. Sends questions to `POST /chat` and shows the answer plus chunk-level citations.

## Prerequisites

API must be running (default `http://127.0.0.1:8001`):

```bash
# from repo root
source .venv/bin/activate
uvicorn app.main:app --reload --port 8001
```

## Run

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. Vite proxies `/api/*` → FastAPI `:8001`, so no CORS setup is required for local use.

Optional: set `VITE_API_BASE` in `.env` (see `.env.example`) to point at a deployed ALB instead of the proxy.

## Stack

- React 19 + TypeScript + Vite
- Talks directly to existing FastAPI (no Node backend)
