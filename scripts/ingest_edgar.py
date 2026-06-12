#!/usr/bin/env python3
"""
Step 5: Download SEC 10-K → chunk → embed → pgvector.

Usage (repo root):
    python scripts/ingest_edgar.py --ticker AAPL

Pipeline:
  1. sec-edgar-downloader  (SEC User-Agent = your name/email from .env)
  2. full-submission.txt under sec-edgar-filings/{TICKER}/10-K/{accession}/
  3. tiktoken chunk 400 tokens, 100 overlap
  4. app.store.insert_chunks()  → embed + INSERT
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import tiktoken

from app.config import settings
from app.store import init_schema, insert_chunks
from app.s3_storage import upload_filing_submission

# scripts/ → repo root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FILINGS_DIR = PROJECT_ROOT / "sec-edgar-filings"

# Same as SEC-10-K-RAG: ~300 words/chunk, overlap keeps sentences from being cut in half
CHUNK_SIZE_TOKENS = 400
CHUNK_OVERLAP_TOKENS = 100


def chunk_with_overlap(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split filing text into token windows (cl100k_base encoding)."""
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    if not tokens:
        return []

    chunks: list[str] = []
    stride = chunk_size - overlap
    start = 0

    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        piece = encoding.decode(tokens[start:end]).strip()
        if piece:
            chunks.append(piece)
        start += stride
        if start >= len(tokens):
            break

    return chunks


def download_10k(ticker: str, limit: int = 1) -> None:
    """
    Download latest 10-K(s) into sec-edgar-filings/.
    SEC requires real identity — read from settings (SEC_COMPANY_* in .env).

    Note: Downloader's 3rd arg is the *parent* directory; the library always
    creates a sec-edgar-filings/ subfolder inside it. Pass PROJECT_ROOT, not FILINGS_DIR.
    """
    from sec_edgar_downloader import Downloader

    dl = Downloader(
        settings.sec_company_name,
        settings.sec_company_email,
        str(PROJECT_ROOT),
    )
    print(f"Downloading up to {limit} 10-K(s) for {ticker} ...")
    dl.get("10-K", ticker, limit=limit)


def find_filing_paths(ticker: str) -> list[tuple[Path, str]]:
    """
    Locate full-submission.txt files under sec-edgar-filings/.
    Returns [(path, filing_id), ...] where filing_id = accession folder name.

    Uses rglob so we still find files if an older run used the wrong download path.
    """
    if not FILINGS_DIR.exists():
        return []

    ticker = ticker.upper()
    results: list[tuple[Path, str]] = []
    seen: set[str] = set()

    for txt_path in sorted(FILINGS_DIR.rglob("full-submission.txt")):
        parts = txt_path.parts
        try:
            ten_k_idx = parts.index("10-K")
        except ValueError:
            continue
        if ten_k_idx < 1 or parts[ten_k_idx - 1].upper() != ticker:
            continue
        if ten_k_idx + 1 >= len(parts):
            continue
        filing_id = parts[ten_k_idx + 1]
        if filing_id in seen:
            continue
        seen.add(filing_id)
        results.append((txt_path, filing_id))

    return results

def ingest_file(txt_path: Path, ticker: str, filing_id: str, *, upload_s3: bool = False) -> int:
    """Read one filing, chunk, call store.insert_chunks(). Returns chunk count."""
    print(f"  Reading {txt_path} ({len(txt_path.read_bytes()) // 1024} KB) ...")
    text = txt_path.read_text(encoding="utf-8", errors="ignore")

    chunks = chunk_with_overlap(text, CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS)
    if not chunks:
        print("  No chunks produced.")
        return 0

    print(f"  Embedding + inserting {len(chunks)} chunks (first run downloads MiniLM) ...")

    # Stable IDs → re-run updates same rows (ON CONFLICT in store.py)
    chunk_ids = [f"{ticker.upper()}-{filing_id}-{i:05d}" for i in range(len(chunks))]

    n = insert_chunks(
        chunks,
        ticker=ticker.upper(),
        filing_id=filing_id,
        source=str(txt_path.relative_to(PROJECT_ROOT)),
        chunk_ids=chunk_ids,
    )

    if upload_s3:
        uri = upload_filing_submission(txt_path, ticker=ticker, filing_id=filing_id)
        if uri:
            print(f"  S3: {uri}")

    return n


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest SEC 10-K into local pgvector")
    parser.add_argument("--ticker", default="AAPL", help="Ticker symbol (default: AAPL)")
    parser.add_argument("--limit", type=int, default=1, help="Number of 10-Ks to download")
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip EDGAR download; ingest files already under sec-edgar-filings/",
    )
    parser.add_argument(
        "--upload-s3",
        action="store_true",
        help="After ingest, upload full-submission.txt to S3 (needs S3_BUCKET in .env)",
    )
    args = parser.parse_args()
    ticker = args.ticker.upper()

    print("Step 5 ingest —", ticker)
    print(f"  SEC identity: {settings.sec_company_name} <{settings.sec_company_email}>")
    print(f"  Database: {settings.database_url}")

    print("\n1/3 init_schema() ...")
    init_schema()

    if not args.skip_download:
        print("\n2/3 download from EDGAR ...")
        download_10k(ticker, limit=args.limit)
    else:
        print("\n2/3 skip download (--skip-download)")

    filings = find_filing_paths(ticker)
    if not filings:
        print(
            f"\nNo full-submission.txt for {ticker} under {FILINGS_DIR}.\n"
            "Run without --skip-download, or check SEC name/email in .env."
        )
        return 1

    print(f"\n3/3 ingest {len(filings)} filing(s) ...")
    total = 0
    for txt_path, filing_id in filings:
        print(f"\nFiling {filing_id}:")
        n = ingest_file(txt_path, ticker, filing_id, upload_s3=args.upload_s3)
        total += n
        print(f"Ingested {n} chunks for {ticker} / {filing_id}")

    print(f"\nDone. Total chunks: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())