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

# 各記事タイプの抽象的なビジュアルテーマ（英語）。
# 日本語タイトル・本文をプロンプトに渡すと画像モデルが文字を描画しようと
# するため、テキスト誘発を避ける目的でこの英語テーマのみを被写体に使う。
_CONTENT_TYPE_SUBJECTS: dict[ContentType, str] = {
    "weekly-ai-news": "abstract artificial intelligence and technology news concept",
    "paper-review": "abstract academic research and scientific discovery concept",
    "project-intro": "abstract open-source software project concept",
    "tool-tips": "abstract developer tools and productivity concept",
    "market-analysis": "abstract financial market and AI investment concept",
    "ml-practice": "abstract machine learning and data analysis concept",
    "cv": "abstract computer vision and image recognition concept",
    "feature": "abstract in-depth AI technology feature concept",
}

# テキスト描画を徹底的に抑制するための強い否定指示。
_NO_TEXT_DIRECTIVE = (
    "Absolutely no text of any kind: no Japanese characters, no kanji, no kana, "
    "no English letters, no words, no numbers, no captions, no labels, "
    "no UI text, no logos, no watermarks, no signage. "
    "Purely visual illustration with shapes, colors and imagery only."
)

# 過去記事との見た目の平仄を合わせるための構図指示。
# 被写体を中央の横帯に収めず、フレーム全体を端まで埋める full-bleed 構図にする。
_COMPOSITION_DIRECTIVE = (
    "Full-bleed composition that fills the entire 16:9 frame edge to edge. "
    "No border, no inner frame, no letterbox bars, no empty margins. "
    "The main subject is balanced and fills the vertical space of the frame."
)


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
    subject = _CONTENT_TYPE_SUBJECTS[content_type]

    # 日本語の title / body_excerpt はプロンプトに含めない。
    # 画像モデルがそれらを文字として描画し、崩れた日本語が混入するため、
    # 被写体は英語の抽象テーマのみで表現する。
    parts = [
        f"Featured image for an AI engineering blog post: {subject}.",
        f"Style: {style}.",
        _NO_TEXT_DIRECTIVE,
        _COMPOSITION_DIRECTIVE,
        "16:9 aspect ratio, high quality, suitable as a WordPress hero image.",
    ]

    return " ".join(parts)
