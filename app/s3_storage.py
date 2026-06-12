"""
S3 object storage for SEC filings — Phase 4 Step 2.

职责：
  - 根据 ticker / filing_id 生成 S3 key（路径规范）
  - 把本地 full-submission.txt 上传到 bucket
  - bucket 未配置时静默跳过（本地开发不强制 S3）

不负责：
  - 创建 boto3 client（见 app.aws.get_s3_client）
  - chunk 向量（仍走 store.py / 日后 OpenSearch）
"""

from __future__ import annotations

from pathlib import Path

import structlog

from app.aws import get_s3_client, require_s3_bucket
from app.config import settings

log = structlog.get_logger()

CONTENT_TYPE_PLAIN = "text/plain; charset=utf-8"


def is_s3_configured() -> bool:
    """S3_BUCKET 非空才启用上传（pytest 默认空 bucket → 不调 AWS）。"""
    return bool(settings.s3_bucket.strip())


def build_object_key(ticker: str, filing_id: str, filename: str) -> str:
    """
    对象 key 规范：{prefix}/{TICKER}/{filing_id}/{filename}

    例：filings/AAPL/0000320193-25-000079/full-submission.txt
    """
    prefix = settings.s3_prefix.strip().strip("/")
    ticker_u = ticker.upper()
    safe_name = Path(filename).name
    if prefix:
        return f"{prefix}/{ticker_u}/{filing_id}/{safe_name}"
    return f"{ticker_u}/{filing_id}/{safe_name}"


def upload_bytes(
    *,
    key: str,
    body: bytes,
    content_type: str = CONTENT_TYPE_PLAIN,
) -> str:
    """
    上传字节到 S3。返回 s3://bucket/key URI。
    """
    bucket = require_s3_bucket()
    client = get_s3_client()
    log.info("s3_put_object", bucket=bucket, key=key, bytes=len(body))
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
    )
    return f"s3://{bucket}/{key}"


def upload_file(local_path: Path, *, key: str) -> str:
    """读本地文件并 upload_bytes。"""
    data = local_path.read_bytes()
    return upload_bytes(key=key, body=data)


def upload_filing_submission(
    local_txt_path: Path,
    *,
    ticker: str,
    filing_id: str,
) -> str | None:
    """
    上传一份 10-K full-submission.txt。

    若 S3_BUCKET 未配置，返回 None（不报错，方便无 AWS 时跑 ingest）。
    """
    if not is_s3_configured():
        log.debug("s3_upload_skipped", reason="S3_BUCKET not set")
        return None

    key = build_object_key(ticker, filing_id, local_txt_path.name)
    uri = upload_file(local_txt_path, key=key)
    log.info("s3_filing_uploaded", uri=uri, ticker=ticker, filing_id=filing_id)
    return uri