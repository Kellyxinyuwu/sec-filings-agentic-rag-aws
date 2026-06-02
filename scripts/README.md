# Scripts

| Script | Purpose |
|--------|---------|
| `local_dev.sh` | Create venv, install deps, run API on port 8000 |
| `ingest_edgar.py` | *(Phase 1)* Download + chunk SEC filings |

Run ingest from repo root:

```bash
python scripts/ingest_edgar.py --ticker AAPL
```
