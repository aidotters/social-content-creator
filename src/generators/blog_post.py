"""ブログ記事生成エンジン。"""

from datetime import UTC, datetime
from pathlib import Path

from src.errors import DraftSaveError
from src.models.blog_post import BlogPost, CollectedData, ContentType
from src.models.template import ContentTemplate
from src.templates import get_template
from src.utils.markdown import generate_slug, read_frontmatter_markdown, write_frontmatter_markdown


class BlogPostGenerator:
    """ブログ記事の生成・保存・管理を行うジェネレーター。"""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or Path(".")

    @property
    def drafts_dir(self) -> Path:
        return self._base_dir / "docs" / "drafts"

    @property
    def posts_dir(self) -> Path:
        return self._base_dir / "docs" / "posts"

    def get_template(self, content_type: ContentType) -> ContentTemplate:
        """テンプレートを取得する。

        Args:
            content_type: コンテンツタイプ

        Returns:
            対応するテンプレート
        """
        return get_template(content_type)

    def build_prompt_context(
        self,
        template: ContentTemplate,
        topic: str | None = None,
        source_url: str | None = None,
        collected_data: list[CollectedData] | None = None,
    ) -> str:
        """記事生成用のプロンプトコンテキストを構築する。

        スキル層（Claude LLM）が記事本文を生成するための情報を整理する。

        Args:
            template: コンテンツテンプレート
            topic: トピック
            source_url: 参照URL
            collected_data: 収集データ

        Returns:
            プロンプトコンテキスト文字列
        """
        parts: list[str] = []
        parts.append(f"# 記事テンプレート: {template.name}")
        parts.append(f"タイプ: {template.content_type}")
        parts.append(f"文字数目安: {template.min_words}〜{template.max_words}字")
        parts.append(f"文体: {template.style_guide}")
        parts.append("")
        parts.append("## セクション構成")
        for i, section in enumerate(template.sections, 1):
            required_mark = "" if section.required else "（任意）"
            parts.append(f"{i}. **{section.title}**{required_mark}")
            parts.append(f"   {section.description}")
        parts.append("")

        if topic:
            parts.append(f"## トピック\n{topic}\n")
        if source_url:
            parts.append(f"## 参照URL\n{source_url}\n")
        if collected_data:
            parts.append("## 収集データ")
            for data in collected_data:
                parts.append(f"### [{data.source}] {data.title}")
                if data.url:
                    parts.append(f"URL: {data.url}")
                parts.append(data.content[:2000])
                parts.append("")

        return "\n".join(parts)

    async def generate(
        self,
        content_type: ContentType,
        title: str,
        content: str,
        topic: str | None = None,
        source_url: str | None = None,
        collected_data: list[CollectedData] | None = None,
    ) -> BlogPost:
        """ブログ記事オブジェクトを生成する。

        記事本文はスキル層（Claude LLM）が生成し、このメソッドに渡される。

        Args:
            content_type: コンテンツタイプ
            title: 記事タイトル
            content: 記事本文（Markdown）
            topic: トピック
            source_url: 参照URL
            collected_data: 収集データ

        Returns:
            生成されたBlogPost
        """
        slug = generate_slug(title)
        return BlogPost(
            title=title,
            content=content,
            content_type=content_type,
            status="draft",
            slug=slug,
            created_at=datetime.now(UTC),
        )

    async def save_draft(self, post: BlogPost) -> Path:
        """記事をドラフトとして保存する。

        Args:
            post: 保存するBlogPost

        Returns:
            保存先のパス

        Raises:
            DraftSaveError: 保存に失敗した場合
        """
        date_str = post.created_at.strftime("%Y%m%d")
        filename = f"{date_str}-{post.slug}.md"
        save_path = self.drafts_dir / post.content_type / filename

        metadata: dict[str, object] = {
            "title": post.title,
            "date": post.created_at.isoformat(),
            "type": post.content_type,
            "status": post.status,
            "slug": post.slug,
        }
        if post.categories:
            metadata["categories"] = post.categories
        if post.tags:
            metadata["tags"] = post.tags

        try:
            write_frontmatter_markdown(save_path, metadata, post.content)
        except OSError as e:
            raise DraftSaveError(path=str(save_path), message=str(e)) from e

        return save_path

    async def load_draft(self, path: Path) -> BlogPost:
        """ドラフトファイルから記事を読み込む。

        Args:
            path: ドラフトファイルのパス

        Returns:
            読み込んだBlogPost
        """
        metadata, content = read_frontmatter_markdown(path)
        return BlogPost(
            title=str(metadata.get("title", "")),
            content=content,
            content_type=metadata.get("type", "weekly-ai-news"),  # type: ignore[arg-type]
            status=metadata.get("status", "draft"),  # type: ignore[arg-type]
            slug=str(metadata.get("slug", "")),
            categories=metadata.get("categories", []),  # type: ignore[arg-type]
            tags=metadata.get("tags", []),  # type: ignore[arg-type]
            created_at=datetime.fromisoformat(
                str(metadata.get("date", datetime.now(UTC).isoformat()))
            ),
        )

    async def move_to_published(self, post: BlogPost, draft_path: Path) -> Path:
        """ドラフトを投稿済みディレクトリに移動する。

        frontmatterにpublished_atフィールドを追加してから移動する。

        Args:
            post: 投稿済みのBlogPost
            draft_path: ドラフトファイルのパス

        Returns:
            移動先のパス
        """
        now = datetime.now(UTC)
        year_month = now.strftime("%Y/%m")
        date_str = now.strftime("%Y%m%d")
        filename = f"{date_str}-{post.content_type}-{post.slug}.md"
        dest_path = self.posts_dir / year_month / filename

        if dest_path.exists():
            raise DraftSaveError(path=str(dest_path), message="移動先ファイルが既に存在します")

        # frontmatterにpublished_atを追加して書き出す
        metadata, content = read_frontmatter_markdown(draft_path)
        metadata["published_at"] = now.isoformat()
        metadata["status"] = "published"
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        write_frontmatter_markdown(dest_path, metadata, content)

        # 元のドラフトファイルを削除
        draft_path.unlink()
        return dest_path
