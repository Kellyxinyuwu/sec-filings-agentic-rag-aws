"""Tests for app/s3_storage.py — mock S3, no real AWS."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app import aws
from app.config import settings
from app.s3_storage import (
    build_object_key,
    is_s3_configured,
    upload_bytes,
    upload_filing_submission,
)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    aws.clear_aws_client_cache()
    yield
    aws.clear_aws_client_cache()


def test_is_s3_configured_false_by_default() -> None:
    with patch.object(settings, "s3_bucket", ""):
        assert is_s3_configured() is False


def test_is_s3_configured_true_when_bucket_set() -> None:
    with patch.object(settings, "s3_bucket", "my-bucket"):
        assert is_s3_configured() is True


def test_build_object_key_with_prefix() -> None:
    with patch.object(settings, "s3_prefix", "filings"):
        key = build_object_key("aapl", "0000320193-25-000079", "full-submission.txt")
    assert key == "filings/AAPL/0000320193-25-000079/full-submission.txt"


def test_upload_bytes_calls_put_object(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    monkeypatch.setattr("app.s3_storage.get_s3_client", lambda: mock_client)
    with patch.object(settings, "s3_bucket", "test-bucket"):
        uri = upload_bytes(key="filings/AAPL/x/full-submission.txt", body=b"hello")

    assert uri == "s3://test-bucket/filings/AAPL/x/full-submission.txt"
    mock_client.put_object.assert_called_once()
    call = mock_client.put_object.call_args.kwargs
    assert call["Bucket"] == "test-bucket"
    assert call["Body"] == b"hello"


def test_upload_filing_skipped_without_bucket(tmp_path: Path) -> None:
    f = tmp_path / "full-submission.txt"
    f.write_text("test", encoding="utf-8")
    with patch.object(settings, "s3_bucket", ""):
        assert upload_filing_submission(f, ticker="AAPL", filing_id="fid-1") is None


def test_upload_filing_with_bucket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f = tmp_path / "full-submission.txt"
    f.write_text("filing body", encoding="utf-8")
    mock_client = MagicMock()
    monkeypatch.setattr("app.s3_storage.get_s3_client", lambda: mock_client)
    with patch.object(settings, "s3_bucket", "bkt"), patch.object(settings, "s3_prefix", "filings"):
        uri = upload_filing_submission(f, ticker="AAPL", filing_id="0000320193-25-000079")

    assert uri == "s3://bkt/filings/AAPL/0000320193-25-000079/full-submission.txt"
    mock_client.put_object.assert_called_once()