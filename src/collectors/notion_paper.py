"""Notion Arxiv論文 Collector。"""

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


class NotionPaperCollector(NotionBaseCollector):
    """Notion APIでArxiv論文データベースを直接クエリするCollector。"""

    def __init__(
        self, token: str | None = None, paper_db_id: str | None = None
    ) -> None:
        super().__init__(token=token)
        load_dotenv()
        self._db_id = paper_db_id or os.environ.get("NOTION_PAPER_DB_ID", "")
        if not self._db_id:
            raise CollectionError(
                source="notion_paper",
                message="NOTION_PAPER_DB_IDが未設定です。",
            )

    async def collect(self, query: str, **kwargs: object) -> list[CollectedData]:
        """Arxiv論文データを収集する。

        Args:
            query: フィルタキーワード（空文字で全件）
            **kwargs:
                days: 過去何日間のデータを対象にするか（デフォルト: 7）

        Returns:
            変換されたCollectedDataのリスト
        """
        days_val = kwargs.get("days", 7)
        days = int(days_val) if isinstance(days_val, (int, str)) else 7
        cutoff = datetime.now(UTC) - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        filter_obj: dict[str, Any] = {
            "property": "公開日",
            "date": {"on_or_after": cutoff_str},
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                pages = await self._query_database(
                    client,
                    self._db_id,
                    filter_obj=filter_obj,
                    sorts=[{"property": "公開日", "direction": "descending"}],
                )
        except CollectionError:
            raise
        except httpx.HTTPError as e:
            raise CollectionError(source="notion_paper", message=str(e)) from e

        collected: list[CollectedData] = []
        for page in pages:
            props = page.get("properties", {})

            title_raw = self._extract_title(props, "タイトル")
            japanese_title = self._extract_rich_text(props, "日本語訳")
            summary = self._extract_rich_text(props, "概要")
            url = self._extract_url(props, "URL")

            display_title = japanese_title or title_raw or "Untitled"

            if query:
                searchable = f"{title_raw} {japanese_title} {summary}".lower()
                if query.lower() not in searchable:
                    continue

            collected.append(
                CollectedData(
                    source="notion_paper",
                    title=display_title,
                    url=url or None,
                    content=summary,
                    collected_at=datetime.now(UTC),
                )
            )
        return collected
