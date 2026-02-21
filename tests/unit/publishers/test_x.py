"""XPublisherのテスト。"""

from datetime import UTC, datetime

import httpx
import pytest
import pytest_mock
import respx

from src.errors import XPublishError
from src.models.blog_post import BlogPost
from src.publishers.x import MAX_TWEET_LENGTH, X_API_BASE, XPublisher


@pytest.fixture
def publisher() -> XPublisher:
    return XPublisher(
        api_key="test-key",
        api_secret="test-secret",
        access_token="test-token",
        access_token_secret="test-token-secret",
    )


@pytest.fixture
def blog_post() -> BlogPost:
    return BlogPost(
        title="テスト投稿",
        content="テストコンテンツ",
        content_type="weekly-ai-news",
        slug="test-post",
        created_at=datetime(2026, 2, 16, tzinfo=UTC),
        wordpress_url="https://example.com/blog/test-post",
    )


def _tweet_response(tweet_id: str = "123456") -> httpx.Response:
    return httpx.Response(
        201,
        json={"data": {"id": tweet_id}},
    )


class TestXPublisherInit:
    """XPublisher初期化のテスト。"""

    def test_missing_token_raises_value_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OAuth 1.0aキーが未設定の場合にValueErrorが発生する。"""
        monkeypatch.delenv("X_API_KEY", raising=False)
        monkeypatch.delenv("X_API_SECRET", raising=False)
        monkeypatch.delenv("X_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("X_ACCESS_TOKEN_SECRET", raising=False)
        monkeypatch.setattr("src.publishers.x.load_dotenv", lambda: None)
        with pytest.raises(ValueError, match="X_API_KEY"):
            XPublisher()

    def test_constructor_arg_no_error(self) -> None:
        """コンストラクタ引数でトークンを渡せる。"""
        publisher = XPublisher(
            api_key="k",
            api_secret="s",
            access_token="t",
            access_token_secret="ts",
        )
        assert publisher._api_key == "k"
        assert publisher._api_secret == "s"
        assert publisher._access_token == "t"
        assert publisher._access_token_secret == "ts"


class TestWeightedLength:
    """加重文字数計算のテスト。"""

    def test_ascii_only(self, publisher: XPublisher) -> None:
        """ASCII文字は1文字=1カウント。"""
        assert publisher.weighted_length("hello") == 5

    def test_japanese_double_weight(self, publisher: XPublisher) -> None:
        """日本語は1文字=2カウント。"""
        assert publisher.weighted_length("あいう") == 6

    def test_emoji_double_weight(self, publisher: XPublisher) -> None:
        """絵文字は1文字=2カウント。"""
        assert publisher.weighted_length("🔥") == 2

    def test_url_fixed_23(self, publisher: XPublisher) -> None:
        """URLはt.co短縮で23文字固定。"""
        assert publisher.weighted_length("https://example.com/long/path") == 23

    def test_mixed_text(self, publisher: XPublisher) -> None:
        """混合テキストの加重文字数計算。"""
        # "Hi " (3) + "あ" (2) + " " (1) + URL (23) = 29
        assert publisher.weighted_length("Hi あ https://example.com") == 29


class TestValidateText:
    """文字数バリデーションのテスト（加重文字数）。"""

    def test_valid_text(self, publisher: XPublisher) -> None:
        """280加重文字以内のテキストはエラーなし。"""
        publisher.validate_text("Hello World")

    def test_exact_280_ascii(self, publisher: XPublisher) -> None:
        """ASCII 280文字（加重280）はエラーなし。"""
        publisher.validate_text("a" * MAX_TWEET_LENGTH)

    def test_281_ascii_raises(self, publisher: XPublisher) -> None:
        """ASCII 281文字（加重281）でValueErrorが発生する。"""
        with pytest.raises(ValueError, match="1文字超過"):
            publisher.validate_text("a" * (MAX_TWEET_LENGTH + 1))

    def test_empty_text_raises(self, publisher: XPublisher) -> None:
        """空文字列でValueErrorが発生する。"""
        with pytest.raises(ValueError, match="空です"):
            publisher.validate_text("")

    def test_japanese_140_chars_ok(self, publisher: XPublisher) -> None:
        """日本語140文字（加重280）はエラーなし。"""
        publisher.validate_text("あ" * 140)

    def test_japanese_141_chars_raises(self, publisher: XPublisher) -> None:
        """日本語141文字（加重282）でValueErrorが発生する。"""
        with pytest.raises(ValueError, match="2文字超過"):
            publisher.validate_text("あ" * 141)

    def test_japanese_280_chars_raises(self, publisher: XPublisher) -> None:
        """日本語280文字（加重560）でValueErrorが発生する。"""
        with pytest.raises(ValueError, match="超過"):
            publisher.validate_text("あ" * MAX_TWEET_LENGTH)


class TestPublish:
    """1ツイート投稿のテスト。"""

    @respx.mock
    async def test_publish_with_text(self, publisher: XPublisher, blog_post: BlogPost) -> None:
        """テキスト指定で投稿成功。"""
        respx.post(f"{X_API_BASE}/tweets").mock(return_value=_tweet_response("999"))

        result = await publisher.publish(blog_post, text="テスト投稿です")

        assert result.success is True
        assert result.post_id == 999
        assert result.url == "https://x.com/i/status/999"

    async def test_publish_auto_text_with_url(
        self, publisher: XPublisher, blog_post: BlogPost, mocker: pytest_mock.MockerFixture
    ) -> None:
        """テキスト未指定でpost.titleとwordpress_urlから自動生成。"""
        mock_post = mocker.patch.object(
            publisher, "_post_tweet", return_value={"data": {"id": "100"}}
        )

        result = await publisher.publish(blog_post)

        assert result.success is True
        called_text = mock_post.call_args[0][0]
        assert "テスト投稿" in called_text
        assert "https://example.com/blog/test-post" in called_text

    async def test_publish_auto_text_without_url(
        self, publisher: XPublisher, mocker: pytest_mock.MockerFixture
    ) -> None:
        """wordpress_urlがない場合はtitleのみで投稿。"""
        mock_post = mocker.patch.object(
            publisher, "_post_tweet", return_value={"data": {"id": "101"}}
        )

        post = BlogPost(
            title="タイトルのみ",
            content="内容",
            content_type="weekly-ai-news",
            slug="title-only",
            created_at=datetime(2026, 2, 16, tzinfo=UTC),
        )

        result = await publisher.publish(post)

        assert result.success is True
        assert mock_post.call_args[0][0] == "タイトルのみ"

    @respx.mock
    async def test_publish_auth_error(self, publisher: XPublisher, blog_post: BlogPost) -> None:
        """認証エラー時にXPublishErrorが発生する。"""
        respx.post(f"{X_API_BASE}/tweets").mock(
            return_value=httpx.Response(401, json={"detail": "Unauthorized"})
        )

        with pytest.raises(XPublishError, match="認証に失敗"):
            await publisher.publish(blog_post, text="テスト")

    @respx.mock
    async def test_publish_credits_depleted(
        self, publisher: XPublisher, blog_post: BlogPost
    ) -> None:
        """クレジット不足時にXPublishErrorが発生する。"""
        respx.post(f"{X_API_BASE}/tweets").mock(
            return_value=httpx.Response(402, json={"title": "CreditsDepleted"})
        )

        with pytest.raises(XPublishError, match="クレジットが不足"):
            await publisher.publish(blog_post, text="テスト")

    @respx.mock
    async def test_publish_network_error_retry(
        self, publisher: XPublisher, blog_post: BlogPost
    ) -> None:
        """ネットワークエラー時にリトライ後XPublishErrorが発生する。"""
        respx.post(f"{X_API_BASE}/tweets").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(XPublishError, match="通信エラー"):
            await publisher.publish(blog_post, text="テスト")

        assert respx.calls.call_count == 2  # 初回 + リトライ1回

    async def test_publish_text_too_long_ascii(
        self, publisher: XPublisher, blog_post: BlogPost
    ) -> None:
        """ASCII文字数超過時にValueErrorが発生する。"""
        with pytest.raises(ValueError, match="超過"):
            await publisher.publish(blog_post, text="a" * 281)

    async def test_publish_text_too_long_japanese(
        self, publisher: XPublisher, blog_post: BlogPost
    ) -> None:
        """日本語で加重文字数超過時にValueErrorが発生する。"""
        with pytest.raises(ValueError, match="超過"):
            await publisher.publish(blog_post, text="あ" * 141)


class TestPublishThread:
    """スレッド投稿のテスト。"""

    @respx.mock
    async def test_thread_three_tweets(self, publisher: XPublisher, blog_post: BlogPost) -> None:
        """3件のスレッド投稿が順番に実行される。"""
        call_count = 0

        def make_response(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(201, json={"data": {"id": f"t{call_count}"}})

        respx.post(f"{X_API_BASE}/tweets").mock(side_effect=make_response)

        result = await publisher.publish_thread(blog_post, ["ツイート1", "ツイート2", "ツイート3"])

        assert result.success is True
        assert result.thread_ids == ["t1", "t2", "t3"]
        assert result.tweet_id == "t1"
        assert result.tweet_url == "https://x.com/i/status/t1"

    async def test_thread_replies_chain(
        self, publisher: XPublisher, blog_post: BlogPost, mocker: pytest_mock.MockerFixture
    ) -> None:
        """2件目以降が前のツイートへのリプライとして投稿される。"""
        call_count = 0

        async def fake_post_tweet(text: str, reply_to: str | None = None) -> dict[str, object]:
            nonlocal call_count
            call_count += 1
            return {"data": {"id": f"t{call_count}"}}

        mock_post = mocker.patch.object(publisher, "_post_tweet", side_effect=fake_post_tweet)

        await publisher.publish_thread(blog_post, ["1件目", "2件目", "3件目"])

        # 1件目はリプライなし
        assert mock_post.call_args_list[0] == mocker.call("1件目", reply_to=None)
        # 2件目は1件目へのリプライ
        assert mock_post.call_args_list[1] == mocker.call("2件目", reply_to="t1")
        # 3件目は2件目へのリプライ
        assert mock_post.call_args_list[2] == mocker.call("3件目", reply_to="t2")

    def test_thread_text_validation(self, publisher: XPublisher, blog_post: BlogPost) -> None:
        """スレッド内の加重文字数超過でValueErrorが発生する。"""
        with pytest.raises(ValueError, match="超過"):
            import asyncio

            asyncio.get_event_loop().run_until_complete(
                publisher.publish_thread(blog_post, ["OK", "あ" * 141])
            )

    @respx.mock
    async def test_thread_ids_recorded(self, publisher: XPublisher, blog_post: BlogPost) -> None:
        """thread_idsに全ツイートIDが記録される。"""
        call_count = 0

        def make_response(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(201, json={"data": {"id": f"id{call_count}"}})

        respx.post(f"{X_API_BASE}/tweets").mock(side_effect=make_response)

        result = await publisher.publish_thread(blog_post, ["A", "B"])

        assert len(result.thread_ids) == 2
        assert result.thread_ids == ["id1", "id2"]


class TestPostTweetErrorHandling:
    """_post_tweetのエラーハンドリングテスト。"""

    @respx.mock
    async def test_general_4xx_error_with_detail(self, publisher: XPublisher) -> None:
        """一般4xxエラー時にレスポンスのdetailが含まれる。"""
        respx.post(f"{X_API_BASE}/tweets").mock(
            return_value=httpx.Response(400, json={"detail": "Bad Request: invalid text"})
        )

        with pytest.raises(XPublishError, match="Bad Request: invalid text"):
            await publisher._post_tweet("テスト")

    @respx.mock
    async def test_general_4xx_error_without_detail(self, publisher: XPublisher) -> None:
        """一般4xxエラーでdetailがない場合のフォールバックメッセージ。"""
        respx.post(f"{X_API_BASE}/tweets").mock(
            return_value=httpx.Response(400, json={"error": "unknown"})
        )

        with pytest.raises(XPublishError, match="投稿に失敗しました"):
            await publisher._post_tweet("テスト")

    @respx.mock
    async def test_general_4xx_error_invalid_json(self, publisher: XPublisher) -> None:
        """一般4xxエラーでJSON解析に失敗した場合のフォールバック。"""
        respx.post(f"{X_API_BASE}/tweets").mock(return_value=httpx.Response(400, text="not json"))

        with pytest.raises(XPublishError, match="投稿に失敗しました"):
            await publisher._post_tweet("テスト")

    @respx.mock
    async def test_success_response_invalid_json(self, publisher: XPublisher) -> None:
        """成功レスポンスでJSON解析に失敗した場合。"""
        respx.post(f"{X_API_BASE}/tweets").mock(return_value=httpx.Response(201, text="not json"))

        with pytest.raises(XPublishError, match="レスポンスの解析に失敗"):
            await publisher._post_tweet("テスト")

    @respx.mock
    async def test_rate_limit_error(self, publisher: XPublisher) -> None:
        """レート制限エラー(429)時にXPublishErrorが発生する。"""
        respx.post(f"{X_API_BASE}/tweets").mock(
            return_value=httpx.Response(429, json={"detail": "Too Many Requests"})
        )

        with pytest.raises(XPublishError, match="レート制限"):
            await publisher._post_tweet("テスト")


class TestPostTweetRetry:
    """_post_tweetのリトライ動作テスト。"""

    @respx.mock
    async def test_server_error_retry_then_success(self, publisher: XPublisher) -> None:
        """サーバーエラー後にリトライで成功する。"""
        route = respx.post(f"{X_API_BASE}/tweets")
        route.side_effect = [
            httpx.Response(500, json={"detail": "Internal Server Error"}),
            _tweet_response("retry-ok"),
        ]

        result = await publisher._post_tweet("テスト")

        assert result["data"] == {"id": "retry-ok"}  # type: ignore[comparison-overlap]

    @respx.mock
    async def test_server_error_retry_then_fail(self, publisher: XPublisher) -> None:
        """サーバーエラー2回でXPublishErrorが発生する。"""
        respx.post(f"{X_API_BASE}/tweets").mock(
            return_value=httpx.Response(500, json={"detail": "error"})
        )

        with pytest.raises(XPublishError, match="サーバーエラー"):
            await publisher._post_tweet("テスト")

    @respx.mock
    async def test_network_error_retry_then_success(self, publisher: XPublisher) -> None:
        """ネットワークエラー後にリトライで成功する。"""
        route = respx.post(f"{X_API_BASE}/tweets")
        route.side_effect = [
            httpx.ConnectError("refused"),
            _tweet_response("net-ok"),
        ]

        result = await publisher._post_tweet("テスト")

        assert result["data"] == {"id": "net-ok"}  # type: ignore[comparison-overlap]
