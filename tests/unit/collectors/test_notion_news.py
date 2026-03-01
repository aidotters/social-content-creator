"""NotionNewsCollectorのテスト。"""

import pytest
import respx
from httpx import Response

from src.collectors.notion_news import NotionNewsCollector
from src.errors import CollectionError

NOTION_DB_QUERY_URL = "https://api.notion.com/v1/databases/test-news-db-id/query"


def _make_page(
    title: str = "テストニュース",
    summary: str = "テスト概要",
    source: str = "TechCrunch",
    tags: list[str] | None = None,
    url: str = "https://example.com/news",
    date: str = "2026-02-18",
) -> dict:
    """テスト用のNotionページデータを生成する。"""
    return {
        "properties": {
            "Title": {"title": [{"plain_text": title}]},
            "Original Title": {"rich_text": [{"plain_text": f"EN: {title}"}]},
            "Summary": {"rich_text": [{"plain_text": summary}]},
            "Snippet": {"rich_text": [{"plain_text": "snippet text"}]},
            "Source": {"rich_text": [{"plain_text": source}]},
            "Tags": {
                "multi_select": [{"name": t} for t in (tags or ["AI"])]
            },
            "URL": {"url": url},
            "Date": {"date": {"start": date}},
        },
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


class TestNotionNewsCollector:
    """NotionNewsCollectorのテスト。"""

    def test_init_without_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """トークン未設定でCollectionErrorが発生する。"""
        monkeypatch.setenv("NOTION_TOKEN", "")
        with pytest.raises(CollectionError, match="NOTION_TOKEN"):
            NotionNewsCollector(news_db_id="test-db")

    def test_init_without_db_id_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DB ID未設定でCollectionErrorが発生する。"""
        monkeypatch.setenv("NOTION_NEWS_DB_ID", "")
        with pytest.raises(CollectionError, match="NOTION_NEWS_DB_ID"):
            NotionNewsCollector(token="secret_test")

    @respx.mock
    async def test_collect_recent_news(self) -> None:
        """最近のニュースが取得できる。"""
        pages = [
            _make_page(title="AIニュース1", summary="最新のAI動向"),
            _make_page(title="AIニュース2", summary="新しいモデルの発表"),
        ]
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response(pages))
        )

        collector = NotionNewsCollector(token="secret_test", news_db_id="test-news-db-id")
        results = await collector.collect("")

        assert len(results) == 2
        assert results[0].title == "AIニュース1"
        assert results[0].source == "notion_news"
        assert "最新のAI動向" in results[0].content

    @respx.mock
    async def test_filter_by_keyword(self) -> None:
        """キーワードでフィルタリングできる。"""
        pages = [
            _make_page(title="LLMの進化", summary="大規模言語モデル"),
            _make_page(title="ロボット工学", summary="自律走行"),
        ]
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response(pages))
        )

        collector = NotionNewsCollector(token="secret_test", news_db_id="test-news-db-id")
        results = await collector.collect("LLM")

        assert len(results) == 1
        assert results[0].title == "LLMの進化"

    @respx.mock
    async def test_content_includes_source_and_tags(self) -> None:
        """contentにSource・Tagsが含まれる。"""
        pages = [_make_page(source="TheVerge", tags=["AI", "LLM"])]
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response(pages))
        )

        collector = NotionNewsCollector(token="secret_test", news_db_id="test-news-db-id")
        results = await collector.collect("")

        assert "Source: TheVerge" in results[0].content
        assert "Tags: AI, LLM" in results[0].content

    @respx.mock
    async def test_url_extracted(self) -> None:
        """URLが正しく抽出される。"""
        pages = [_make_page(url="https://example.com/article")]
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response(pages))
        )

        collector = NotionNewsCollector(token="secret_test", news_db_id="test-news-db-id")
        results = await collector.collect("")

        assert results[0].url == "https://example.com/article"

    @respx.mock
    async def test_api_error_raises(self) -> None:
        """APIエラーでCollectionErrorが発生する。"""
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(401, json={"message": "Unauthorized"})
        )

        collector = NotionNewsCollector(token="secret_test", news_db_id="test-news-db-id")
        with pytest.raises(CollectionError, match="401"):
            await collector.collect("")

    @respx.mock
    async def test_pagination(self) -> None:
        """ページネーションで全ページ取得できる。"""
        page1 = [_make_page(title="ニュース1")]
        page2 = [_make_page(title="ニュース2")]

        route = respx.post(NOTION_DB_QUERY_URL)
        route.side_effect = [
            Response(200, json=_make_query_response(page1, has_more=True, next_cursor="cursor1")),
            Response(200, json=_make_query_response(page2, has_more=False)),
        ]

        collector = NotionNewsCollector(token="secret_test", news_db_id="test-news-db-id")
        results = await collector.collect("")

        assert len(results) == 2
        assert results[0].title == "ニュース1"
        assert results[1].title == "ニュース2"

    @respx.mock
    async def test_empty_results(self) -> None:
        """結果が空の場合、空リストが返る。"""
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response([]))
        )

        collector = NotionNewsCollector(token="secret_test", news_db_id="test-news-db-id")
        results = await collector.collect("")

        assert results == []

    @respx.mock
    async def test_days_filter_sent_in_request(self) -> None:
        """daysパラメータがAPIリクエストのフィルタに反映される。"""
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response([]))
        )

        collector = NotionNewsCollector(token="secret_test", news_db_id="test-news-db-id")
        await collector.collect("", days=3)

        request = respx.calls[0].request
        import json
        body = json.loads(request.content)
        assert body["filter"]["property"] == "Date"
        assert "on_or_after" in body["filter"]["date"]

    @respx.mock
    async def test_date_from_to_filter(self) -> None:
        """date_from/date_toがcompound filterとしてリクエストに反映される。"""
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response([]))
        )

        collector = NotionNewsCollector(token="secret_test", news_db_id="test-news-db-id")
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
        """date_fromのみ指定時、単一フィルタが送信される。"""
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response([]))
        )

        collector = NotionNewsCollector(token="secret_test", news_db_id="test-news-db-id")
        await collector.collect("", date_from="2026-02-15")

        request = respx.calls[0].request
        import json
        body = json.loads(request.content)
        assert body["filter"]["property"] == "Date"
        assert body["filter"]["date"]["on_or_after"] == "2026-02-15"
        assert "and" not in body["filter"]

    @respx.mock
    async def test_published_date_extracted(self) -> None:
        """published_dateがDateプロパティから設定される。"""
        pages = [_make_page(date="2026-02-18")]
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response(pages))
        )

        collector = NotionNewsCollector(token="secret_test", news_db_id="test-news-db-id")
        results = await collector.collect("")

        assert results[0].published_date == "2026-02-18"

    @respx.mock
    async def test_sort_by_date_descending(self) -> None:
        """Date降順でソートされる。"""
        respx.post(NOTION_DB_QUERY_URL).mock(
            return_value=Response(200, json=_make_query_response([]))
        )

        collector = NotionNewsCollector(token="secret_test", news_db_id="test-news-db-id")
        await collector.collect("")

        request = respx.calls[0].request
        import json
        body = json.loads(request.content)
        assert body["sorts"] == [{"property": "Date", "direction": "descending"}]
