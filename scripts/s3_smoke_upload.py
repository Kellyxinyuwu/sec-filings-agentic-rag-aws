#!/usr/bin/env python3
"""
Phase 4 Step 2 smoke test — upload one local filing to S3.

Prereqs:
  - .env: S3_BUCKET, AWS credentials (profile or keys)
  - Local file under sec-edgar-filings/ (run ingest download first, or --skip-download)

Usage (repo root):
    python scripts/s3_smoke_upload.py --ticker AAPL
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402
from app.s3_storage import is_s3_configured, upload_filing_submission  # noqa: E402

# Reuse ingest path discovery
from scripts.ingest_edgar import find_filing_paths  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload one SEC filing to S3 (smoke test)")
    parser.add_argument("--ticker", default="AAPL")
    args = parser.parse_args()
    ticker = args.ticker.upper()

    if not is_s3_configured():
        print("S3_BUCKET is empty — set it in .env first.")
        return 1

    print(f"Bucket: {settings.s3_bucket}")
    print(f"Prefix: {settings.s3_prefix}")
    print(f"Region: {settings.aws_region}")

    filings = find_filing_paths(ticker)
    if not filings:
        print(f"No filing found for {ticker}. Run ingest_edgar.py first.")
        return 1

    txt_path, filing_id = filings[0]
    print(f"Uploading {txt_path} ...")
    uri = upload_filing_submission(txt_path, ticker=ticker, filing_id=filing_id)
    if uri is None:
        print("Upload skipped (S3 not configured).")
        return 1

    print(f"OK: {uri}")
    print(f"\nVerify: aws s3 ls s3://{settings.s3_bucket}/{settings.s3_prefix.strip('/')}/{ticker}/ --recursive")
    return 0


if __name__ == "__main__":
    sys.exit(main())