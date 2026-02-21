"""WordPress投稿Publisher。"""

import base64
import os
from typing import Literal

import httpx
from dotenv import load_dotenv

from src.errors import WordPressPublishError
from src.models.blog_post import BlogPost, PublishResult
from src.utils.markdown import markdown_to_html


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
        **kwargs: object,
    ) -> PublishResult:
        """記事をWordPressに投稿する。

        Args:
            post: 投稿するBlogPost
            status: 投稿ステータス（"draft" or "publish"）
            categories: カテゴリ名のリスト
            tags: タグ名のリスト
            **kwargs: 未使用

        Returns:
            投稿結果

        Raises:
            WordPressPublishError: 投稿に失敗した場合
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                category_ids = await self._resolve_categories(client, categories or [])
                tag_ids = await self._resolve_tags(client, tags or [])

                html_content = markdown_to_html(post.content)

                payload: dict[str, object] = {
                    "title": post.title,
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
                    raise WordPressPublishError(message=message, status_code=response.status_code)

                try:
                    data = response.json()
                except ValueError as e:
                    raise WordPressPublishError(
                        message=f"レスポンスの解析に失敗しました: {e}"
                    ) from e

                post_id = data.get("id")
                post_url = data.get("link", "")

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
