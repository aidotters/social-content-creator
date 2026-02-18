"""NotionPaperCollectorのテスト。"""

import pytest
import respx
from httpx import Response

from src.collectors.notion_paper import NotionPaperCollector
from src.errors import CollectionError

NOTION_DB_QUERY_URL = "https://api.notion.com/v1/databases/test-paper-db-id/query"


def _make_page(
    title: str = "Attention Is All You Need",
    japanese_title: str = "",
    summary: str = "Transformer architecture",
    url: str = "https://arxiv.org/abs/1706.03762",
) -> dict:
    """テスト用のNotionページデータを生成する。"""
    return {
        "properties": {
            "タイトル": {"title": [{"plain_text": title}]},
            "日本語訳": {"rich_text": [{"plain_text": japanese_title}] if japanese_title else []},
            "概要": {"rich_text": [{"plain_text": summary}]},
            "URL": {"url": url},
            "公開日": {"date": {"start": "2026-02-15"}},
            "更新日": {"date": {"start": "2026-02-16"}},
            "チェック済": {"checkbox": False},
        }
    }


def _make_query_response(
    pages: list[dict],
    has_more: bool = False,
    next_cursor: str | None = None,
) -> dict:
    return {
        "results": pages,
        "has_more": has_more,
        "next_cursor": next_cursor,
    }


class TestNotionPaperCollector:
    """NotionPaperCollectorのテスト。"""

    def test_init_without_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """トークン未設定でCollectionErrorが発生する。"""
        monkeypatch.setenv("NOTION_TOKEN", "")
        with pytest.raises(CollectionError, match="NOTION_TOKEN"):
            NotionPaperCollector(paper_db_id="test-db")

    def test_init_without_db_id_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DB ID未設定でCollectionErrorが発生する。"""
        monkeypatch.setenv("NOTION_PAPER_DB_ID", "")
        with pytest.raises(CollectionError, match="NOTION_PAPER_DB_ID"):
            NotionPaperCollector(token="secret_test")

    @respx.mock
    async def test_collect_recent_papers(self) -> None:
        """最近の論文が取得できる。"""
        pages = [_make_page()]
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response(pages))
        )

        collector = NotionPaperCollector(token="secret_test", paper_db_id="test-paper-db-id")
        results = await collector.collect("")

        assert len(results) == 1
        assert results[0].title == "Attention Is All You Need"
        assert results[0].source == "notion_paper"
        assert "Transformer" in results[0].content

    @respx.mock
    async def test_japanese_title_preferred(self) -> None:
        """日本語訳がある場合はそちらが優先される。"""
        pages = [_make_page(title="Original", japanese_title="日本語タイトル")]
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response(pages))
        )

        collector = NotionPaperCollector(token="secret_test", paper_db_id="test-paper-db-id")
        results = await collector.collect("")

        assert results[0].title == "日本語タイトル"

    @respx.mock
    async def test_filter_by_keyword(self) -> None:
        """キーワードでフィルタリングできる。"""
        pages = [
            _make_page(title="Vision Transformer", summary="Image classification"),
            _make_page(title="BERT Fine-tuning", summary="NLP with BERT"),
        ]
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response(pages))
        )

        collector = NotionPaperCollector(token="secret_test", paper_db_id="test-paper-db-id")
        results = await collector.collect("Vision")

        assert len(results) == 1
        assert results[0].title == "Vision Transformer"

    @respx.mock
    async def test_api_error_raises(self) -> None:
        """APIエラーでCollectionErrorが発生する。"""
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(500, json={"message": "Internal Server Error"})
        )

        collector = NotionPaperCollector(token="secret_test", paper_db_id="test-paper-db-id")
        with pytest.raises(CollectionError, match="500"):
            await collector.collect("")

    @respx.mock
    async def test_pagination(self) -> None:
        """ページネーションで全ページ取得できる。"""
        page1 = [_make_page(title="論文1")]
        page2 = [_make_page(title="論文2")]

        route = respx.post(NOTION_DB_QUERY_URL)
        route.side_effect = [
            Response(200, json=_make_query_response(page1, has_more=True, next_cursor="c1")),
            Response(200, json=_make_query_response(page2, has_more=False)),
        ]

        collector = NotionPaperCollector(token="secret_test", paper_db_id="test-paper-db-id")
        results = await collector.collect("")

        assert len(results) == 2

    @respx.mock
    async def test_empty_results(self) -> None:
        """結果が空の場合、空リストが返る。"""
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response([]))
        )

        collector = NotionPaperCollector(token="secret_test", paper_db_id="test-paper-db-id")
        results = await collector.collect("")

        assert results == []

    @respx.mock
    async def test_url_extracted(self) -> None:
        """URLが正しく抽出される。"""
        pages = [_make_page(url="https://arxiv.org/abs/2401.12345")]
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response(pages))
        )

        collector = NotionPaperCollector(token="secret_test", paper_db_id="test-paper-db-id")
        results = await collector.collect("")

        assert results[0].url == "https://arxiv.org/abs/2401.12345"
