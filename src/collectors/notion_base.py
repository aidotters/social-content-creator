"""Notion API共通基底クラス。"""

import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv

from src.errors import CollectionError

logger = logging.getLogger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionBaseCollector:
    """Notion Database Query APIの共通ロジックを提供する基底クラス。"""

    def __init__(self, token: str | None = None) -> None:
        load_dotenv()
        self._token = token or os.environ.get("NOTION_TOKEN", "")
        if not self._token:
            raise CollectionError(
                source="notion",
                message="NOTION_TOKENが未設定です。.envにNOTION_TOKENを設定してください。",
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    async def _query_database(
        self,
        client: httpx.AsyncClient,
        db_id: str,
        filter_obj: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """ページネーション対応のDatabase Queryを実行する。"""
        url = f"{NOTION_API_BASE}/databases/{db_id}/query"
        all_results: list[dict[str, Any]] = []
        start_cursor: str | None = None

        while True:
            body: dict[str, Any] = {}
            if filter_obj:
                body["filter"] = filter_obj
            if sorts:
                body["sorts"] = sorts
            if start_cursor:
                body["start_cursor"] = start_cursor

            response = await client.post(url, headers=self._headers(), json=body)
            if response.status_code != 200:
                raise CollectionError(
                    source="notion",
                    message=f"Notion API エラー (HTTP {response.status_code}): {response.text}",
                )

            data = response.json()
            results = data.get("results", [])
            all_results.extend(results)

            if data.get("has_more") and data.get("next_cursor"):
                start_cursor = data["next_cursor"]
            else:
                break

        return all_results

    @staticmethod
    def _extract_title(props: dict[str, Any], key: str) -> str:
        """titleプロパティからテキストを抽出する。"""
        prop = props.get(key, {})
        title_list = prop.get("title", [])
        if not title_list:
            return ""
        return "".join(item.get("plain_text", "") for item in title_list)

    @staticmethod
    def _extract_rich_text(props: dict[str, Any], key: str) -> str:
        """rich_textプロパティからテキストを抽出する。"""
        prop = props.get(key, {})
        rich_text_list = prop.get("rich_text", [])
        if not rich_text_list:
            return ""
        return "".join(item.get("plain_text", "") for item in rich_text_list)

    @staticmethod
    def _extract_url(props: dict[str, Any], key: str) -> str:
        """urlプロパティから値を抽出する。"""
        prop = props.get(key, {})
        return prop.get("url", "") or ""

    @staticmethod
    def _extract_date(props: dict[str, Any], key: str) -> str:
        """dateプロパティからstart日付を抽出する。"""
        prop = props.get(key, {})
        date_obj = prop.get("date")
        if not date_obj:
            return ""
        return date_obj.get("start", "") or ""

    @staticmethod
    def _extract_multi_select(props: dict[str, Any], key: str) -> list[str]:
        """multi_selectプロパティから名前のリストを抽出する。"""
        prop = props.get(key, {})
        options = prop.get("multi_select", [])
        return [opt.get("name", "") for opt in options if opt.get("name")]

    @staticmethod
    def _extract_number(props: dict[str, Any], key: str) -> float | None:
        """numberプロパティから値を抽出する。"""
        prop = props.get(key, {})
        value = prop.get("number")
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _extract_checkbox(props: dict[str, Any], key: str) -> bool:
        """checkboxプロパティから値を抽出する。"""
        prop = props.get(key, {})
        return bool(prop.get("checkbox", False))

    @staticmethod
    def _extract_select(props: dict[str, Any], key: str) -> str:
        """selectプロパティから名前を抽出する。"""
        prop = props.get(key, {})
        select = prop.get("select")
        if not select:
            return ""
        return select.get("name", "") or ""
