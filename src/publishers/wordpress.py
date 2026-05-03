"""WordPress投稿Publisher。"""

import base64
import os
import shutil
from pathlib import Path
from typing import Literal

import httpx
from dotenv import load_dotenv

from src.errors import WordPressPublishError
from src.models.blog_post import BlogPost, ContentType, PublishResult
from src.utils.markdown import html_to_gutenberg_blocks, markdown_to_html

_CONTENT_TYPE_PREFIXES: dict[ContentType, str] = {
    "paper-review": "【論文解説】",
    "weekly-ai-news": "【週刊AIニュース】",
    "project-intro": "【プロジェクト紹介】",
    "tool-tips": "【ツール紹介】",
    "market-analysis": "【市場分析】",
    "ml-practice": "【ML実践】",
    "cv": "【CV論文解説】",
    "feature": "【特集】",
}

_SUPPORTED_IMAGE_MIME_TYPES: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

_MEDIA_ARCHIVE_DIR = Path("outputs/images/archive")


class WordPressPublisher:
    """WordPress REST APIで記事を投稿するPublisher。"""

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        app_password: str | None = None,
    ) -> None:
        load_dotenv()
        self._base_url = (base_url or os.environ.get("WORDPRESS_URL", "")).rstrip("/")
        self._username = username or os.environ.get("WORDPRESS_USER", "")
        self._app_password = app_password or os.environ.get("WORDPRESS_APP_PASSWORD", "")

        missing = []
        if not self._base_url:
            missing.append("WORDPRESS_URL")
        if not self._username:
            missing.append("WORDPRESS_USER")
        if not self._app_password:
            missing.append("WORDPRESS_APP_PASSWORD")
        if missing:
            raise ValueError(
                f"WordPress認証情報が未設定です: {', '.join(missing)}。"
                ".envファイルまたはコンストラクタ引数で設定してください。"
            )

    @property
    def api_base(self) -> str:
        return f"{self._base_url}/wp-json/wp/v2"

    def _auth_header(self) -> dict[str, str]:
        credentials = f"{self._username}:{self._app_password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    async def publish(
        self,
        post: BlogPost,
        status: Literal["draft", "publish"] = "draft",
        categories: list[str] | None = None,
        tags: list[str] | None = None,
        featured_image_path: Path | None = None,
        featured_image_alt: str | None = None,
        force_featured_image: bool = False,  # publish() 内では未使用（docstring 参照）
        **kwargs: object,
    ) -> PublishResult:
        """記事をWordPressに投稿する。

        Args:
            post: 投稿するBlogPost
            status: 投稿ステータス（"draft" or "publish"）
            categories: カテゴリ名のリスト
            tags: タグ名のリスト
            featured_image_path: アイキャッチ画像のローカルパス。指定時は事前に
                upload_media() を呼び、payload の featured_media にセットする。
            featured_image_alt: アイキャッチ画像の alt 属性。未指定時は post.title を使用。
            force_featured_image: 既存アイキャッチの上書きフラグ（publish() では未使用、
                Phase 3 のスキル層から set_featured_media() を直接呼ぶ用途）。
            **kwargs: 未使用

        Returns:
            投稿結果

        Raises:
            WordPressPublishError: 投稿に失敗した場合
        """
        try:
            media_id: int | None = None
            if featured_image_path is not None:
                alt_text = featured_image_alt or post.title
                media_id = await self.upload_media(
                    image_path=featured_image_path,
                    alt_text=alt_text,
                    title=post.title,
                )

            async with httpx.AsyncClient(timeout=30.0) as client:
                category_ids = await self._resolve_categories(client, categories or [])
                tag_ids = await self._resolve_tags(client, tags or [])

                html_content = markdown_to_html(post.content)
                html_content = html_to_gutenberg_blocks(html_content)

                # サブタイトルをコンテンツ先頭に挿入
                if post.subtitle:
                    subtitle_block = (
                        "<!-- wp:paragraph -->\n"
                        f'<p class="article-subtitle" style="'
                        f"font-size:1.05em;color:#666;"
                        f'margin-bottom:1.5em;">'
                        f"<em>{post.subtitle}</em></p>\n"
                        "<!-- /wp:paragraph -->"
                    )
                    html_content = subtitle_block + "\n\n" + html_content

                # content_typeに応じてタイトルにプレフィックスを付与
                prefix = _CONTENT_TYPE_PREFIXES.get(post.content_type, "")
                title = post.title
                if prefix and not title.startswith(prefix):
                    title = prefix + title

                payload: dict[str, object] = {
                    "title": title,
                    "content": html_content,
                    "status": status,
                    "slug": post.slug,
                }
                if post.subtitle:
                    payload["excerpt"] = post.subtitle
                if category_ids:
                    payload["categories"] = category_ids
                if tag_ids:
                    payload["tags"] = tag_ids
                if media_id is not None:
                    payload["featured_media"] = media_id

                response = await client.post(
                    f"{self.api_base}/posts",
                    json=payload,
                    headers=self._auth_header(),
                )

                if response.status_code == 401:
                    raise WordPressPublishError(
                        message="認証に失敗しました。.envのWordPress認証情報を確認してください。",
                        status_code=401,
                    )

                if response.status_code >= 400:
                    try:
                        error_data = response.json()
                        message = str(error_data.get("message", "投稿に失敗しました"))
                    except (ValueError, KeyError):
                        message = f"投稿に失敗しました (HTTP {response.status_code})"
                    if media_id is not None:
                        message = (
                            f"{message} | アップロード済みメディア "
                            f"media_id={media_id} は手動でクリーンアップしてください"
                        )
                    raise WordPressPublishError(message=message, status_code=response.status_code)

                try:
                    data = response.json()
                except ValueError as e:
                    raise WordPressPublishError(
                        message=f"レスポンスの解析に失敗しました: {e}"
                    ) from e

                post_id = data.get("id")
                post_url = data.get("link", "")

                # 下書き投稿時はlinkが?p=形式になるため、slugからパーマリンクを構築
                if post_url and "?p=" in post_url:
                    post_slug = data.get("slug", post.slug)
                    post_url = f"{self._base_url}/{post_slug}/"

                if post.subtitle and post_id and post_url:
                    excerpt_with_more = (
                        f"{post.subtitle}… "
                        f'<a class="more-link" href="{post_url}">続きを読む</a>'
                    )
                    await client.post(
                        f"{self.api_base}/posts/{post_id}",
                        json={"excerpt": excerpt_with_more},
                        headers=self._auth_header(),
                    )

                return PublishResult(
                    success=True,
                    post_id=post_id,
                    url=post_url,
                )

        except WordPressPublishError:
            raise
        except httpx.HTTPError as e:
            raise WordPressPublishError(message=f"通信エラー: {e}") from e

    async def upload_media(
        self,
        image_path: Path,
        alt_text: str,
        title: str | None = None,
    ) -> int:
        """画像をWordPressメディアライブラリにアップロードし media_id を返す。

        アップロード後、`POST /wp/v2/media/{id}` を呼んで alt_text/title を更新し、
        ローカルファイルを `outputs/images/archive/` へ移動する。

        Args:
            image_path: アップロードする画像のローカルパス。
            alt_text: 画像の alt 属性に設定する文字列。
            title: メディアタイトル。未指定時はファイル名を使用。

        Returns:
            アップロードされたメディアの ID。

        Raises:
            WordPressPublishError: ファイル不在、未サポート拡張子、API失敗時。
        """
        path = Path(image_path)
        if not path.exists() or not path.is_file():
            raise WordPressPublishError(message=f"画像ファイルが存在しません: {path}")

        ext = path.suffix.lower()
        mime_type = _SUPPORTED_IMAGE_MIME_TYPES.get(ext)
        if mime_type is None:
            supported = "/".join(e.lstrip(".") for e in _SUPPORTED_IMAGE_MIME_TYPES)
            raise WordPressPublishError(
                message=(f"サポートされていない画像形式です: {ext}（対応: {supported}）")
            )

        media_title = title or path.stem
        try:
            with path.open("rb") as fp:
                file_bytes = fp.read()

            async with httpx.AsyncClient(timeout=60.0) as client:
                files = {"file": (path.name, file_bytes, mime_type)}
                data = {
                    "alt_text": alt_text,
                    "title": media_title,
                }
                response = await client.post(
                    f"{self.api_base}/media",
                    files=files,
                    data=data,
                    headers=self._auth_header(),
                )

                if response.status_code == 401:
                    raise WordPressPublishError(
                        message="認証に失敗しました。.envのWordPress認証情報を確認してください。",
                        status_code=401,
                    )

                if response.status_code >= 400:
                    try:
                        error_data = response.json()
                        message = str(
                            error_data.get("message", "メディアアップロードに失敗しました")
                        )
                    except (ValueError, KeyError):
                        message = (
                            f"メディアアップロードに失敗しました (HTTP {response.status_code})"
                        )
                    raise WordPressPublishError(message=message, status_code=response.status_code)

                try:
                    payload = response.json()
                except ValueError as e:
                    raise WordPressPublishError(
                        message=f"メディアレスポンスの解析に失敗しました: {e}"
                    ) from e

                media_id = payload.get("id")
                if not isinstance(media_id, int):
                    raise WordPressPublishError(
                        message="メディアレスポンスに id が含まれていません。"
                    )

                # multipart 経由で alt_text が反映されないケースに備え、
                # 別エンドポイントで alt_text/title を明示的に更新する。
                update_response = await client.post(
                    f"{self.api_base}/media/{media_id}",
                    json={"alt_text": alt_text, "title": media_title},
                    headers=self._auth_header(),
                )
                if update_response.status_code >= 400:
                    try:
                        error_data = update_response.json()
                        message = str(
                            error_data.get("message", "メディアメタデータ更新に失敗しました")
                        )
                    except (ValueError, KeyError):
                        message = (
                            f"メディアメタデータ更新に失敗しました "
                            f"(HTTP {update_response.status_code})"
                        )
                    raise WordPressPublishError(
                        message=f"{message} | media_id={media_id}",
                        status_code=update_response.status_code,
                    )

            # 成功時はローカルファイルをアーカイブへ移動
            _MEDIA_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(_MEDIA_ARCHIVE_DIR / path.name))

            return media_id

        except WordPressPublishError:
            raise
        except httpx.HTTPError as e:
            raise WordPressPublishError(message=f"通信エラー: {e}") from e

    async def set_featured_media(
        self,
        post_id: int,
        media_id: int,
        force: bool = False,
    ) -> None:
        """投稿に featured_media を設定する。

        既存の featured_media が 0 以外の場合、`force=False` ならエラーを投げる。

        Args:
            post_id: 対象投稿の ID。
            media_id: 設定するメディアの ID。
            force: True の場合、既存アイキャッチを上書きする。

        Raises:
            WordPressPublishError: 既存ありかつ force=False、または API 失敗時。
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if not force:
                    get_response = await client.get(
                        f"{self.api_base}/posts/{post_id}",
                        headers=self._auth_header(),
                    )
                    if get_response.status_code >= 400:
                        try:
                            error_data = get_response.json()
                            message = str(error_data.get("message", "投稿の取得に失敗しました"))
                        except (ValueError, KeyError):
                            message = f"投稿の取得に失敗しました (HTTP {get_response.status_code})"
                        raise WordPressPublishError(
                            message=message, status_code=get_response.status_code
                        )

                    try:
                        existing = get_response.json()
                    except ValueError as e:
                        raise WordPressPublishError(
                            message=f"投稿レスポンスの解析に失敗しました: {e}"
                        ) from e

                    existing_media = existing.get("featured_media")
                    if isinstance(existing_media, int) and existing_media != 0:
                        raise WordPressPublishError(
                            message=(
                                f"投稿 {post_id} には既にアイキャッチ "
                                f"(media_id={existing_media}) が設定されています。"
                                "--force で上書きしてください"
                            )
                        )

                update_response = await client.post(
                    f"{self.api_base}/posts/{post_id}",
                    json={"featured_media": media_id},
                    headers=self._auth_header(),
                )
                if update_response.status_code >= 400:
                    try:
                        error_data = update_response.json()
                        message = str(error_data.get("message", "アイキャッチ設定に失敗しました"))
                    except (ValueError, KeyError):
                        message = (
                            f"アイキャッチ設定に失敗しました "
                            f"(HTTP {update_response.status_code})"
                        )
                    raise WordPressPublishError(
                        message=f"{message} | media_id={media_id}",
                        status_code=update_response.status_code,
                    )
        except WordPressPublishError:
            raise
        except httpx.HTTPError as e:
            raise WordPressPublishError(message=f"通信エラー: {e}") from e

    async def get_post(self, post_id: int) -> dict[str, object]:
        """既存記事の情報を取得する。

        Args:
            post_id: 取得する投稿の ID。

        Returns:
            WordPress REST API のレスポンス（title.rendered, content.rendered,
            featured_media など）をそのまま返す dict。

        Raises:
            WordPressPublishError: 取得に失敗した場合。
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.api_base}/posts/{post_id}",
                    headers=self._auth_header(),
                )
                if response.status_code >= 400:
                    try:
                        error_data = response.json()
                        message = str(error_data.get("message", "投稿の取得に失敗しました"))
                    except (ValueError, KeyError):
                        message = f"投稿の取得に失敗しました (HTTP {response.status_code})"
                    raise WordPressPublishError(message=message, status_code=response.status_code)
                try:
                    result: dict[str, object] = response.json()
                except ValueError as e:
                    raise WordPressPublishError(
                        message=f"投稿レスポンスの解析に失敗しました: {e}"
                    ) from e
                return result
        except WordPressPublishError:
            raise
        except httpx.HTTPError as e:
            raise WordPressPublishError(message=f"通信エラー: {e}") from e

    async def get_categories(self) -> list[dict[str, object]]:
        """WordPress上のカテゴリ一覧を取得する。"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.api_base}/categories",
                headers=self._auth_header(),
                params={"per_page": 100},
            )
            response.raise_for_status()
            try:
                result: list[dict[str, object]] = response.json()
            except ValueError as e:
                raise WordPressPublishError(message=f"カテゴリ一覧の解析に失敗しました: {e}") from e
            return result

    async def get_tags(self) -> list[dict[str, object]]:
        """WordPress上のタグ一覧を取得する。"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.api_base}/tags",
                headers=self._auth_header(),
                params={"per_page": 100},
            )
            response.raise_for_status()
            try:
                result: list[dict[str, object]] = response.json()
            except ValueError as e:
                raise WordPressPublishError(message=f"タグ一覧の解析に失敗しました: {e}") from e
            return result

    async def _resolve_categories(self, client: httpx.AsyncClient, names: list[str]) -> list[int]:
        """カテゴリ名からIDを解決する。"""
        if not names:
            return []
        response = await client.get(
            f"{self.api_base}/categories",
            headers=self._auth_header(),
            params={"per_page": 100},
        )
        response.raise_for_status()
        try:
            categories: list[dict[str, object]] = response.json()
        except ValueError:
            return []
        name_to_id: dict[str, int] = {}
        for c in categories:
            cname = str(c.get("name", ""))
            cid = c.get("id")
            if cname and isinstance(cid, int):
                name_to_id[cname.lower()] = cid
        return [name_to_id[n.lower()] for n in names if n.lower() in name_to_id]

    async def _resolve_tags(self, client: httpx.AsyncClient, names: list[str]) -> list[int]:
        """タグ名からIDを解決する。"""
        if not names:
            return []
        response = await client.get(
            f"{self.api_base}/tags",
            headers=self._auth_header(),
            params={"per_page": 100},
        )
        response.raise_for_status()
        try:
            tags: list[dict[str, object]] = response.json()
        except ValueError:
            return []
        name_to_id: dict[str, int] = {}
        for t in tags:
            tname = str(t.get("name", ""))
            tid = t.get("id")
            if tname and isinstance(tid, int):
                name_to_id[tname.lower()] = tid
        return [name_to_id[n.lower()] for n in names if n.lower() in name_to_id]
