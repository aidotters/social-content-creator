"""ブログ記事関連のデータモデル。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

type ContentType = Literal[
    "weekly-ai-news",
    "paper-review",
    "project-intro",
    "tool-tips",
    "market-analysis",
    "ml-practice",
    "cv",
    "feature",
]

type PostStatus = Literal["draft", "review", "ready", "published"]


class BlogPost(BaseModel):
    """ブログ記事のデータモデル。"""

    title: str
    subtitle: str | None = None
    content: str
    content_type: ContentType
    status: PostStatus = "draft"
    slug: str
    categories: list[str] = []
    tags: list[str] = []
    created_at: datetime
    published_at: datetime | None = None
    wordpress_id: int | None = None
    wordpress_url: str | None = None


class XPublishResult(BaseModel):
    """X投稿結果のデータモデル。"""

    success: bool
    tweet_id: str | None = None
    tweet_url: str | None = None
    thread_ids: list[str] = []
    error_message: str | None = None


class CollectedData(BaseModel):
    """情報収集結果のデータモデル。"""

    source: str
    title: str
    url: str | None = None
    content: str
    collected_at: datetime
    published_date: str | None = None


class PublishResult(BaseModel):
    """投稿結果のデータモデル。"""

    success: bool
    post_id: int | None = None
    url: str | None = None
    error_message: str | None = None
