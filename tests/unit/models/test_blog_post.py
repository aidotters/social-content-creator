"""BlogPost, CollectedData, PublishResult のテスト。"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.models.blog_post import BlogPost, CollectedData, PublishResult


class TestBlogPost:
    """BlogPostモデルのテスト。"""

    def test_create_with_required_fields(self) -> None:
        """必須フィールドで生成できる。"""
        post = BlogPost(
            title="テスト",
            content="コンテンツ",
            content_type="weekly-ai-news",
            slug="test",
            created_at=datetime.now(UTC),
        )
        assert post.title == "テスト"
        assert post.status == "draft"
        assert post.categories == []
        assert post.tags == []
        assert post.wordpress_id is None

    def test_create_with_all_fields(self) -> None:
        """全フィールド指定で生成できる。"""
        now = datetime.now(UTC)
        post = BlogPost(
            title="全フィールドテスト",
            content="コンテンツ",
            content_type="paper-review",
            status="published",
            slug="full-test",
            categories=["AI"],
            tags=["test"],
            created_at=now,
            published_at=now,
            wordpress_id=100,
            wordpress_url="https://example.com/blog/full-test",
        )
        assert post.content_type == "paper-review"
        assert post.status == "published"
        assert post.wordpress_id == 100

    def test_invalid_content_type_raises_error(self) -> None:
        """無効なcontent_typeでValidationErrorが発生する。"""
        with pytest.raises(ValidationError):
            BlogPost(
                title="テスト",
                content="コンテンツ",
                content_type="invalid-type",  # type: ignore[arg-type]
                slug="test",
                created_at=datetime.now(UTC),
            )

    def test_all_content_types_are_valid(self) -> None:
        """8種類すべてのcontent_typeが有効。"""
        types = [
            "weekly-ai-news",
            "paper-review",
            "project-intro",
            "tool-tips",
            "market-analysis",
            "ml-practice",
            "cv",
            "feature",
        ]
        for ct in types:
            post = BlogPost(
                title="テスト",
                content="コンテンツ",
                content_type=ct,  # type: ignore[arg-type]
                slug="test",
                created_at=datetime.now(UTC),
            )
            assert post.content_type == ct

    def test_create_with_subtitle(self) -> None:
        """subtitle付きで生成できる。"""
        post = BlogPost(
            title="メインタイトル",
            subtitle="サブタイトル補足情報",
            content="コンテンツ",
            content_type="weekly-ai-news",
            slug="test",
            created_at=datetime.now(UTC),
        )
        assert post.subtitle == "サブタイトル補足情報"

    def test_create_without_subtitle(self) -> None:
        """subtitleなしで生成できる（後方互換）。"""
        post = BlogPost(
            title="メインタイトル",
            content="コンテンツ",
            content_type="weekly-ai-news",
            slug="test",
            created_at=datetime.now(UTC),
        )
        assert post.subtitle is None


class TestCollectedData:
    """CollectedDataモデルのテスト。"""

    def test_create_with_url(self) -> None:
        """URL付きで生成できる。"""
        data = CollectedData(
            source="web",
            title="テスト",
            url="https://example.com",
            content="コンテンツ",
            collected_at=datetime.now(UTC),
        )
        assert data.url == "https://example.com"

    def test_create_without_url(self) -> None:
        """URLなしで生成できる。"""
        data = CollectedData(
            source="gemini",
            title="テスト",
            content="コンテンツ",
            collected_at=datetime.now(UTC),
        )
        assert data.url is None


class TestPublishResult:
    """PublishResultモデルのテスト。"""

    def test_success_result(self) -> None:
        """成功結果が生成できる。"""
        result = PublishResult(success=True, post_id=1, url="https://example.com/p/1")
        assert result.success is True
        assert result.post_id == 1

    def test_failure_result(self) -> None:
        """失敗結果が生成できる。"""
        result = PublishResult(success=False, error_message="認証失敗")
        assert result.success is False
        assert result.error_message == "認証失敗"
        assert result.post_id is None
