"""X（Twitter）投稿Publisher。"""

import asyncio
import os
import typing

import httpx
from authlib.integrations.httpx_client import OAuth1Auth
from authlib.integrations.httpx_client.utils import build_request
from dotenv import load_dotenv

from src.errors import XPublishError
from src.models.blog_post import BlogPost, PublishResult, XPublishResult

X_API_BASE = "https://api.x.com/2"
MAX_TWEET_LENGTH = 280
THREAD_WAIT_SECONDS = 0.1


class _OAuth1AuthJsonFix(OAuth1Auth):  # type: ignore[misc]
    """authlib の OAuth1Auth は JSON body を署名時に空にしてしまうバグがある。

    OAuth 1.0a の仕様では JSON body は署名に含めないのが正しいが、
    authlib は署名後に body 自体も空にリセットしてしまう。
    このサブクラスでは元の body を保持するよう修正する。
    """

    def auth_flow(
        self, request: httpx.Request
    ) -> typing.Generator[httpx.Request, httpx.Response, None]:
        original_body = request.content
        url, headers, body = self.prepare(
            request.method, str(request.url), request.headers, request.content
        )
        # prepare() が body を空にした場合、元の body を復元する
        if not body and original_body:
            body = original_body
        headers["Content-Length"] = str(len(body))
        yield build_request(
            url=url, headers=headers, body=body, initial_request=request
        )


class XPublisher:
    """X API v2でツイートを投稿するPublisher。"""

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        access_token: str | None = None,
        access_token_secret: str | None = None,
    ) -> None:
        load_dotenv()
        self._api_key = api_key or os.environ.get("X_API_KEY", "")
        self._api_secret = api_secret or os.environ.get("X_API_SECRET", "")
        self._access_token = access_token or os.environ.get("X_ACCESS_TOKEN", "")
        self._access_token_secret = access_token_secret or os.environ.get(
            "X_ACCESS_TOKEN_SECRET", ""
        )

        missing = [
            name
            for name, value in [
                ("X_API_KEY", self._api_key),
                ("X_API_SECRET", self._api_secret),
                ("X_ACCESS_TOKEN", self._access_token),
                ("X_ACCESS_TOKEN_SECRET", self._access_token_secret),
            ]
            if not value
        ]
        if missing:
            raise ValueError(
                f"X API認証情報が未設定です: {', '.join(missing)}。"
                ".envファイルまたはコンストラクタ引数で設定してください。"
            )

        self._auth = _OAuth1AuthJsonFix(
            client_id=self._api_key,
            client_secret=self._api_secret,
            token=self._access_token,
            token_secret=self._access_token_secret,
        )

    def validate_text(self, text: str) -> None:
        """テキストの文字数バリデーション。"""
        if not text:
            raise ValueError("投稿テキストが空です。")
        if len(text) > MAX_TWEET_LENGTH:
            over = len(text) - MAX_TWEET_LENGTH
            raise ValueError(
                f"投稿テキストが{MAX_TWEET_LENGTH}文字を超えています（{over}文字超過）。"
            )

    async def _post_tweet(
        self,
        text: str,
        reply_to: str | None = None,
    ) -> dict[str, object]:
        """1件のツイートを投稿する（内部メソッド）。"""
        payload: dict[str, object] = {"text": text}
        if reply_to:
            payload["reply"] = {"in_reply_to_tweet_id": reply_to}

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{X_API_BASE}/tweets",
                        json=payload,
                        auth=self._auth,
                    )

                if response.status_code in (401, 403):
                    raise XPublishError(
                        message=(
                            "認証に失敗しました。.envの"
                            "X_API_KEY, X_API_SECRET, "
                            "X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET"
                            "を確認してください。"
                        ),
                        status_code=response.status_code,
                    )

                if response.status_code == 402:
                    raise XPublishError(
                        message=(
                            "APIクレジットが不足しています。"
                            "X Developer Portalでクレジットを"
                            "購入してください。"
                            " https://developer.x.com/"
                        ),
                        status_code=402,
                    )

                if response.status_code == 429:
                    raise XPublishError(
                        message="レート制限に達しました。しばらく待ってから再試行してください。",
                        status_code=429,
                    )

                if response.status_code >= 500:
                    if attempt == 0:
                        last_error = XPublishError(
                            message="サーバーエラーが発生しました。",
                            status_code=response.status_code,
                        )
                        continue
                    raise XPublishError(
                        message="サーバーエラーが発生しました。",
                        status_code=response.status_code,
                    )

                if response.status_code >= 400:
                    try:
                        error_data = response.json()
                        message = str(error_data.get("detail", "投稿に失敗しました"))
                    except (ValueError, KeyError):
                        message = "投稿に失敗しました"
                    raise XPublishError(message=message, status_code=response.status_code)

                try:
                    data: dict[str, object] = response.json()
                except ValueError as e:
                    raise XPublishError(
                        message=f"レスポンスの解析に失敗しました: {e}"
                    ) from e
                return data

            except XPublishError:
                raise
            except httpx.HTTPError as e:
                if attempt == 0:
                    last_error = e
                    continue
                raise XPublishError(message=f"通信エラー: {e}") from e

        raise XPublishError(message=f"通信エラー: {last_error}") from last_error

    async def publish(
        self,
        post: BlogPost,
        text: str | None = None,
        **kwargs: object,
    ) -> PublishResult:
        """記事の紹介ツイートを1件投稿する。

        Raises:
            XPublishError: X API関連のエラー
            ValueError: テキストのバリデーションエラー
        """
        if text is None:
            if post.wordpress_url:
                text = f"{post.title} {post.wordpress_url}"
            else:
                text = post.title

        self.validate_text(text)
        data = await self._post_tweet(text)
        tweet_data = data.get("data", {})
        if isinstance(tweet_data, dict):
            tweet_id = str(tweet_data.get("id", ""))
        else:
            tweet_id = ""
        tweet_url = f"https://x.com/i/status/{tweet_id}" if tweet_id else None

        try:
            post_id = int(tweet_id)
        except (ValueError, TypeError):
            post_id = None

        return PublishResult(
            success=True,
            post_id=post_id,
            url=tweet_url,
        )

    async def publish_thread(
        self,
        post: BlogPost,
        texts: list[str],
    ) -> XPublishResult:
        """スレッド形式で複数ツイートを投稿する。"""
        for text in texts:
            self.validate_text(text)

        thread_ids: list[str] = []
        reply_to: str | None = None

        for i, text in enumerate(texts):
            data = await self._post_tweet(text, reply_to=reply_to)
            tweet_data = data.get("data", {})
            if isinstance(tweet_data, dict):
                tweet_id = str(tweet_data.get("id", ""))
            else:
                tweet_id = ""
            thread_ids.append(tweet_id)
            reply_to = tweet_id

            if i < len(texts) - 1:
                await asyncio.sleep(THREAD_WAIT_SECONDS)

        first_id = thread_ids[0] if thread_ids else None
        tweet_url = f"https://x.com/i/status/{first_id}" if first_id else None
        return XPublishResult(
            success=True,
            tweet_id=first_id,
            tweet_url=tweet_url,
            thread_ids=thread_ids,
        )
