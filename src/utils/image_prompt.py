"""アイキャッチ画像生成用プロンプト組み立てユーティリティ。"""

from __future__ import annotations

from src.models.blog_post import ContentType

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
    # 「training a model」と書くと画面に "training model" の文字が描かれる。
    # 動作ではなく物として書く。
    "ml-practice": (
        "a data workshop scene of a node graph, scatter plot, gears, "
        "database cylinders and a laptop showing a bar chart"
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
        "objects connected by simple lines into a flow, grouped as a compact "
        "cluster on two levels rather than a single straight row"
    ),
    "cv": (
        "one main subject framed at the centre with smaller framed objects around it, "
        "a sense of things being detected"
    ),
    "feature": (
        "one large dominant object at the centre with smaller objects spread out "
        "to its left and right, confident and poster-like"
    ),
}

# aidotters.com のトーンに合わせるブランド指示。
#
# 対応する色（プロンプトには hex を書かない。理由は下記）:
#   白地      #ffffff
#   濃紺      #17325b
#   ブランド紺 #1d4e7c  ← サイト src/styles/tokens.css の --accent と同値
#   中間青    #6fa3d6  ← 同 --accent-lift と同値
#   淡青      #a8cbe8
#   ティール  #4fb8a8 / ミント #8fd8cc
#   イエロー  #f2c94c / サンド #f7e2a3
#
# ティールとイエローはイラスト専用の拡張色で、tokens.css には無い。
# サイトの UI 色に足すかどうかは別の判断なので、ここを変えても
# サイト側 tokens.css は追従しない点に注意。
#
# hex をプロンプトに書いてはいけない。画像モデルは hex を色として解釈せず、
# 端末の画面などに "6FA32D6" のような崩れた文字列として描画してしまう
# （2026-08-22 に weekly-ai-news 12枚中4枚で実測）。色は言語記述だけで
# 十分に再現されるため、hex はプロンプト内では純粋なノイズになる。
_BRAND_STYLE_DIRECTIVE = (
    "Art direction: flat vector illustration, the style of modern editorial "
    "stock illustration. Bold simple filled shapes with rounded corners, "
    "no outlines or only sparse thin outlines, no shading, no gradients. "
    "Pure white background. "
    "Palette, used in this order of dominance: deep navy and brand navy blue "
    "for the main shapes, medium blue and light blue "
    "for the secondary shapes, teal and mint as a lighter accent, "
    "and warm yellow with sand as a small highlight accent only. "
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
    "Do not draw newspapers, printed headlines or colour codes. "
    "Document and screen shapes are drawn with plain coloured bars "
    "instead of text — no headline, no title bar text, no chart axis labels. "
    "Purely visual illustration with shapes, colors and imagery only."
)

# 上下端に置く水平構造（上から吊るすもの / 下で受けるもの）。
#
# 白地にオブジェクトを浮かせただけだと、上下の境目が無く絵が宙に浮いて見える。
# 参考にした元のアイキャッチ（Vexels の Factory Automation / Business Workflow
# Automation）は、上端のレールと下端のコンベアが絵の枠を作っていた。
#
# 構造そのものは共通のルール（濃紺・細い・端から端まで）で揃え、それが何で
# あるかだけを記事タイプごとに変える。これで統一感を保ちつつ内容に合う絵になる。
# 無地の帯にすると単なる罫線に見えるため、必ず等間隔で反復するディテールを持たせる。
_CONTENT_TYPE_FRAMES: dict[ContentType, tuple[str, str]] = {
    "weekly-ai-news": (
        "a ruler strip with evenly spaced tick marks",
        "a timeline rail with large round station markers at even intervals",
    ),
    # 上の棚板を上端ぴったりに置くと、その上に立つ本がフレーム外で切れる。
    # 少し下げて、本が収まる高さを空ける。
    "paper-review": (
        "an upper bookshelf plank set a little below the top edge, lined with upright "
        "books and box files standing on it",
        "a bookshelf plank along the very bottom edge, lined with upright books " "and bookends",
    ),
    "project-intro": (
        "an overhead rail with evenly spaced hooks, each carrying a hanging part",
        "a conveyor belt with a row of evenly spaced rollers",
    ),
    "tool-tips": (
        "a pegboard strip with evenly spaced holes and small hooks",
        "a desk surface with a row of drawer handles along its front edge",
    ),
    "market-analysis": (
        "an overhead rail with evenly spaced screens hanging from it, each showing "
        "a small chart",
        "a trading desk counter with evenly spaced panel seams along its front",
    ),
    "ml-practice": (
        "a cable tray with evenly spaced clamps holding bundled cables",
        "a platform with evenly spaced pedestals joined left to right by arrows",
    ),
    "cv": (
        "a scan strip with evenly spaced measurement notches and corner brackets",
        "a graph-paper base with a fine even grid",
    ),
    "feature": (
        "a lighting bar with evenly spaced round lamps",
        "a stage floor with evenly spaced plank seams and small footlights",
    ),
}


def _frame_directive(top: str, bottom: str) -> str:
    """上下の水平構造と、その間の埋め方を指示する文を組み立てる。

    指示を盛るほど良くなるわけではない。「余白を作るな」と重ねて書くと、
    構造だけが太って中身が薄くなる挙動を実測しているので、ここは短く保つ。
    """
    return (
        f"Framing: along the very top edge, {top}. Along the very bottom edge, {bottom}. "
        "Both are deep navy, slim (about 7 percent of the frame height), and run "
        "unbroken from the very left edge to the very right edge. Each carries its "
        "repeating detail across its whole length; neither is a plain solid bar. "
        "Some objects hang from the upper one, the rest rest on the lower one, and "
        "together they fill the space between the two structures from side to side."
    )


# 絵の詰まり具合。手本にした市販のフラットイラストは、要素が大きく少し重なり
# 合っていて隙間が少ない（塗られた画素の割合で 39% / 41%）。
# 何も言わないと 20% 台の薄い絵になりやすいので、大きさと重なりを明示する。
# ただし指示だけでは安定しない（実測で 43% と 13% に振れた）ため、
# 生成側で密度を測って引き直す（src/utils/image_retry.py）。
_DENSITY_DIRECTIVE = (
    "The objects are drawn large — each roughly a third of the gap's height — and "
    "overlap each other slightly, so they read as one dense cluster rather than "
    "separate icons with space around them. "
    # 手本にした市販イラストでは、ロボットアームが天井のレールから下のコンベアまで
    # 届いていて、それが縦の空きを埋めていた。上下をつなぐ背の高い要素を入れる。
    "At least two objects are tall enough to bridge the gap, running from the upper "
    "structure down to the lower one. Objects that hang from the upper structure do so "
    "on short lines, sitting close beneath it, so no empty band is left under it. "
    # 構造そのものがフレーム端から浮くと、そのぶん上下に白帯ができる。
    "The upper structure's top side touches the top edge of the frame and the lower "
    "structure's bottom side touches the bottom edge: there is no white space above "
    "the upper structure or below the lower one."
)

_COMPOSITION_DIRECTIVE = (
    "The scene fills the entire 16:9 frame edge to edge. "
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
        title: 記事タイトル。呼び出し側の互換のため受け取るが、プロンプトには
            含めない（画像モデルが日本語を文字として描画してしまうため）。
        body_excerpt: 本文冒頭。title と同じ理由でプロンプトには含めない。

    Returns:
        英語ベースの画像生成プロンプト文字列。
    """
    style = _CONTENT_TYPE_STYLES[content_type]
    subject = _CONTENT_TYPE_SUBJECTS[content_type]
    top, bottom = _CONTENT_TYPE_FRAMES[content_type]

    # 日本語の title / body_excerpt はプロンプトに含めない。
    # 画像モデルがそれらを文字として描画し、崩れた日本語が混入するため、
    # 被写体は英語の記述のみで表現する。
    parts = [
        f"Featured illustration for an AI engineering blog post: {subject}.",
        _BRAND_STYLE_DIRECTIVE,
        f"Layout: {style}.",
        _frame_directive(top, bottom),
        _DENSITY_DIRECTIVE,
        _ANTI_STYLE_DIRECTIVE,
        _NO_TEXT_DIRECTIVE,
        _COMPOSITION_DIRECTIVE,
        "16:9 aspect ratio, high quality, suitable as a blog hero image.",
    ]

    return " ".join(parts)
