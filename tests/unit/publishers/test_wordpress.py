"""WordPressPublisherのテスト。"""

from datetime import UTC, datetime

import httpx
import pytest

from src.errors import WordPressPublishError
from src.models.blog_post import BlogPost
from src.publishers.wordpress import WordPressPublisher


@pytest.fixture
def publisher() -> WordPressPublisher:
    return WordPressPublisher(
        base_url="https://example.com",
        username="testuser",
        app_password="testpass",
    )


@pytest.fixture
def blog_post() -> BlogPost:
    return BlogPost(
        title="テスト投稿",
        content="<p>テストコンテンツ</p>",
        content_type="weekly-ai-news",
        slug="test-post",
        created_at=datetime(2026, 2, 13, tzinfo=UTC),
    )


class TestWordPressPublisherInit:
    """WordPressPublisher初期化のテスト。"""

    def test_missing_url_raises_value_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """WORDPRESS_URLが未設定の場合にValueErrorが発生する。"""
        monkeypatch.delenv("WORDPRESS_URL", raising=False)
        monkeypatch.delenv("WORDPRESS_USER", raising=False)
        monkeypatch.delenv("WORDPRESS_APP_PASSWORD", raising=False)
        monkeypatch.setattr("src.publishers.wordpress.load_dotenv", lambda: None)
        with pytest.raises(ValueError, match="WORDPRESS_URL"):
            WordPressPublisher()

    def test_missing_all_raises_value_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """全認証情報が未設定の場合に全項目がエラーメッセージに含まれる。"""
        monkeypatch.delenv("WORDPRESS_URL", raising=False)
        monkeypatch.delenv("WORDPRESS_USER", raising=False)
        monkeypatch.delenv("WORDPRESS_APP_PASSWORD", raising=False)
        monkeypatch.setattr("src.publishers.wordpress.load_dotenv", lambda: None)
        pattern = "WORDPRESS_URL.*WORDPRESS_USER.*WORDPRESS_APP_PASSWORD"
        with pytest.raises(ValueError, match=pattern):
            WordPressPublisher()

    def test_valid_args_no_error(self) -> None:
        """有効な引数が渡された場合にエラーが発生しない。"""
        publisher = WordPressPublisher(
            base_url="https://example.com",
            username="user",
            app_password="pass",
        )
        assert publisher._base_url == "https://example.com"


class TestWordPressPublisher:
    """WordPressPublisherのテスト。"""

    async def test_publish_draft_success(
        self, publisher: WordPressPublisher, blog_post: BlogPost, respx_mock: object
    ) -> None:
        """下書き投稿が成功する。"""
        import respx as respx_lib

        respx_lib.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": 42,
                    "link": "https://example.com/blog/test-post",
                },
            )
        )

        result = await publisher.publish(blog_post, status="draft")

        assert result.success is True
        assert result.post_id == 42
        assert result.url == "https://example.com/blog/test-post"

    async def test_publish_with_publish_status(
        self, publisher: WordPressPublisher, blog_post: BlogPost, respx_mock: object
    ) -> None:
        """公開投稿が成功する。"""
        import respx as respx_lib

        respx_lib.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": 43,
                    "link": "https://example.com/blog/test-post",
                },
            )
        )

        result = await publisher.publish(blog_post, status="publish")
        assert result.success is True

    async def test_publish_with_categories_and_tags(
        self, publisher: WordPressPublisher, blog_post: BlogPost, respx_mock: object
    ) -> None:
        """カテゴリ・タグ付き投稿が成功する。"""
        import respx as respx_lib

        respx_lib.get("https://example.com/wp-json/wp/v2/categories").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": 1, "name": "AI"},
                    {"id": 2, "name": "Tech"},
                ],
            )
        )
        respx_lib.get("https://example.com/wp-json/wp/v2/tags").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": 10, "name": "python"},
                ],
            )
        )
        respx_lib.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": 44,
                    "link": "https://example.com/blog/test",
                },
            )
        )

        result = await publisher.publish(blog_post, categories=["AI"], tags=["python"])
        assert result.success is True

    async def test_publish_with_subtitle_includes_excerpt(
        self, publisher: WordPressPublisher, respx_mock: object
    ) -> None:
        """subtitle付き投稿でexcerptが設定され、続きを読むリンク付きで更新される。"""
        import respx as respx_lib

        post = BlogPost(
            title="サブタイトル付き投稿",
            subtitle="補足サブタイトル",
            content="<p>コンテンツ</p>",
            content_type="weekly-ai-news",
            slug="subtitle-test",
            created_at=datetime(2026, 2, 13, tzinfo=UTC),
        )

        create_route = respx_lib.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(
                201,
                json={"id": 50, "link": "https://example.com/blog/subtitle-test"},
            )
        )
        update_route = respx_lib.post(
            "https://example.com/wp-json/wp/v2/posts/50"
        ).mock(return_value=httpx.Response(200, json={"id": 50}))

        result = await publisher.publish(post, status="draft")
        assert result.success is True

        import json

        create_payload = json.loads(create_route.calls[0].request.content)
        assert create_payload["excerpt"] == "補足サブタイトル"

        update_payload = json.loads(update_route.calls[0].request.content)
        assert "補足サブタイトル" in update_payload["excerpt"]
        assert "続きを読む" in update_payload["excerpt"]
        assert "more-link" in update_payload["excerpt"]

    async def test_publish_without_subtitle_excludes_excerpt(
        self, publisher: WordPressPublisher, blog_post: BlogPost, respx_mock: object
    ) -> None:
        """subtitleなし投稿でpayloadにexcerptが含まれない。"""
        import respx as respx_lib

        route = respx_lib.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(
                201,
                json={"id": 51, "link": "https://example.com/blog/test-post"},
            )
        )

        result = await publisher.publish(blog_post, status="draft")
        assert result.success is True

        import json

        payload = json.loads(route.calls[0].request.content)
        assert "excerpt" not in payload

    async def test_publish_auth_error(
        self, publisher: WordPressPublisher, blog_post: BlogPost, respx_mock: object
    ) -> None:
        """認証エラー時にWordPressPublishErrorが発生する。"""
        import respx as respx_lib

        respx_lib.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(401, json={"message": "Unauthorized"})
        )

        with pytest.raises(WordPressPublishError, match="認証に失敗"):
            await publisher.publish(blog_post)

    async def test_publish_server_error(
        self, publisher: WordPressPublisher, blog_post: BlogPost, respx_mock: object
    ) -> None:
        """サーバーエラー時にWordPressPublishErrorが発生する。"""
        import respx as respx_lib

        respx_lib.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(500, json={"message": "Internal Server Error"})
        )

        with pytest.raises(WordPressPublishError):
            await publisher.publish(blog_post)

    async def test_get_categories_invalid_json(
        self, publisher: WordPressPublisher, respx_mock: object
    ) -> None:
        """get_categories()で不正JSONが返された場合にWordPressPublishErrorが発生する。"""
        import respx as respx_lib

        respx_lib.get("https://example.com/wp-json/wp/v2/categories").mock(
            return_value=httpx.Response(
                200, content=b"not json", headers={"content-type": "text/plain"}
            )
        )

        with pytest.raises(WordPressPublishError, match="カテゴリ一覧の解析に失敗"):
            await publisher.get_categories()

    async def test_get_tags_invalid_json(
        self, publisher: WordPressPublisher, respx_mock: object
    ) -> None:
        """get_tags()で不正JSONが返された場合にWordPressPublishErrorが発生する。"""
        import respx as respx_lib

        respx_lib.get("https://example.com/wp-json/wp/v2/tags").mock(
            return_value=httpx.Response(
                200, content=b"not json", headers={"content-type": "text/plain"}
            )
        )

        with pytest.raises(WordPressPublishError, match="タグ一覧の解析に失敗"):
            await publisher.get_tags()
