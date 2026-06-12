"""
Tests for app/aws.py — Phase 4 Step 1.

Mock boto3 / OpenSearch — no real AWS calls in CI.
"""

from unittest.mock import MagicMock, patch

import pytest

from app import aws
from app.config import settings


@pytest.fixture(autouse=True)
def _clear_session_cache() -> None:
    aws.clear_aws_client_cache()
    yield
    aws.clear_aws_client_cache()


def test_vector_backend_defaults_local() -> None:
    assert aws.vector_backend() == "local"
    assert aws.use_local_pgvector() is True
    assert aws.use_opensearch() is False


def test_parse_opensearch_host_from_url() -> None:
    host = aws.parse_opensearch_host("https://abc123.us-east-1.aoss.amazonaws.com")
    assert host == "abc123.us-east-1.aoss.amazonaws.com"


def test_parse_opensearch_host_bare_hostname() -> None:
    host = aws.parse_opensearch_host("abc123.us-east-1.aoss.amazonaws.com")
    assert host == "abc123.us-east-1.aoss.amazonaws.com"


def test_require_s3_bucket_raises_when_empty() -> None:
    with patch.object(settings, "s3_bucket", ""):
        with pytest.raises(ValueError, match="S3_BUCKET"):
            aws.require_s3_bucket()


def test_require_s3_bucket_rejects_invalid_name() -> None:
    with patch.object(settings, "s3_bucket", "你建的bucket名"):
        with pytest.raises(ValueError, match="not a valid S3 bucket name"):
            aws.require_s3_bucket()


def test_get_s3_client_uses_region(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client
    monkeypatch.setattr(aws, "get_boto3_session", lambda: mock_session)

    client = aws.get_s3_client()

    mock_session.client.assert_called_once_with("s3")
    assert client is mock_client


@patch("app.aws.OpenSearch")
@patch("app.aws._opensearch_aws4auth")
def test_get_opensearch_client(
    mock_auth: MagicMock,
    mock_opensearch_cls: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_auth.return_value = MagicMock()
    mock_opensearch_cls.return_value = MagicMock(name="os_client")
    monkeypatch.setattr(settings, "opensearch_endpoint", "https://test.us-east-1.aoss.amazonaws.com")

    client = aws.get_opensearch_client()

    mock_opensearch_cls.assert_called_once()
    call_kwargs = mock_opensearch_cls.call_args.kwargs
    assert call_kwargs["hosts"] == [{"host": "test.us-east-1.aoss.amazonaws.com", "port": 443}]
    assert call_kwargs["use_ssl"] is True
    assert client is mock_opensearch_cls.return_value


def test_get_opensearch_client_requires_endpoint() -> None:
    with patch.object(settings, "opensearch_endpoint", ""):
        with pytest.raises(ValueError, match="OPENSEARCH_ENDPOINT"):
            aws.get_opensearch_client()


def test_import_does_not_create_clients() -> None:
    """Import + helper calls that skip network should not instantiate boto3 Session."""
    with patch("app.aws.boto3.Session") as mock_session_cls:
        aws.clear_aws_client_cache()
        assert aws.vector_backend() == "local"
        mock_session_cls.assert_not_called()