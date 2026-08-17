"""静的サイト（aidotters-website）へ記事を書き出すPublisher。

WordPress REST API への投稿を置き換えるもの。記事Markdownをサイトリポジトリの
`src/content/blog/{type}/{slug}.md` へ配置し、git commit するところまでを行う。

frontmatter はサイト側の zod スキーマ（src/content.config.ts）と対になっている。
キーを増減するとサイトのビルドが落ちるため、変更時は両方を揃えること。
"""

import os
import re
import subprocess
from datetime import timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

from src.errors import StaticSitePublishError
from src.models.blog_post import BlogPost, PublishResult

_CONTENT_DIR = Path("src/content/blog")

# アイキャッチはサイト側で image() スキーマに通すため、記事Markdownと同じ
# ディレクトリに置いて相対パスで参照する。詳細はサイトの AGENTS.md を参照。
_IMAGE_SUFFIX = ".webp"
# 元画像は 1344x768 の PNG で 1.5MB 前後。リポジトリに毎週積むには重いので落とす。
# 88 は文字を載せた生成画像でも滲みが出ない範囲で選んだ値（実測で 150KB 前後）。
_IMAGE_QUALITY = 88

# slug に使う日付は日本時間で決める。UTC のままだと日本の夜に書いた記事が前日扱いになる。
_JST = timezone(timedelta(hours=9))

# サイト側 zod スキーマが受け付けるキー。ここに無いキーは書き出さない。
_FRONTMATTER_ORDER = ("title", "subtitle", "date", "published_at", "type", "status", "image")


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
            return (post.published_at or post.created_at).astimezone(_JST).strftime("%Y-%m-%d")
        slug = post.slug.strip().strip("/")
        if not slug:
            raise StaticSitePublishError(f"slugが空です: {post.title}")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise StaticSitePublishError(
                f"slugに使えない文字が含まれています（英小文字・数字・ハイフンのみ）: {slug}"
            )
        return slug

    def build_frontmatter(self, post: BlogPost, published: bool, image: str | None = None) -> str:
        """サイト側スキーマに合う frontmatter を組み立てる。

        Args:
            post: 対象の記事
            published: 公開扱いにするか
            image: アイキャッチの相対パス（`./{slug}.webp`）。None なら書かない
        """
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
        if image:
            values["image"] = image

        lines = [f"{k}: {_quote(values[k])}" for k in _FRONTMATTER_ORDER if k in values]
        return "---\n" + "\n".join(lines) + "\n---\n"

    def image_path(self, post: BlogPost) -> Path:
        """アイキャッチの置き場。記事Markdownと同じディレクトリ・同じ名前にする。"""
        return self.target_path(post).with_suffix(_IMAGE_SUFFIX)

    def attach_image(self, post: BlogPost, image_path: Path | str) -> Path:
        """アイキャッチを WebP に変換してサイトリポジトリへ置き、その置き場を返す。

        Raises:
            StaticSitePublishError: 元画像が無い、または変換に失敗した場合
        """
        src = Path(image_path).expanduser()
        if not src.is_file():
            raise StaticSitePublishError(f"アイキャッチ画像が見つかりません: {src}")

        dest = self.image_path(post)
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(src) as im:
                im.save(dest, format="WEBP", quality=_IMAGE_QUALITY)
        except OSError as exc:
            raise StaticSitePublishError(f"アイキャッチの変換に失敗しました: {exc}") from exc
        return dest

    def target_path(self, post: BlogPost) -> Path:
        return self._repo / _CONTENT_DIR / post.content_type / f"{self.resolve_slug(post)}.md"

    async def publish(
        self,
        post: BlogPost,
        status: str = "draft",
        commit: bool = True,
        push: bool = False,
        overwrite: bool = False,
        featured_image_path: Path | str | None = None,
        **kwargs: object,
    ) -> PublishResult:
        """記事を静的サイトのリポジトリへ書き出す。

        Args:
            post: 投稿するBlogPost
            status: "publish" なら公開扱い、それ以外はサイト側でビルド対象外の下書き
            commit: git commit まで行うか
            push: commit 後に push するか。push した時点でサイトのデプロイが走るため、
                既定では行わない（呼び出し側で明示的に指定する）
            overwrite: 既存ファイルを上書きするか
            featured_image_path: アイキャッチ画像のローカルパス。WebP に変換して
                記事Markdownの隣に置き、frontmatter の `image` に相対パスを書く。
                未指定でも既に置かれている画像があればその参照を残す（上書き publish で
                画像だけが黙って消えるのを防ぐ）
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

        image_file: Path | None = None
        if featured_image_path is not None:
            image_file = self.attach_image(post, featured_image_path)
        elif self.image_path(post).is_file():
            image_file = self.image_path(post)

        image_ref = f"./{image_file.name}" if image_file else None
        content = post.content.rstrip("\n") + "\n"
        text = (
            self.build_frontmatter(post, published=status == "publish", image=image_ref)
            + "\n"
            + content
        )

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except OSError as exc:
            raise StaticSitePublishError(f"ファイル書き出しに失敗しました: {exc}") from exc

        url = f"/blog/{post.content_type}/{self.resolve_slug(post)}/"
        if commit:
            self._commit(path, post, image_file)
            if push:
                self._push()
        return PublishResult(success=True, url=url)

    def _push(self) -> None:
        try:
            subprocess.run(
                ["git", "push"],
                cwd=self._repo,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise StaticSitePublishError(
                f"git push に失敗しました（commit は完了しています）: {exc.stderr or exc.stdout}"
            ) from exc

    def _commit(self, path: Path, post: BlogPost, image_file: Path | None = None) -> None:
        # アイキャッチを含めないと、frontmatter だけ image を指してファイルが無い
        # 状態がコミットされ、サイトのビルドが落ちる
        targets = [str(path.relative_to(self._repo))]
        if image_file is not None:
            targets.append(str(image_file.relative_to(self._repo)))
        message = f"post: {post.title}\n\nSource: social-content-creator ({post.content_type})"
        try:
            subprocess.run(
                ["git", "add", "--", *targets],
                cwd=self._repo,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "commit", "-m", message, "--", *targets],
                cwd=self._repo,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise StaticSitePublishError(
                f"git commit に失敗しました: {exc.stderr or exc.stdout}"
            ) from exc
