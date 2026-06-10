# Ingest & SEC download — FAQ

Questions that often come up during **Phase 1 Step 5** (`scripts/ingest_edgar.py`).

Related: [PHASE_1.md](./PHASE_1.md) Step 5, old project `SEC-10-K-RAG/scripts/download_financial_docs.py`.

---

## Does this project fetch filings from the SEC website?

**Yes — programmatically, not in a browser.**

`ingest_edgar.py` uses **`sec-edgar-downloader`**, which sends HTTP requests to **SEC EDGAR**. This is the same idea as the old project’s `download_financial_docs.py`:

```python
dl.get("10-K", ticker, limit=1)   # hits EDGAR servers
```

There is no separate step where you open sec.gov manually. The download is **step 2/3** when you run:

```bash
python scripts/ingest_edgar.py --ticker AAPL
```

You should see:

```
2/3 download from EDGAR ...
Downloading up to 1 10-K(s) for AAPL ...
```

If you use **`--skip-download`**, that step is skipped and the script only reads files already on disk — so it can look like “we never fetched from the website” even though the pipeline supports it.

```bash
# Download + ingest
python scripts/ingest_edgar.py --ticker AAPL

# Ingest only (files must already exist under sec-edgar-filings/)
python scripts/ingest_edgar.py --ticker AAPL --skip-download
```

---

## One company or several? (vs old `SEC-10-K-RAG`)

The **old project** downloaded multiple tickers in one script:

```python
TICKERS = ["AAPL", "GOOGL"]
```

**This capstone — Phase 1 MVP** defaults to **one ticker, one 10-K**:

| | Old `SEC-10-K-RAG` | This repo (Phase 1) |
|--|-------------------|---------------------|
| Tickers | AAPL + GOOGL (config list) | **AAPL** by default (`--ticker`) |
| 10-Ks per ticker | 1 | 1 (`--limit` to change) |
| Rationale | Practice multi-ticker retrieval | Smaller scope — debug ingest → retrieve first |

This is **intentional** ([PHASE_1.md](./PHASE_1.md): “MVP ticker: AAPL, 1 份 10-K”). It is not a missing feature.

### Adding more companies later

Run ingest again with another ticker (download + embed each time):

```bash
python scripts/ingest_edgar.py --ticker GOOGL
python scripts/ingest_edgar.py --ticker MSFT
```

Multiple 10-Ks for the same ticker:

```bash
python scripts/ingest_edgar.py --ticker AAPL --limit 2
```

Use `retrieve(..., ticker="AAPL")` in Step 6+ to filter search to one company.

---

## What are the three steps when the script runs?

| Step | When | What |
|------|------|------|
| **1/3** | Always | `init_schema()` — ensure `documents` table exists |
| **2/3** | Unless `--skip-download` | Download from EDGAR via `sec-edgar-downloader` |
| **3/3** | Always | Read `full-submission.txt` → chunk → embed → `insert_chunks()` |

Example successful end of step 3:

```
Ingested 10834 chunks for AAPL / 0000320193-25-000079
Done. Total chunks: 10834
```

---

## Where do downloaded files go?

`sec-edgar-downloader` always creates a **`sec-edgar-filings/`** subfolder inside the parent directory you pass to `Downloader`.

This project passes **repo root** (`PROJECT_ROOT`), so the correct layout is:

```
sec-edgar-filings/AAPL/10-K/{accession}/full-submission.txt
```

**Common mistake:** passing `.../sec-edgar-filings` as the Downloader parent → double nesting:

```
sec-edgar-filings/sec-edgar-filings/AAPL/10-K/...   # wrong
```

`find_filing_paths()` in `ingest_edgar.py` uses `rglob` so older mistaken downloads can still be ingested.

---

## SEC identity (`.env`)

EDGAR requires a real name and email in the User-Agent. Set in `.env` (**no space after `=`**):

```bash
SEC_COMPANY_NAME=Kelly Wu
SEC_COMPANY_EMAIL=kellywuxinyu@gmail.com
```

Read via `app.config.settings` → `Downloader(settings.sec_company_name, settings.sec_company_email, ...)`.

---

## Other notes

| Topic | Note |
|-------|------|
| **HF_TOKEN warning** | Optional; first run still downloads `all-MiniLM-L6-v2` |
| **Docker** | `docker compose ps` → `db` healthy before ingest |
| **Re-ingest** | Same `chunk_id` pattern → UPSERT in `store.py`, safe to re-run |
| **Phase 1 scope** | Real retrieval, no LLM yet; multi-ticker is optional stretch |
