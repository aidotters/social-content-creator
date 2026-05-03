"""WordPressPublisherのテスト。"""

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx as respx_lib

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

    async def test_publish_draft_resolves_permalink_from_slug(
        self, publisher: WordPressPublisher, blog_post: BlogPost, respx_mock: object
    ) -> None:
        """下書き投稿時に?p=形式のlinkがスラッグベースのパーマリンクに変換される。"""
        import respx as respx_lib

        respx_lib.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": 45,
                    "link": "https://example.com/?p=45",
                    "slug": "my-draft-post",
                },
            )
        )

        result = await publisher.publish(blog_post, status="draft")

        assert result.success is True
        assert result.post_id == 45
        assert result.url == "https://example.com/my-draft-post/"

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
        update_route = respx_lib.post("https://example.com/wp-json/wp/v2/posts/50").mock(
            return_value=httpx.Response(200, json={"id": 50})
        )

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


def _make_image_file(directory: Path, name: str = "thumb.png") -> Path:
    """テスト用のダミー画像ファイル（PNG ヘッダ）を生成する。"""
    path = directory / name
    # PNG signature + minimal data。MIME 推定とアップロード bytes 用。
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    return path


class TestUploadMedia:
    """upload_media() のテスト。"""

    async def test_upload_media_success(
        self,
        publisher: WordPressPublisher,
        tmp_path: Path,
        respx_mock: object,
    ) -> None:
        """画像をアップロードして media_id が返る。"""
        image = _make_image_file(tmp_path)

        create_route = respx_lib.post("https://example.com/wp-json/wp/v2/media").mock(
            return_value=httpx.Response(201, json={"id": 99, "alt_text": ""})
        )
        update_route = respx_lib.post("https://example.com/wp-json/wp/v2/media/99").mock(
            return_value=httpx.Response(200, json={"id": 99, "alt_text": "alt"})
        )

        media_id = await publisher.upload_media(image_path=image, alt_text="alt", title="title")

        assert media_id == 99
        assert create_route.call_count == 1
        assert update_route.call_count == 1

        update_payload = json.loads(update_route.calls[0].request.content)
        assert update_payload["alt_text"] == "alt"
        assert update_payload["title"] == "title"

    async def test_upload_media_moves_file_to_archive(
        self,
        publisher: WordPressPublisher,
        tmp_path: Path,
        respx_mock: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """成功時にファイルが outputs/images/archive/ に移動される。"""
        archive_root = tmp_path / "archive"
        monkeypatch.setattr("src.publishers.wordpress._MEDIA_ARCHIVE_DIR", archive_root)
        image = _make_image_file(tmp_path, name="hero.png")

        respx_lib.post("https://example.com/wp-json/wp/v2/media").mock(
            return_value=httpx.Response(201, json={"id": 11})
        )
        respx_lib.post("https://example.com/wp-json/wp/v2/media/11").mock(
            return_value=httpx.Response(200, json={"id": 11})
        )

        await publisher.upload_media(image_path=image, alt_text="alt")

        assert not image.exists()
        assert (archive_root / "hero.png").exists()

    async def test_upload_media_file_not_found(
        self,
        publisher: WordPressPublisher,
        tmp_path: Path,
        respx_mock: object,
    ) -> None:
        """ファイル不在時に WordPressPublishError、API は呼ばれない。"""
        missing = tmp_path / "missing.png"

        api_route = respx_lib.post("https://example.com/wp-json/wp/v2/media").mock(
            return_value=httpx.Response(201, json={"id": 1})
        )

        with pytest.raises(WordPressPublishError, match="画像ファイルが存在しません"):
            await publisher.upload_media(image_path=missing, alt_text="alt")

        assert api_route.call_count == 0

    async def test_upload_media_unsupported_extension(
        self,
        publisher: WordPressPublisher,
        tmp_path: Path,
        respx_mock: object,
    ) -> None:
        """未サポート拡張子で WordPressPublishError、API は呼ばれない。"""
        bad = tmp_path / "note.txt"
        bad.write_text("not an image")

        api_route = respx_lib.post("https://example.com/wp-json/wp/v2/media").mock(
            return_value=httpx.Response(201, json={"id": 1})
        )

        with pytest.raises(WordPressPublishError, match="サポートされていない画像形式"):
            await publisher.upload_media(image_path=bad, alt_text="alt")

        assert api_route.call_count == 0

    async def test_upload_media_401(
        self,
        publisher: WordPressPublisher,
        tmp_path: Path,
        respx_mock: object,
    ) -> None:
        """401 で WordPressPublishError(status_code=401)。"""
        image = _make_image_file(tmp_path)

        respx_lib.post("https://example.com/wp-json/wp/v2/media").mock(
            return_value=httpx.Response(401, json={"message": "Unauthorized"})
        )

        with pytest.raises(WordPressPublishError) as exc_info:
            await publisher.upload_media(image_path=image, alt_text="alt")
        assert exc_info.value.status_code == 401

    async def test_upload_media_metadata_update_failure(
        self,
        publisher: WordPressPublisher,
        tmp_path: Path,
        respx_mock: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """メタデータ更新（2段階目POST）失敗時に media_id= を含むエラー、ファイルは元の場所。"""
        archive_root = tmp_path / "archive"
        monkeypatch.setattr("src.publishers.wordpress._MEDIA_ARCHIVE_DIR", archive_root)
        image = _make_image_file(tmp_path)

        respx_lib.post("https://example.com/wp-json/wp/v2/media").mock(
            return_value=httpx.Response(201, json={"id": 77})
        )
        respx_lib.post("https://example.com/wp-json/wp/v2/media/77").mock(
            return_value=httpx.Response(500, json={"message": "Internal Error"})
        )

        with pytest.raises(WordPressPublishError, match="media_id=77"):
            await publisher.upload_media(image_path=image, alt_text="alt")

        # メタデータ更新失敗時はファイルがアーカイブへ移動されていない
        assert image.exists()


class TestSetFeaturedMedia:
    """set_featured_media() のテスト。"""

    async def test_set_featured_media_success_when_no_existing(
        self,
        publisher: WordPressPublisher,
        respx_mock: object,
    ) -> None:
        """既存 featured_media=0 で設定成功。"""
        respx_lib.get("https://example.com/wp-json/wp/v2/posts/12").mock(
            return_value=httpx.Response(200, json={"id": 12, "featured_media": 0})
        )
        update_route = respx_lib.post("https://example.com/wp-json/wp/v2/posts/12").mock(
            return_value=httpx.Response(200, json={"id": 12, "featured_media": 99})
        )

        await publisher.set_featured_media(post_id=12, media_id=99)

        assert update_route.call_count == 1
        payload = json.loads(update_route.calls[0].request.content)
        assert payload["featured_media"] == 99

    async def test_set_featured_media_overrides_with_force(
        self,
        publisher: WordPressPublisher,
        respx_mock: object,
    ) -> None:
        """force=True で既存ありでも上書き、GET は省略される。"""
        get_route = respx_lib.get("https://example.com/wp-json/wp/v2/posts/12").mock(
            return_value=httpx.Response(200, json={"id": 12, "featured_media": 50})
        )
        update_route = respx_lib.post("https://example.com/wp-json/wp/v2/posts/12").mock(
            return_value=httpx.Response(200, json={"id": 12})
        )

        await publisher.set_featured_media(post_id=12, media_id=99, force=True)

        assert get_route.call_count == 0
        assert update_route.call_count == 1

    async def test_set_featured_media_rejects_existing_without_force(
        self,
        publisher: WordPressPublisher,
        respx_mock: object,
    ) -> None:
        """既存ありで force=False の場合 WordPressPublishError、更新APIは呼ばれない。"""
        respx_lib.get("https://example.com/wp-json/wp/v2/posts/12").mock(
            return_value=httpx.Response(200, json={"id": 12, "featured_media": 50})
        )
        update_route = respx_lib.post("https://example.com/wp-json/wp/v2/posts/12").mock(
            return_value=httpx.Response(200, json={"id": 12})
        )

        with pytest.raises(WordPressPublishError, match="--force"):
            await publisher.set_featured_media(post_id=12, media_id=99)

        assert update_route.call_count == 0

    async def test_set_featured_media_api_error(
        self,
        publisher: WordPressPublisher,
        respx_mock: object,
    ) -> None:
        """更新POST失敗時に WordPressPublishError、メッセージに media_id= を含む。"""
        respx_lib.get("https://example.com/wp-json/wp/v2/posts/12").mock(
            return_value=httpx.Response(200, json={"id": 12, "featured_media": 0})
        )
        respx_lib.post("https://example.com/wp-json/wp/v2/posts/12").mock(
            return_value=httpx.Response(500, json={"message": "Internal Error"})
        )

        with pytest.raises(WordPressPublishError, match="media_id=99"):
            await publisher.set_featured_media(post_id=12, media_id=99)


class TestGetPost:
    """get_post() のテスト。"""

    async def test_get_post_success(
        self,
        publisher: WordPressPublisher,
        respx_mock: object,
    ) -> None:
        """GETでレスポンスdictが返る。"""
        respx_lib.get("https://example.com/wp-json/wp/v2/posts/7").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": 7,
                    "title": {"rendered": "タイトル"},
                    "content": {"rendered": "<p>本文</p>"},
                    "featured_media": 0,
                },
            )
        )

        result = await publisher.get_post(post_id=7)

        assert result["id"] == 7
        assert isinstance(result["title"], dict)

    async def test_get_post_404(
        self,
        publisher: WordPressPublisher,
        respx_mock: object,
    ) -> None:
        """404 で WordPressPublishError。"""
        respx_lib.get("https://example.com/wp-json/wp/v2/posts/999").mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )

        with pytest.raises(WordPressPublishError) as exc_info:
            await publisher.get_post(post_id=999)
        assert exc_info.value.status_code == 404


class TestPublishWithFeaturedImage:
    """publish() のアイキャッチ画像連携テスト。"""

    async def test_publish_with_featured_image_uploads_then_posts(
        self,
        publisher: WordPressPublisher,
        blog_post: BlogPost,
        tmp_path: Path,
        respx_mock: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """featured_image_path 指定時、media→posts の順で payload が featured_media を含む。"""
        archive_root = tmp_path / "archive"
        monkeypatch.setattr("src.publishers.wordpress._MEDIA_ARCHIVE_DIR", archive_root)
        image = _make_image_file(tmp_path)

        media_route = respx_lib.post("https://example.com/wp-json/wp/v2/media").mock(
            return_value=httpx.Response(201, json={"id": 200})
        )
        media_update_route = respx_lib.post("https://example.com/wp-json/wp/v2/media/200").mock(
            return_value=httpx.Response(200, json={"id": 200})
        )
        post_route = respx_lib.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(
                201,
                json={"id": 60, "link": "https://example.com/blog/test-post"},
            )
        )

        result = await publisher.publish(
            blog_post,
            status="publish",
            featured_image_path=image,
            featured_image_alt="Custom alt",
        )

        assert result.success is True
        assert result.post_id == 60
        assert media_route.call_count == 1
        assert media_update_route.call_count == 1
        assert post_route.call_count == 1

        media_update_payload = json.loads(media_update_route.calls[0].request.content)
        assert media_update_payload["alt_text"] == "Custom alt"

        post_payload = json.loads(post_route.calls[0].request.content)
        assert post_payload["featured_media"] == 200

    async def test_publish_with_featured_image_uses_title_as_alt_when_not_specified(
        self,
        publisher: WordPressPublisher,
        blog_post: BlogPost,
        tmp_path: Path,
        respx_mock: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """featured_image_alt 未指定時は post.title が alt_text に使われる。"""
        archive_root = tmp_path / "archive"
        monkeypatch.setattr("src.publishers.wordpress._MEDIA_ARCHIVE_DIR", archive_root)
        image = _make_image_file(tmp_path)

        respx_lib.post("https://example.com/wp-json/wp/v2/media").mock(
            return_value=httpx.Response(201, json={"id": 201})
        )
        media_update_route = respx_lib.post("https://example.com/wp-json/wp/v2/media/201").mock(
            return_value=httpx.Response(200, json={"id": 201})
        )
        respx_lib.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(
                201, json={"id": 61, "link": "https://example.com/blog/test"}
            )
        )

        await publisher.publish(blog_post, featured_image_path=image)

        media_update_payload = json.loads(media_update_route.calls[0].request.content)
        assert media_update_payload["alt_text"] == blog_post.title

    async def test_publish_with_featured_image_post_failure_includes_media_id(
        self,
        publisher: WordPressPublisher,
        blog_post: BlogPost,
        tmp_path: Path,
        respx_mock: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """アップロード成功 → posts 作成失敗時、エラーメッセージに media_id= が含まれる。"""
        archive_root = tmp_path / "archive"
        monkeypatch.setattr("src.publishers.wordpress._MEDIA_ARCHIVE_DIR", archive_root)
        image = _make_image_file(tmp_path)

        respx_lib.post("https://example.com/wp-json/wp/v2/media").mock(
            return_value=httpx.Response(201, json={"id": 300})
        )
        respx_lib.post("https://example.com/wp-json/wp/v2/media/300").mock(
            return_value=httpx.Response(200, json={"id": 300})
        )
        respx_lib.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(500, json={"message": "Internal"})
        )

        with pytest.raises(WordPressPublishError, match="media_id=300"):
            await publisher.publish(blog_post, featured_image_path=image)

    async def test_publish_without_featured_image_keeps_legacy_behavior(
        self,
        publisher: WordPressPublisher,
        blog_post: BlogPost,
        respx_mock: object,
    ) -> None:
        """featured_image_path=None で payload に featured_media を含めない。"""
        post_route = respx_lib.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(
                201, json={"id": 62, "link": "https://example.com/blog/test"}
            )
        )

        await publisher.publish(blog_post)

        payload = json.loads(post_route.calls[0].request.content)
        assert "featured_media" not in payload
