"""NotionBaseCollectorのテスト。"""

import pytest

from src.collectors.notion_base import NotionBaseCollector
from src.errors import CollectionError


class TestNotionBaseCollector:
    """NotionBaseCollectorのテスト。"""

    def test_init_with_token(self) -> None:
        """トークン指定で初期化できる。"""
        collector = NotionBaseCollector(token="secret_test")
        assert collector._token == "secret_test"

    def test_init_without_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """トークン未設定でCollectionErrorが発生する。"""
        monkeypatch.setenv("NOTION_TOKEN", "")
        with pytest.raises(CollectionError, match="NOTION_TOKEN"):
            NotionBaseCollector()

    def test_init_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """環境変数からトークンを取得できる。"""
        monkeypatch.setenv("NOTION_TOKEN", "secret_from_env")
        collector = NotionBaseCollector()
        assert collector._token == "secret_from_env"

    def test_headers(self) -> None:
        """ヘッダーが正しく生成される。"""
        collector = NotionBaseCollector(token="secret_test")
        headers = collector._headers()
        assert headers["Authorization"] == "Bearer secret_test"
        assert "Notion-Version" in headers

    def test_extract_title(self) -> None:
        """titleプロパティを抽出できる。"""
        props = {
            "Title": {
                "title": [
                    {"plain_text": "Hello "},
                    {"plain_text": "World"},
                ]
            }
        }
        assert NotionBaseCollector._extract_title(props, "Title") == "Hello World"

    def test_extract_title_empty(self) -> None:
        """空のtitleプロパティで空文字が返る。"""
        assert NotionBaseCollector._extract_title({}, "Title") == ""
        assert NotionBaseCollector._extract_title({"Title": {"title": []}}, "Title") == ""

    def test_extract_rich_text(self) -> None:
        """rich_textプロパティを抽出できる。"""
        props = {
            "Summary": {
                "rich_text": [{"plain_text": "テスト概要"}]
            }
        }
        assert NotionBaseCollector._extract_rich_text(props, "Summary") == "テスト概要"

    def test_extract_url(self) -> None:
        """urlプロパティを抽出できる。"""
        props = {"URL": {"url": "https://example.com"}}
        assert NotionBaseCollector._extract_url(props, "URL") == "https://example.com"

    def test_extract_url_none(self) -> None:
        """urlがnullの場合、空文字が返る。"""
        props = {"URL": {"url": None}}
        assert NotionBaseCollector._extract_url(props, "URL") == ""

    def test_extract_date(self) -> None:
        """dateプロパティを抽出できる。"""
        props = {"Date": {"date": {"start": "2026-02-17"}}}
        assert NotionBaseCollector._extract_date(props, "Date") == "2026-02-17"

    def test_extract_date_empty(self) -> None:
        """dateがnullの場合、空文字が返る。"""
        props = {"Date": {"date": None}}
        assert NotionBaseCollector._extract_date(props, "Date") == ""

    def test_extract_multi_select(self) -> None:
        """multi_selectプロパティを抽出できる。"""
        props = {
            "Tags": {
                "multi_select": [
                    {"name": "AI"},
                    {"name": "LLM"},
                ]
            }
        }
        assert NotionBaseCollector._extract_multi_select(props, "Tags") == ["AI", "LLM"]

    def test_extract_number(self) -> None:
        """numberプロパティを抽出できる。"""
        props = {"Claps": {"number": 42}}
        assert NotionBaseCollector._extract_number(props, "Claps") == 42

    def test_extract_checkbox(self) -> None:
        """checkboxプロパティを抽出できる。"""
        props = {"Done": {"checkbox": True}}
        assert NotionBaseCollector._extract_checkbox(props, "Done") is True

    def test_extract_select(self) -> None:
        """selectプロパティを抽出できる。"""
        props = {"Status": {"select": {"name": "Active"}}}
        assert NotionBaseCollector._extract_select(props, "Status") == "Active"

    def test_extract_select_none(self) -> None:
        """selectがnullの場合、空文字が返る。"""
        props = {"Status": {"select": None}}
        assert NotionBaseCollector._extract_select(props, "Status") == ""
