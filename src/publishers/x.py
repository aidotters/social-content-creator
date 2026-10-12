"""X（Twitter）投稿Publisher。"""

import asyncio
import logging
import mimetypes
import os
import re
import typing
from pathlib import Path

import httpx
from authlib.integrations.httpx_client import OAuth1Auth
from authlib.integrations.httpx_client.utils import build_request
from dotenv import load_dotenv

from src.errors import XPublishError
from src.models.blog_post import BlogPost, PublishResult, XPublishResult

logger = logging.getLogger(__name__)

X_API_BASE = "https://api.x.com/2"
MAX_TWEET_LENGTH = 280
THREAD_WAIT_SECONDS = 0.1

# X加重文字数でカウントされるCJK / 絵文字のコードポイント範囲
_WEIGHTED_RANGES = (
    (0x1100, 0x11FF),  # Hangul Jamo
    (0x2E80, 0x9FFF),  # CJK Radicals 〜 CJK Unified Ideographs
    (0xAC00, 0xD7FF),  # Hangul Syllables
    (0xF900, 0xFAFF),  # CJK Compatibility Ideographs
    (0xFE30, 0xFE4F),  # CJK Compatibility Forms
    (0xFF00, 0xFFEF),  # Halfwidth and Fullwidth Forms
    (0x3000, 0x303F),  # CJK Symbols and Punctuation
    (0x3040, 0x309F),  # Hiragana
    (0x30A0, 0x30FF),  # Katakana
    (0x1F000, 0x1FFFF),  # Emoticons / Emoji
    (0x20000, 0x2FA1F),  # CJK Extension
)

_URL_WEIGHT = 23  # t.co短縮URLの固定長

# 画像の添付（v2 の media/upload・1リクエストで送る simple upload）
MAX_IMAGES = 4
MAX_IMAGE_BYTES = 5 * 1024 * 1024
_IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


class _OAuth1AuthJsonFix(OAuth1Auth):  # type: ignore[misc]
    """authlib の OAuth1Auth は JSON body を署名時に空にしてしまうバグがある。

    OAuth 1.0a の仕様では JSON body は署名に含めないのが正しいが、
    authlib は署名後に body 自体も空にリセットしてしまう。
    このサブクラスでは元の body を保持するよう修正する。
    画像アップロードの multipart body も同じ理由で必要（署名に含めず、本体は送る）。
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
        yield build_request(url=url, headers=headers, body=body, initial_request=request)


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

    @staticmethod
    def weighted_length(text: str) -> int:
        """Xの加重文字数を計算する。

        CJK文字・絵文字は2文字、URLはt.co短縮で23文字、その他は1文字。
        """
        url_pattern = re.compile(r"https?://\S+")
        urls = url_pattern.findall(text)
        text_no_url = url_pattern.sub("", text)

        count = 0
        for char in text_no_url:
            cp = ord(char)
            if any(lo <= cp <= hi for lo, hi in _WEIGHTED_RANGES):
                count += 2
            else:
                count += 1

        count += len(urls) * _URL_WEIGHT
        return count

    def validate_text(self, text: str) -> None:
        """テキストの加重文字数バリデーション。

        Xでは日本語・CJK文字・絵文字を2文字、URLをt.co短縮で23文字としてカウントする。
        """
        if not text:
            raise ValueError("投稿テキストが空です。")
        wlen = self.weighted_length(text)
        if wlen > MAX_TWEET_LENGTH:
            over = wlen - MAX_TWEET_LENGTH
            raise ValueError(
                f"投稿テキストが{MAX_TWEET_LENGTH}文字を超えています"
                f"（加重文字数{wlen}、{over}文字超過）。"
            )

    async def _post_tweet(
        self,
        text: str,
        reply_to: str | None = None,
        media_ids: list[str] | None = None,
    ) -> dict[str, object]:
        """1件のツイートを投稿する（内部メソッド）。"""
        payload: dict[str, object] = {"text": text}
        if reply_to:
            payload["reply"] = {"in_reply_to_tweet_id": reply_to}
        if media_ids:
            payload["media"] = {"media_ids": media_ids}

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{X_API_BASE}/tweets",
                        json=payload,
                        auth=self._auth,
                    )

                logger.info(
                    "X API response: status=%d, body=%s",
                    response.status_code,
                    response.text,
                )

                if response.status_code in (401, 403):
                    raise XPublishError(
                        message=(
                            "認証に失敗しました。.envの"
                            "X_API_KEY, X_API_SECRET, "
                            "X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET"
                            "を確認してください。"
                            f" (response: {response.text})"
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
                    raise XPublishError(message=f"レスポンスの解析に失敗しました: {e}") from e
                return data

            except XPublishError:
                raise
            except httpx.HTTPError as e:
                if attempt == 0:
                    last_error = e
                    continue
                raise XPublishError(message=f"通信エラー: {e}") from e

        raise XPublishError(message=f"通信エラー: {last_error}") from last_error

    @staticmethod
    def validate_images(image_paths: list[str | Path]) -> list[Path]:
        """添付する画像の枚数・形式・サイズを投稿の前に確かめる。

        途中で失敗して画像だけがアップロード済みになるのを避けるため、
        1枚もアップロードしないうちに全部を検査する。
        """
        if len(image_paths) > MAX_IMAGES:
            raise ValueError(f"画像は{MAX_IMAGES}枚までです（{len(image_paths)}枚指定）。")
        paths: list[Path] = []
        for raw in image_paths:
            path = Path(raw)
            if not path.is_file():
                raise ValueError(f"画像ファイルが見つかりません: {path}")
            if path.suffix.lower() not in _IMAGE_TYPES:
                allowed = ", ".join(sorted(_IMAGE_TYPES))
                raise ValueError(f"対応していない画像形式です: {path.name}（{allowed}）")
            size = path.stat().st_size
            if size > MAX_IMAGE_BYTES:
                raise ValueError(
                    f"画像が大きすぎます: {path.name}（{size:,}バイト・上限"
                    f"{MAX_IMAGE_BYTES:,}バイト）。"
                )
            paths.append(path)
        return paths

    async def _upload_image(self, path: Path) -> str:
        """画像を1枚アップロードして media_id を返す（内部メソッド）。"""
        content_type = _IMAGE_TYPES.get(path.suffix.lower()) or (
            mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        )
        content = path.read_bytes()

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{X_API_BASE}/media/upload",
                        data={"media_category": "tweet_image", "media_type": content_type},
                        files={"media": (path.name, content, content_type)},
                        auth=self._auth,
                    )

                logger.info(
                    "X media upload response: status=%d, body=%s",
                    response.status_code,
                    response.text,
                )

                if response.status_code >= 500 and attempt == 0:
                    last_error = XPublishError(
                        message="画像のアップロードでサーバーエラーが発生しました。",
                        status_code=response.status_code,
                    )
                    continue

                if response.status_code >= 400:
                    raise XPublishError(
                        message=f"画像のアップロードに失敗しました: {path.name}"
                        f" (response: {response.text})",
                        status_code=response.status_code,
                    )

                try:
                    body = response.json()
                except ValueError as e:
                    raise XPublishError(
                        message=f"画像アップロードの応答を解析できません: {e}"
                    ) from e
                data = body.get("data") if isinstance(body, dict) else None
                media_id = data.get("id") if isinstance(data, dict) else None
                if not media_id:
                    raise XPublishError(
                        message=f"画像アップロードの応答に media id がありません: {path.name}"
                    )
                return str(media_id)

            except XPublishError:
                raise
            except httpx.HTTPError as e:
                if attempt == 0:
                    last_error = e
                    continue
                raise XPublishError(message=f"画像アップロードの通信エラー: {e}") from e

        raise XPublishError(message=f"画像アップロードの通信エラー: {last_error}") from last_error

    async def publish(
        self,
        post: BlogPost,
        text: str | None = None,
        image_paths: list[str | Path] | None = None,
        **kwargs: object,
    ) -> PublishResult:
        """記事の紹介ツイートを1件投稿する。

        Args:
            image_paths: 添付する画像（PNG/JPEG/WebP/GIF・4枚まで・各5MBまで）

        Raises:
            XPublishError: X API関連のエラー
            ValueError: テキスト・画像のバリデーションエラー
        """
        if text is None:
            if post.wordpress_url:
                text = f"{post.title} {post.wordpress_url}"
            else:
                text = post.title

        self.validate_text(text)
        images = self.validate_images(image_paths) if image_paths else []
        media_ids = [await self._upload_image(path) for path in images]
        data = await self._post_tweet(text, media_ids=media_ids or None)
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
