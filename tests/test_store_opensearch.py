"""Tests for app/store_opensearch.py — mock OpenSearch client, no AWS."""

from unittest.mock import MagicMock, patch

import pytest

from app.store_opensearch import search_similar_opensearch, upsert_chunks_opensearch


@patch("app.store_opensearch.get_opensearch_client")
@patch("app.store.embed_texts", return_value=[[0.1, 0.2], [0.3, 0.4]])
@patch("app.store.infer_section", return_value="Item 1A")
def test_upsert_chunks_opensearch_bulk(
    mock_infer: MagicMock,
    mock_embed: MagicMock,
    mock_get_client: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_client.bulk.return_value = {"errors": False, "items": []}
    mock_get_client.return_value = mock_client

    n = upsert_chunks_opensearch(
        ["chunk one", "chunk two"],
        ticker="aapl",
        filing_id="0000320193-25-000079",
        source="test/path",
        chunk_ids=["id-1", "id-2"],
    )

    assert n == 2
    mock_client.bulk.assert_called_once()
    body = mock_client.bulk.call_args.kwargs.get("body") or mock_client.bulk.call_args[0][0]
    assert body[0]["index"]["_id"] == "id-1"
    assert body[1]["ticker"] == "AAPL"
    assert body[1]["embedding"] == [0.1, 0.2]
    assert body[3]["chunk_id"] == "id-2"


@patch("app.store_opensearch.get_opensearch_client")
@patch("app.store.embed_query", return_value=[0.5, 0.6])
def test_search_similar_opensearch_maps_hits(
    mock_embed_query: MagicMock,
    mock_get_client: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_client.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_id": "id-1",
                    "_score": 0.92,
                    "_source": {
                        "chunk_id": "id-1",
                        "filing_id": "fid-1",
                        "ticker": "AAPL",
                        "section": "Item 1A",
                        "content": "Risk factors include competition.",
                    },
                }
            ]
        }
    }
    mock_get_client.return_value = mock_client

    rows = search_similar_opensearch("risk factors", ticker="AAPL", top_k=3)

    assert len(rows) == 1
    assert rows[0]["chunk_id"] == "id-1"
    assert rows[0]["excerpt"] == "Risk factors include competition."
    assert rows[0]["score"] == 0.92

    call_body = mock_client.search.call_args.kwargs["body"]
    assert call_body["query"]["knn"]["embedding"]["filter"] == {"term": {"ticker": "AAPL"}}


@patch("app.store_opensearch.get_opensearch_client")
@patch("app.store.embed_query", return_value=[0.1])
def test_search_similar_opensearch_no_ticker_filter(
    mock_embed_query: MagicMock,
    mock_get_client: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_client.search.return_value = {"hits": {"hits": []}}
    mock_get_client.return_value = mock_client

    search_similar_opensearch("query", top_k=5)

    call_body = mock_client.search.call_args.kwargs["body"]
    assert "filter" not in call_body["query"]["knn"]["embedding"]


@patch("app.aws.use_opensearch", return_value=True)
@patch("app.store_opensearch.search_similar_opensearch")
def test_search_similar_routes_to_opensearch(
    mock_os_search: MagicMock,
    mock_use_os: MagicMock,
) -> None:
    from app.store import search_similar

    mock_os_search.return_value = [
        {
            "chunk_id": "x",
            "filing_id": "f",
            "ticker": "AAPL",
            "section": "Item 1A",
            "excerpt": "y",
            "score": 1.0,
        }
    ]
    rows = search_similar("test query", ticker="MSFT", top_k=2)

    mock_os_search.assert_called_once_with("test query", ticker="MSFT", top_k=2)
    assert rows[0]["chunk_id"] == "x"


@patch("app.aws.use_opensearch", return_value=False)
@patch("app.store._search_similar_pgvector")
def test_search_similar_routes_to_pgvector(
    mock_pg_search: MagicMock,
    mock_use_os: MagicMock,
) -> None:
    from app.store import search_similar

    mock_pg_search.return_value = [
        {
            "chunk_id": "local-1",
            "filing_id": "f",
            "ticker": "AAPL",
            "section": "Item 1A",
            "excerpt": "local hit",
            "score": 0.9,
        }
    ]
    rows = search_similar("test query", ticker="AAPL", top_k=3)

    mock_pg_search.assert_called_once_with("test query", ticker="AAPL", top_k=3)
    assert rows[0]["chunk_id"] == "local-1"


@patch("app.aws.is_opensearch_configured", return_value=False)
@patch("app.aws.use_opensearch", return_value=True)
def test_search_similar_opensearch_requires_endpoint(
    mock_use_os: MagicMock,
    mock_os_cfg: MagicMock,
) -> None:
    from app.store import search_similar

    with pytest.raises(ValueError, match="OPENSEARCH_ENDPOINT is empty"):
        search_similar("test query", ticker="AAPL", top_k=3)
