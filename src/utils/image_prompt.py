"""アイキャッチ画像生成用プロンプト組み立てユーティリティ。"""

from __future__ import annotations

from src.models.blog_post import ContentType

_BODY_EXCERPT_MAX_LENGTH = 300

# 各記事タイプの被写体。
# 日本語タイトル・本文をプロンプトに渡すと画像モデルが文字を描画しようと
# するため、テキスト誘発を避ける目的でこの英語の記述のみを被写体に使う。
# 抽象形ではなく具体物を並べるのは、記事タイプごとの違いを絵で出すため。
_CONTENT_TYPE_SUBJECTS: dict[ContentType, str] = {
    # 「新聞」と書くと見出しの "NEWS" が必ず描かれるので、紙媒体は被写体に入れない。
    "weekly-ai-news": (
        "tablet and phone screens showing card layouts, floating panels, "
        "speech bubbles, bell notifications, small satellite dishes and signal waves"
    ),
    "paper-review": (
        "a research desk scene of stacked papers with a magnifying glass, "
        "microscope, beaker, bar and line charts, bookmarks and clipped documents"
    ),
    "project-intro": (
        "a workshop scene of stacked building blocks and boxes, "
        "shipping crates, plugged-together modules, a rocket and folder icons"
    ),
    "tool-tips": (
        "a developer desk scene of a laptop, wrench and screwdriver, gears, "
        "checklists, sticky notes and stacked window panels"
    ),
    "market-analysis": (
        "a market dashboard scene of bar charts, a rising line graph, "
        "coin stacks, pie chart and arrow indicators on floating panels"
    ),
    "ml-practice": (
        "a data workshop scene of a node graph, scatter plot, gears, "
        "database cylinders and a laptop training a model"
    ),
    "cv": (
        "a computer vision scene of a camera and lens, framed detection boxes "
        "around simple objects, an eye motif and grid overlays"
    ),
    "feature": (
        "a feature scene of one large central machine or robot arm assembling "
        "smaller shapes, surrounded by supporting objects and plant leaves"
    ),
}

# 各記事タイプの構図・見せ方。被写体（_CONTENT_TYPE_SUBJECTS）が「何を描くか」、
# こちらは「どう並べるか」。配色はブランド共通（_BRAND_STYLE_DIRECTIVE）で固定し、
# タイプごとの差はモチーフと構図だけで付ける。
_CONTENT_TYPE_STYLES: dict[ContentType, str] = {
    "weekly-ai-news": (
        "objects laid out side by side like a magazine spread, "
        "several items of similar weight, lively but orderly"
    ),
    "paper-review": (
        "a calm, orderly arrangement centred on the desk, "
        "fewer objects with more space between them"
    ),
    "project-intro": (
        "objects stacked and connected into one structure at the centre, "
        "a sense of assembly and construction"
    ),
    "tool-tips": (
        "objects arranged around a central workspace, "
        "friendly and approachable, slight overlap between items"
    ),
    "market-analysis": (
        "panels and charts arranged on a shallow grid, "
        "one chart clearly larger than the rest as the focal point"
    ),
    "ml-practice": (
        "objects connected by simple lines into a flow from left to right, "
        "a sense of pipeline and process"
    ),
    "cv": (
        "one main subject framed at the centre with smaller framed objects around it, "
        "a sense of things being detected"
    ),
    "feature": (
        "one large dominant object at the centre with smaller objects orbiting it, "
        "confident and poster-like"
    ),
}

# aidotters.com のトーンに合わせるブランド指示。
# 青系は同サイトの src/styles/tokens.css（ライト側）と揃えてある:
#   accent #1d4e7c / accent-lift #6fa3d6 / 文字色 #16202b
# ティールとイエローはイラスト専用の拡張色で、tokens.css には無い。
# サイトの UI 色に足すかどうかは別の判断なので、ここを変えても
# サイト側 tokens.css は追従しない点に注意。
# 画像モデルは hex を忠実には再現しないので、色名の言語記述を併記する。
_BRAND_STYLE_DIRECTIVE = (
    "Art direction: flat vector illustration, the style of modern editorial "
    "stock illustration. Bold simple filled shapes with rounded corners, "
    "no outlines or only sparse thin outlines, no shading, no gradients. "
    "Pure white background (#ffffff). "
    "Palette, used in this order of dominance: deep navy (#17325b) and brand navy "
    "(#1d4e7c) for the main shapes, medium blue (#6fa3d6) and light blue (#a8cbe8) "
    "for the secondary shapes, teal (#4fb8a8) and mint (#8fd8cc) as a lighter accent, "
    "and warm yellow (#f2c94c) with sand (#f7e2a3) as a small highlight accent only. "
    "A few simple leaf and plant sprigs may be scattered between the objects. "
    "Cheerful, clean and confident."
)

# 上の指示だけでは学習の強い先入観（SF調のダークUI）に引き戻されるため、
# 反対方向を明示的に禁止する。
_ANTI_STYLE_DIRECTIVE = (
    "Do not use: dark or black backgrounds, neon glow, lens flare, bokeh particles, "
    "sci-fi HUD, holograms, glowing wireframe globes, circuit-board patterns, "
    "3D renders, photorealism, painterly texture, drop shadows, "
    "colour gradients, purple or magenta, saturated red."
)

# テキスト描画を徹底的に抑制するための強い否定指示。
_NO_TEXT_DIRECTIVE = (
    "Absolutely no text of any kind: no Japanese characters, no kanji, no kana, "
    "no English letters, no words, no numbers, no captions, no labels, "
    "no UI text, no logos, no watermarks, no signage. "
    "Do not draw newspapers or printed headlines. "
    "Document and screen shapes are drawn with plain coloured bars "
    "instead of text — no headline, no title bar text, no chart axis labels. "
    "Purely visual illustration with shapes, colors and imagery only."
)

# 構図指示。地は白なのでオブジェクトの周りに余白が出るのが正しいが、
# 放っておくと絵が小さくまとまり、hero 枠の中で寂しくなる。
# 「白地は残す」と「絵は大きく」を両立させるため、占有率を明示する。
_COMPOSITION_DIRECTIVE = (
    "Composition: the objects form one connected group, spread horizontally across "
    "the 16:9 frame and occupying roughly 85 percent of its width and height, "
    "with one clear focal object. The remaining white background reads as even margin. "
    "No border, no inner frame, no letterbox bars, no background panel or card."
)


def build_featured_image_prompt(
    content_type: ContentType,
    title: str,
    body_excerpt: str = "",
) -> str:
    """ブログ記事のアイキャッチ画像生成用プロンプトを組み立てる。

    Args:
        content_type: 記事タイプ。各タイプ固有の被写体・構図指示が選択される。
        title: 記事タイトル。プロンプト内で被写体テーマとして利用する。
        body_excerpt: 本文冒頭。最大300文字まで使用し、コンテキストを補強する。

    Returns:
        英語ベースの画像生成プロンプト文字列。
    """
    style = _CONTENT_TYPE_STYLES[content_type]
    subject = _CONTENT_TYPE_SUBJECTS[content_type]

    # 日本語の title / body_excerpt はプロンプトに含めない。
    # 画像モデルがそれらを文字として描画し、崩れた日本語が混入するため、
    # 被写体は英語の記述のみで表現する。
    parts = [
        f"Featured illustration for an AI engineering blog post: {subject}.",
        _BRAND_STYLE_DIRECTIVE,
        f"Layout: {style}.",
        _ANTI_STYLE_DIRECTIVE,
        _NO_TEXT_DIRECTIVE,
        _COMPOSITION_DIRECTIVE,
        "16:9 aspect ratio, high quality, suitable as a blog hero image.",
    ]

    return " ".join(parts)
