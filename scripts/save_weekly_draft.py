"""weekly-ai-news 第3週ドラフトを保存するランナー。"""

import asyncio
from pathlib import Path

from src.generators.blog_post import BlogPostGenerator

BODY_PATH = Path("scripts/weekly_body_202663.md")
TITLE = "【2026年6月第3週】週刊AIニュースハイライト"
SUBTITLE = "Claude遮断が日本に波及、ソフトバンクのAI防衛、企業の“成果創出”フェーズ"
TYPE = "weekly-ai-news"
TOPIC = "週刊AIニュース 2026年6月第3週"


async def main() -> None:
    content = BODY_PATH.read_text(encoding="utf-8")
    gen = BlogPostGenerator()
    post = await gen.generate(
        content_type=TYPE,
        title=TITLE,
        content=content,
        subtitle=SUBTITLE,
        topic=TOPIC,
    )
    path = await gen.save_draft(post)
    print(f"保存先: {path}")
    print(f"slug: {post.slug}")
    print(f"本文文字数: {len(content)}")


if __name__ == "__main__":
    asyncio.run(main())
