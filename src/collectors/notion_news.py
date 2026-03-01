"""Notion Google Alertニュース Collector。"""

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from dotenv import load_dotenv

from src.collectors.notion_base import NotionBaseCollector
from src.errors import CollectionError
from src.models.blog_post import CollectedData

logger = logging.getLogger(__name__)


class NotionNewsCollector(NotionBaseCollector):
    """Notion APIでGoogle Alertニュースデータベースを直接クエリするCollector。"""

    def __init__(
        self, token: str | None = None, news_db_id: str | None = None
    ) -> None:
        super().__init__(token=token)
        load_dotenv()
        self._db_id = news_db_id or os.environ.get("NOTION_NEWS_DB_ID", "")
        if not self._db_id:
            raise CollectionError(
                source="notion_news",
                message="NOTION_NEWS_DB_IDが未設定です。",
            )

    async def collect(self, query: str, **kwargs: object) -> list[CollectedData]:
        """Google Alertニュースを収集する。

        Args:
            query: フィルタキーワード（空文字で全件）
            **kwargs:
                days: 過去何日間のデータを対象にするか（デフォルト: 7）
                date_from: 開始日（YYYY-MM-DD文字列、指定時はdaysより優先）
                date_to: 終了日（YYYY-MM-DD文字列、指定時はdaysより優先）

        Returns:
            変換されたCollectedDataのリスト
        """
        date_from = kwargs.get("date_from")
        date_to = kwargs.get("date_to")

        if isinstance(date_from, str) and date_from:
            on_or_after = date_from
        else:
            days_val = kwargs.get("days", 7)
            days = int(days_val) if isinstance(days_val, (int, str)) else 7
            cutoff = datetime.now(UTC) - timedelta(days=days)
            on_or_after = cutoff.strftime("%Y-%m-%d")

        on_or_after_filter: dict[str, Any] = {
            "property": "Date",
            "date": {"on_or_after": on_or_after},
        }

        if isinstance(date_to, str) and date_to:
            before_filter: dict[str, Any] = {
                "property": "Date",
                "date": {"before": date_to},
            }
            filter_obj: dict[str, Any] = {
                "and": [on_or_after_filter, before_filter],
            }
        else:
            filter_obj = on_or_after_filter

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                pages = await self._query_database(
                    client,
                    self._db_id,
                    filter_obj=filter_obj,
                    sorts=[{"property": "Date", "direction": "descending"}],
                )
        except CollectionError:
            raise
        except httpx.HTTPError as e:
            raise CollectionError(source="notion_news", message=str(e)) from e

        collected: list[CollectedData] = []
        for page in pages:
            props = page.get("properties", {})

            title = self._extract_title(props, "Title")
            original_title = self._extract_rich_text(props, "Original Title")
            summary = self._extract_rich_text(props, "Summary")
            snippet = self._extract_rich_text(props, "Snippet")
            source = self._extract_rich_text(props, "Source")
            tags = self._extract_multi_select(props, "Tags")
            url = self._extract_url(props, "URL")
            published_date = self._extract_date(props, "Date") or None

            display_title = title or original_title or "Untitled"

            if query:
                searchable = f"{display_title} {summary} {snippet}".lower()
                if query.lower() not in searchable:
                    continue

            content_parts = []
            if summary:
                content_parts.append(summary)
            if source:
                content_parts.append(f"Source: {source}")
            if tags:
                content_parts.append(f"Tags: {', '.join(tags)}")

            collected.append(
                CollectedData(
                    source="notion_news",
                    title=display_title,
                    url=url or None,
                    content="\n".join(content_parts),
                    collected_at=datetime.now(UTC),
                    published_date=published_date,
                )
            )
        return collected
