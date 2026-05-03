"""アイキャッチ画像生成用プロンプト組み立てユーティリティ。"""

from __future__ import annotations

from src.models.blog_post import ContentType

_BODY_EXCERPT_MAX_LENGTH = 300

_CONTENT_TYPE_STYLES: dict[ContentType, str] = {
    "weekly-ai-news": (
        "modern tech news magazine cover, futuristic UI elements, " "blue/orange gradient"
    ),
    "paper-review": ("academic, minimal scientific illustration, soft neutral palette"),
    "project-intro": ("vibrant product showcase, clean isometric style, bright colors"),
    "tool-tips": ("tutorial-style flat illustration, friendly developer workspace"),
    "market-analysis": ("data visualization, charts and graphs, financial dashboard aesthetic"),
    "ml-practice": ("developer-focused, code editor and notebook visuals, dark theme"),
    "cv": ("computer vision visualization, neural network overlay, " "image recognition"),
    "feature": ("cinematic hero image, dramatic lighting, high impact"),
}


def build_featured_image_prompt(
    content_type: ContentType,
    title: str,
    body_excerpt: str = "",
) -> str:
    """ブログ記事のアイキャッチ画像生成用プロンプトを組み立てる。

    Args:
        content_type: 記事タイプ。各タイプ固有のスタイル指示が選択される。
        title: 記事タイトル。プロンプト内で被写体テーマとして利用する。
        body_excerpt: 本文冒頭。最大300文字まで使用し、コンテキストを補強する。

    Returns:
        英語ベースの画像生成プロンプト文字列。
    """
    style = _CONTENT_TYPE_STYLES[content_type]
    excerpt = body_excerpt.strip()
    if len(excerpt) > _BODY_EXCERPT_MAX_LENGTH:
        excerpt = excerpt[:_BODY_EXCERPT_MAX_LENGTH]

    parts = [
        f"Featured image for a Japanese AI engineering blog post titled " f'"{title}".',
        f"Style: {style}.",
        "No text, no captions, no logos, no watermarks.",
        "16:9 aspect ratio, high quality, suitable as a WordPress hero image.",
    ]
    if excerpt:
        parts.insert(2, f"Article context: {excerpt}")

    return " ".join(parts)
