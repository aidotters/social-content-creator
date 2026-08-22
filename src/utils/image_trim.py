"""生成画像の余白を詰めて 16:9 に収め直すユーティリティ。

画像モデルはフレームいっぱいに描くのが苦手で、被写体を中央に小さくまとめ、
周囲に広い余白を残す。「フレームの端まで埋めろ」と指示しても安定しない
（2026-08-22 に複数の構図指示で試行し、いずれも上下または左右が空いた）。
プロンプトで粘るより、描かせたあとに余白を落とすほうが確実なため、
生成とサイトへの配置の間にこの処理を挟む。
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PIL import Image, ImageChops

# 地の色とみなす差の上限（RGB各チャンネルの最大差）。生成画像の地には微妙な
# ムラがあり、小さすぎるとムラを被写体と誤検出して余白が詰まらない
# （実測で 8 相当では検出に失敗した）。
_BG_TOLERANCE = 16

# 被写体の範囲を決めるときに、端から切り捨てる量（被写体画素の総量に対する割合）。
# 生成画像は左上の隅がわずかに暗くなることがあり（Gemini の出力の癖。実測で
# 31枚中15枚）、単純に「最初に閾値を超えた行」を上端にすると、その暗みを
# 被写体と見なして外接矩形が画像全体に広がってしまう。
# 累積で見て外れ値を捨てることで、隅の小さなムラに引きずられなくなる。
_EDGE_TRIM_QUANTILE = 0.01

# 被写体の周りに残す余白。被写体の長辺に対する比率。
_MARGIN_RATIO = 0.05

_TARGET_SIZE = (1344, 768)
_ASPECT = 16 / 9


def _background_color(im: Image.Image) -> tuple[int, int, int]:
    """画像全体の最頻色を地の色とみなす。

    四隅から取る方法は使えない。アイキャッチは上下端に濃紺の構造（レールや
    コンベア）を敷く構図なので、四隅が必ずその構造で塗られ、地の色を濃紺と
    誤って推定してしまう（実測で密度が 91% と出た）。
    """
    # 100万画素を数えるのは無駄なので縮小してから。地の色は面積が大きく、
    # 縮小しても最頻であることは変わらない。
    small = im.resize((im.width // 8, im.height // 8), Image.Resampling.BOX)
    colors = small.getcolors(maxcolors=small.width * small.height)
    if not colors:
        return (255, 255, 255)
    _, most_common = max(colors, key=lambda pair: pair[0])
    return cast("tuple[int, int, int]", most_common)


def _content_mask(im: Image.Image, bg: tuple[int, int, int]) -> Image.Image:
    """地の色と異なる画素を 255 にした2値マスクを返す。"""
    diff = ImageChops.difference(im, Image.new("RGB", im.size, bg))
    red, green, blue = diff.split()
    # 輝度変換だと地と明度が近い色を取り落とすので、チャンネルごとの最大差を使う
    largest = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return largest.point(lambda v: 255 if v > _BG_TOLERANCE else 0)


def _span(weights: list[float]) -> tuple[int, int] | None:
    """重みの並びから、両端の外れ値を捨てた範囲を返す。

    端から順に累積し、全体の _EDGE_TRIM_QUANTILE 分を捨てた位置を境界にする。
    隅のわずかなムラのような、量の小さい外れ値には引きずられない。
    """
    total = sum(weights)
    if total <= 0:
        return None
    cutoff = total * _EDGE_TRIM_QUANTILE

    acc = 0.0
    start = 0
    for i, value in enumerate(weights):
        acc += value
        if acc > cutoff:
            start = i
            break

    acc = 0.0
    end = len(weights) - 1
    for i in range(len(weights) - 1, -1, -1):
        acc += weights[i]
        if acc > cutoff:
            end = i
            break

    return (start, end) if start <= end else None


def content_density(im: Image.Image) -> float:
    """地の色でない画素が画像全体に占める割合を返す。

    絵がどれだけ詰まっているかの指標。外接矩形の広さでは測れない
    （上下に端まで伸びる構造が1本あるだけで矩形は全画面になるが、
    中身は薄いままということが起こる）。

    参考値: 手本にした市販のフラットイラスト2点は 39% と 41% だった。
    """
    mask = _content_mask(im, _background_color(im))
    width, height = im.size
    return sum(mask.histogram()[255:]) / (width * height)


def content_bbox(im: Image.Image) -> tuple[int, int, int, int] | None:
    """被写体の外接矩形を返す。全面が地の色なら None。

    行・列ごとの被写体画素の量を1px幅への縮小（BOX = 平均）で求め、
    両端の外れ値を落とした範囲を被写体とみなす。
    """
    w, h = im.size
    mask = _content_mask(im, _background_color(im))

    row_means = mask.resize((1, h), Image.Resampling.BOX)
    col_means = mask.resize((w, 1), Image.Resampling.BOX)
    vertical = _span([cast(int, row_means.getpixel((0, y))) / 255 for y in range(h)])
    horizontal = _span([cast(int, col_means.getpixel((x, 0))) / 255 for x in range(w)])
    if vertical is None or horizontal is None:
        return None
    return (horizontal[0], vertical[0], horizontal[1] + 1, vertical[1] + 1)


def trim_to_16x9(src: Path | str, dest: Path | str, min_reduction: float = 0.0) -> bool:
    """余白を詰めて 16:9 に組み直し、dest へ保存する。

    Args:
        src: 元画像
        dest: 保存先
        min_reduction: これ以上詰められるときだけ実際に詰める（面積比）。
            0.08 なら「8%以上小さくできる画像だけ処理する」。既に絵が
            フレームを埋めている画像や、一度詰めた画像を触らずに済む。
            既定の 0.0 は常に詰める。

    Returns:
        余白を詰めた場合 True、詰める余地がなかった場合 False。
        False でも dest には（サイズを揃えた）画像が保存される。
    """
    src, dest = Path(src), Path(dest)
    with Image.open(src) as opened:
        im = opened.convert("RGB")
        src_w, src_h = im.size
        bbox = content_bbox(im)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if bbox is None:
            im.resize(_TARGET_SIZE, Image.Resampling.LANCZOS).save(dest)
            return False

        left, top, right, bottom = bbox
        obj_w, obj_h = right - left, bottom - top
        margin = int(max(obj_w, obj_h) * _MARGIN_RATIO)
        target_w, target_h = obj_w + margin * 2, obj_h + margin * 2

        # 被写体を切らずに 16:9 へ。足りない側を広げる。
        if target_w / target_h < _ASPECT:
            target_w = round(target_h * _ASPECT)
        else:
            target_h = round(target_w / _ASPECT)

        # 切り出しは必ず元画像の内側で行う。外側を地の色で埋めると、元画像の
        # 縁にあるわずかな色ムラとの境目が継ぎ目の線になって出る。
        # 元画像も 16:9 なので、上限まで広げてもアスペクト比は保たれる。
        if target_w > src_w or target_h > src_h:
            target_w, target_h = src_w, src_h

        # 詰め幅が小さい画像は触らない。絵が既にフレームを埋めている場合や、
        # 一度詰めた画像を再エンコードするだけの処理を避ける。
        reduction = 1 - (target_w * target_h) / (src_w * src_h)
        if reduction < min_reduction:
            im.resize(_TARGET_SIZE, Image.Resampling.LANCZOS).save(dest)
            return False

        cx, cy = (left + right) // 2, (top + bottom) // 2
        x = min(max(cx - target_w // 2, 0), src_w - target_w)
        y = min(max(cy - target_h // 2, 0), src_h - target_h)

        cropped = im.crop((x, y, x + target_w, y + target_h))
        cropped.resize(_TARGET_SIZE, Image.Resampling.LANCZOS).save(dest)
        return (target_w, target_h) != (src_w, src_h)
