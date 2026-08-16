"""静的サイト（aidotters-web-page）へ記事を書き出すPublisher。

WordPress REST API への投稿を置き換えるもの。記事Markdownをサイトリポジトリの
`src/content/blog/{type}/{slug}.md` へ配置し、git commit するところまでを行う。

frontmatter はサイト側の zod スキーマ（src/content.config.ts）と対になっている。
キーを増減するとサイトのビルドが落ちるため、変更時は両方を揃えること。
"""

import os
import re
import subprocess
from pathlib import Path

from dotenv import load_dotenv

from src.errors import StaticSitePublishError
from src.models.blog_post import BlogPost, PublishResult

_CONTENT_DIR = Path("src/content/blog")

# サイト側 zod スキーマが受け付けるキー。ここに無いキーは書き出さない。
_FRONTMATTER_ORDER = ("title", "subtitle", "date", "published_at", "type", "status")


def _quote(value: str) -> str:
    """YAML のシングルクォート文字列にする。"""
    return "'" + value.replace("'", "''") + "'"


class StaticSitePublisher:
    """記事を静的サイトのリポジトリへ書き出すPublisher。"""

    def __init__(self, site_repo: Path | str | None = None) -> None:
        load_dotenv()
        raw = site_repo or os.environ.get("AIDOTTERS_SITE_REPO", "")
        if not raw:
            raise ValueError(
                "サイトリポジトリのパスが未設定です: AIDOTTERS_SITE_REPO。"
                ".envファイルまたはコンストラクタ引数で設定してください。"
            )
        self._repo = Path(raw).expanduser().resolve()
        if not (self._repo / ".git").exists():
            raise ValueError(f"gitリポジトリではありません: {self._repo}")

    @property
    def repo(self) -> Path:
        return self._repo

    def resolve_slug(self, post: BlogPost) -> str:
        """記事のslugを決める。

        週刊AIニュースはタイトルの「第N週」表記が実際にずれていた実績があるため、
        一意性が保証される公開日ベースにする。それ以外は生成時のslugを使う。
        """
        if post.content_type == "weekly-ai-news":
            return (post.published_at or post.created_at).strftime("%Y-%m-%d")
        slug = post.slug.strip().strip("/")
        if not slug:
            raise StaticSitePublishError(f"slugが空です: {post.title}")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise StaticSitePublishError(
                f"slugに使えない文字が含まれています（英小文字・数字・ハイフンのみ）: {slug}"
            )
        return slug

    def build_frontmatter(self, post: BlogPost, published: bool) -> str:
        """サイト側スキーマに合う frontmatter を組み立てる。"""
        values: dict[str, str] = {
            "title": post.title,
            "date": post.created_at.isoformat(),
            "type": post.content_type,
            "status": "published" if published else "draft",
        }
        if post.subtitle:
            values["subtitle"] = post.subtitle
        if post.published_at:
            values["published_at"] = post.published_at.isoformat()

        lines = [f"{k}: {_quote(values[k])}" for k in _FRONTMATTER_ORDER if k in values]
        return "---\n" + "\n".join(lines) + "\n---\n"

    def target_path(self, post: BlogPost) -> Path:
        return self._repo / _CONTENT_DIR / post.content_type / f"{self.resolve_slug(post)}.md"

    async def publish(
        self,
        post: BlogPost,
        status: str = "draft",
        commit: bool = True,
        overwrite: bool = False,
        **kwargs: object,
    ) -> PublishResult:
        """記事を静的サイトのリポジトリへ書き出す。

        Args:
            post: 投稿するBlogPost
            status: "publish" なら公開扱い、それ以外はサイト側でビルド対象外の下書き
            commit: git commit まで行うか
            overwrite: 既存ファイルを上書きするか
            **kwargs: 未使用

        Returns:
            投稿結果（url は公開後のサイト内パス）

        Raises:
            StaticSitePublishError: 書き出しに失敗した場合
        """
        del kwargs

        path = self.target_path(post)
        if path.exists() and not overwrite:
            raise StaticSitePublishError(
                f"同じslugの記事が既に存在します: {path.relative_to(self._repo)}"
                "（上書きする場合は overwrite=True）"
            )

        content = post.content.rstrip("\n") + "\n"
        text = self.build_frontmatter(post, published=status == "publish") + "\n" + content

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except OSError as exc:
            raise StaticSitePublishError(f"ファイル書き出しに失敗しました: {exc}") from exc

        url = f"/blog/{post.content_type}/{self.resolve_slug(post)}/"
        if commit:
            self._commit(path, post)
        return PublishResult(success=True, url=url)

    def _commit(self, path: Path, post: BlogPost) -> None:
        rel = path.relative_to(self._repo)
        message = f"post: {post.title}\n\nSource: social-content-creator ({post.content_type})"
        try:
            subprocess.run(
                ["git", "add", "--", str(rel)],
                cwd=self._repo,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "commit", "-m", message, "--", str(rel)],
                cwd=self._repo,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise StaticSitePublishError(
                f"git commit に失敗しました: {exc.stderr or exc.stdout}"
            ) from exc
