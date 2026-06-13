"""Tests for ingest_edgar OpenSearch dual-write flag — no AWS."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.ingest_edgar import ingest_file


@patch("scripts.ingest_edgar.upload_filing_submission")
@patch("app.store_opensearch.upsert_chunks_opensearch")
@patch("scripts.ingest_edgar.insert_chunks", return_value=1)
@patch("scripts.ingest_edgar.embed_texts", return_value=[[0.1], [0.2]])
@patch("scripts.ingest_edgar.infer_section", return_value="Item 1A")
@patch("scripts.ingest_edgar.is_opensearch_configured", return_value=True)
def test_ingest_file_indexes_opensearch_when_flag_set(
    mock_os_cfg: MagicMock,
    mock_infer: MagicMock,
    mock_embed: MagicMock,
    mock_insert: MagicMock,
    mock_upsert_os: MagicMock,
    mock_s3: MagicMock,
    tmp_path: Path,
) -> None:
    f = tmp_path / "full-submission.txt"
    f.write_text("risk factors text long enough", encoding="utf-8")

    n = ingest_file(
        f,
        ticker="AAPL",
        filing_id="0000320193-25-000079",
        index_opensearch=True,
    )

    assert n == 1
    mock_upsert_os.assert_called_once()
    kwargs = mock_upsert_os.call_args.kwargs
    assert kwargs["embeddings"] == [[0.1], [0.2]]
    assert kwargs["ticker"] == "AAPL"
    mock_insert.assert_called_once()
    assert mock_insert.call_args.kwargs["embeddings"] == [[0.1], [0.2]]


@patch("app.store_opensearch.upsert_chunks_opensearch")
@patch("scripts.ingest_edgar.insert_chunks", return_value=1)
@patch("scripts.ingest_edgar.embed_texts", return_value=[[0.1]])
@patch("scripts.ingest_edgar.infer_section", return_value="Item 1A")
@patch("scripts.ingest_edgar.is_opensearch_configured", return_value=False)
def test_ingest_file_skips_opensearch_when_not_configured(
    mock_os_cfg: MagicMock,
    mock_infer: MagicMock,
    mock_embed: MagicMock,
    mock_insert: MagicMock,
    mock_upsert_os: MagicMock,
    tmp_path: Path,
) -> None:
    f = tmp_path / "full-submission.txt"
    f.write_text("some filing text here", encoding="utf-8")

    ingest_file(f, ticker="AAPL", filing_id="fid", index_opensearch=True)

    mock_upsert_os.assert_not_called()
