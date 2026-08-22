"""trim_to_16x9 / content_bbox のテスト。"""

from pathlib import Path

from PIL import Image, ImageDraw

from src.utils.image_trim import content_bbox, trim_to_16x9


def _canvas(size: tuple[int, int] = (320, 180), bg: tuple[int, int, int] = (255, 255, 255)):
    return Image.new("RGB", size, bg)


def test_content_bbox_finds_centered_object() -> None:
    """中央に置いた被写体の外接矩形が取れる。"""
    im = _canvas()
    ImageDraw.Draw(im).rectangle((100, 60, 200, 120), fill=(29, 78, 124))
    bbox = content_bbox(im)
    assert bbox is not None
    left, top, right, bottom = bbox
    assert 95 <= left <= 105
    assert 55 <= top <= 65
    assert 195 <= right <= 205
    assert 115 <= bottom <= 125


def test_content_bbox_returns_none_for_blank_image() -> None:
    """地の色だけの画像では None を返す。"""
    assert content_bbox(_canvas()) is None


def test_content_bbox_ignores_faint_background_noise() -> None:
    """地のわずかなムラは被写体として拾わない。

    生成画像の地には微妙なムラがあり、これを拾うと余白が詰まらない。
    """
    im = _canvas()
    # 地とほとんど差のない点を隅に散らす
    for xy in ((5, 5), (310, 8), (12, 170)):
        im.putpixel(xy, (250, 250, 250))
    ImageDraw.Draw(im).rectangle((140, 80, 180, 100), fill=(29, 78, 124))
    bbox = content_bbox(im)
    assert bbox is not None
    assert bbox[0] >= 130
    assert bbox[1] >= 70


def test_trim_enlarges_small_object(tmp_path: Path) -> None:
    """余白だらけの画像は、被写体が枠を占めるように詰められる。"""
    im = _canvas((1344, 768))
    ImageDraw.Draw(im).rectangle((600, 330, 740, 430), fill=(29, 78, 124))
    src = tmp_path / "src.png"
    im.save(src)

    dest = tmp_path / "dest.png"
    assert trim_to_16x9(src, dest) is True

    with Image.open(dest) as out:
        assert out.size == (1344, 768)
        bbox = content_bbox(out.convert("RGB"))
    assert bbox is not None
    # 詰める前は幅の約 10% しかなかった被写体が、大きく育っている
    assert (bbox[2] - bbox[0]) / 1344 > 0.5


def test_trim_keeps_aspect_ratio_and_does_not_clip(tmp_path: Path) -> None:
    """被写体が縦長でも 16:9 に収まり、切り落とされない。"""
    im = _canvas((1344, 768))
    ImageDraw.Draw(im).rectangle((640, 100, 700, 660), fill=(29, 78, 124))
    src = tmp_path / "tall.png"
    im.save(src)

    dest = tmp_path / "tall-out.png"
    trim_to_16x9(src, dest)

    with Image.open(dest) as out:
        assert out.size == (1344, 768)
        bbox = content_bbox(out.convert("RGB"))
    assert bbox is not None
    # 上下が切れていない（被写体の上下に地の色が残っている）
    assert bbox[1] > 0
    assert bbox[3] < 768


def test_trim_handles_tinted_background(tmp_path: Path) -> None:
    """白地でなくても、四隅から地の色を推定して処理できる。"""
    im = _canvas((1344, 768), bg=(235, 240, 245))
    ImageDraw.Draw(im).rectangle((600, 330, 740, 430), fill=(29, 78, 124))
    src = tmp_path / "tinted.png"
    im.save(src)

    dest = tmp_path / "tinted-out.png"
    assert trim_to_16x9(src, dest) is True

    with Image.open(dest) as out:
        # 詰めたあとも地の色は保たれる
        assert out.getpixel((3, 3))[:3] == (235, 240, 245)


def test_trim_crops_inside_source_and_keeps_edge_object(tmp_path: Path) -> None:
    """被写体が端に寄っていても欠けず、切り出しは元画像の内側で行われる。

    元画像の外側を地の色で埋めると、元画像の縁の色ムラとの境目が
    継ぎ目の線として出てしまうため、はみ出す切り出しはしない。
    """
    im = _canvas((1344, 768))
    # 左端に接する被写体
    ImageDraw.Draw(im).rectangle((0, 300, 300, 460), fill=(29, 78, 124))
    src = tmp_path / "edge.png"
    im.save(src)

    dest = tmp_path / "edge-out.png"
    trim_to_16x9(src, dest)

    with Image.open(dest) as out:
        assert out.size == (1344, 768)
        bbox = content_bbox(out.convert("RGB"))
    assert bbox is not None
    # 左端の被写体が残っている（切り出しが左へはみ出していれば消える）。
    # 両端の外れ値を落とす都合で数pxは削れるため、厳密な 0 は求めない。
    assert bbox[0] < 20
    assert bbox[2] - bbox[0] > 100
