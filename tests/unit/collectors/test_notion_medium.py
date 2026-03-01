"""NotionMediumCollectorのテスト。"""

import pytest
import respx
from httpx import Response

from src.collectors.notion_medium import NotionMediumCollector
from src.errors import CollectionError

NOTION_DB_QUERY_URL = "https://api.notion.com/v1/databases/test-medium-db-id/query"


def _make_page(
    title: str = "Building AI Agents",
    japanese_title: str = "",
    author: str = "John Doe",
    summary: str = "A guide to building AI agents",
    url: str = "https://medium.com/article",
    claps: int = 100,
) -> dict:
    """テスト用のNotionページデータを生成する。"""
    return {
        "properties": {
            "Title": {"title": [{"plain_text": title}]},
            "Japanese Title": {
                "rich_text": [{"plain_text": japanese_title}] if japanese_title else []
            },
            "Author": {"rich_text": [{"plain_text": author}]},
            "Summary": {"rich_text": [{"plain_text": summary}]},
            "Date": {"date": {"start": "2026-02-15"}},
            "Claps": {"number": claps},
            "Translated": {"checkbox": False},
            "URL": {"url": url},
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


class TestNotionMediumCollector:
    """NotionMediumCollectorのテスト。"""

    def test_init_without_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """トークン未設定でCollectionErrorが発生する。"""
        monkeypatch.setenv("NOTION_TOKEN", "")
        with pytest.raises(CollectionError, match="NOTION_TOKEN"):
            NotionMediumCollector(medium_db_id="test-db")

    def test_init_without_db_id_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DB ID未設定でCollectionErrorが発生する。"""
        monkeypatch.setenv("NOTION_MEDIUM_DB_ID", "")
        with pytest.raises(CollectionError, match="NOTION_MEDIUM_DB_ID"):
            NotionMediumCollector(token="secret_test")

    @respx.mock
    async def test_collect_recent_articles(self) -> None:
        """最近の記事が取得できる。"""
        pages = [
            _make_page(title="Article 1", summary="Summary 1"),
            _make_page(title="Article 2", summary="Summary 2"),
        ]
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response(pages))
        )

        collector = NotionMediumCollector(token="secret_test", medium_db_id="test-medium-db-id")
        results = await collector.collect("")

        assert len(results) == 2
        assert results[0].title == "Article 1"
        assert results[0].source == "notion_medium"

    @respx.mock
    async def test_japanese_title_preferred(self) -> None:
        """Japanese Titleがある場合はそちらが優先される。"""
        pages = [_make_page(title="Original", japanese_title="日本語タイトル")]
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response(pages))
        )

        collector = NotionMediumCollector(token="secret_test", medium_db_id="test-medium-db-id")
        results = await collector.collect("")

        assert results[0].title == "日本語タイトル"

    @respx.mock
    async def test_content_includes_author(self) -> None:
        """contentにAuthorが含まれる。"""
        pages = [_make_page(author="Jane Smith")]
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response(pages))
        )

        collector = NotionMediumCollector(token="secret_test", medium_db_id="test-medium-db-id")
        results = await collector.collect("")

        assert "Author: Jane Smith" in results[0].content

    @respx.mock
    async def test_filter_by_keyword(self) -> None:
        """キーワードでフィルタリングできる。"""
        pages = [
            _make_page(title="AI Agents", summary="Building agents"),
            _make_page(title="Web Design", summary="CSS tips"),
        ]
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response(pages))
        )

        collector = NotionMediumCollector(token="secret_test", medium_db_id="test-medium-db-id")
        results = await collector.collect("Agent")

        assert len(results) == 1
        assert results[0].title == "AI Agents"

    @respx.mock
    async def test_api_error_raises(self) -> None:
        """APIエラーでCollectionErrorが発生する。"""
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(403, json={"message": "Forbidden"})
        )

        collector = NotionMediumCollector(token="secret_test", medium_db_id="test-medium-db-id")
        with pytest.raises(CollectionError, match="403"):
            await collector.collect("")

    @respx.mock
    async def test_pagination(self) -> None:
        """ページネーションで全ページ取得できる。"""
        page1 = [_make_page(title="記事1")]
        page2 = [_make_page(title="記事2")]

        route = respx.post(NOTION_DB_QUERY_URL)
        route.side_effect = [
            Response(200, json=_make_query_response(page1, has_more=True, next_cursor="c1")),
            Response(200, json=_make_query_response(page2, has_more=False)),
        ]

        collector = NotionMediumCollector(token="secret_test", medium_db_id="test-medium-db-id")
        results = await collector.collect("")

        assert len(results) == 2

    @respx.mock
    async def test_empty_results(self) -> None:
        """結果が空の場合、空リストが返る。"""
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response([]))
        )

        collector = NotionMediumCollector(token="secret_test", medium_db_id="test-medium-db-id")
        results = await collector.collect("")

        assert results == []

    @respx.mock
    async def test_url_extracted(self) -> None:
        """URLが正しく抽出される。"""
        pages = [_make_page(url="https://medium.com/test-article")]
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response(pages))
        )

        collector = NotionMediumCollector(token="secret_test", medium_db_id="test-medium-db-id")
        results = await collector.collect("")

        assert results[0].url == "https://medium.com/test-article"

    @respx.mock
    async def test_date_from_to_filter(self) -> None:
        """date_from/date_toがAPIリクエストのフィルタに反映される。"""
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response([]))
        )

        collector = NotionMediumCollector(token="secret_test", medium_db_id="test-medium-db-id")
        await collector.collect("", date_from="2026-02-15", date_to="2026-02-22")

        request = respx.calls[0].request
        import json
        body = json.loads(request.content)
        and_filters = body["filter"]["and"]
        assert len(and_filters) == 2
        assert and_filters[0]["date"]["on_or_after"] == "2026-02-15"
        assert and_filters[1]["date"]["before"] == "2026-02-22"

    @respx.mock
    async def test_date_from_only(self) -> None:
        """date_fromのみ指定時、beforeは設定されない。"""
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response([]))
        )

        collector = NotionMediumCollector(token="secret_test", medium_db_id="test-medium-db-id")
        await collector.collect("", date_from="2026-02-15")

        request = respx.calls[0].request
        import json
        body = json.loads(request.content)
        date_filter = body["filter"]["date"]
        assert date_filter["on_or_after"] == "2026-02-15"
        assert "before" not in date_filter

    @respx.mock
    async def test_published_date_extracted(self) -> None:
        """published_dateがDateプロパティから設定される。"""
        pages = [_make_page()]
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response(pages))
        )

        collector = NotionMediumCollector(token="secret_test", medium_db_id="test-medium-db-id")
        results = await collector.collect("")

        assert results[0].published_date == "2026-02-15"
