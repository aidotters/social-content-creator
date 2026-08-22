"""generate_with_density のテスト。"""

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from src.utils.image_retry import generate_with_density


class _FakeGenerator:
    """指定した密度の画像を順に返す、生成器の差し替え。"""

    def __init__(self, densities: list[float], out_dir: Path) -> None:
        self._densities = densities
        self._out_dir = out_dir
        self.calls = 0

    async def generate(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "16:9",
        filename: str | None = None,
        slug: str | None = None,
    ) -> Path:
        ratio = self._densities[self.calls]
        self.calls += 1
        im = Image.new("RGB", (320, 180), (255, 255, 255))
        # 指定した割合だけ塗る
        filled_width = int(320 * ratio)
        ImageDraw.Draw(im).rectangle((0, 0, filled_width, 180), fill=(29, 78, 124))
        path = self._out_dir / (filename or "out.png")
        im.save(path)
        return path


@pytest.mark.asyncio
async def test_returns_first_image_within_range(tmp_path: Path) -> None:
    """密度が範囲内なら1回で返す。"""
    gen = _FakeGenerator([0.40], tmp_path)
    path, density, attempts = await generate_with_density(
        gen, "prompt", filename="a.png", min_density=0.28, max_density=0.60
    )
    assert attempts == 1
    assert gen.calls == 1
    assert 0.28 <= density <= 0.60
    assert path.is_file()


@pytest.mark.asyncio
async def test_retries_while_too_sparse(tmp_path: Path) -> None:
    """薄い画像が続く間は引き直し、範囲に入った時点で返す。"""
    gen = _FakeGenerator([0.10, 0.15, 0.45], tmp_path)
    _, density, attempts = await generate_with_density(
        gen, "prompt", filename="b.png", min_density=0.28, max_density=0.60
    )
    assert attempts == 3
    assert gen.calls == 3
    assert density >= 0.28


@pytest.mark.asyncio
async def test_keeps_best_when_never_in_range(tmp_path: Path) -> None:
    """一度も範囲に入らなければ、範囲の中心に最も近い1枚を残す。"""
    gen = _FakeGenerator([0.05, 0.20, 0.02], tmp_path)
    path, density, attempts = await generate_with_density(
        gen, "prompt", filename="c.png", min_density=0.28, max_density=0.60
    )
    assert attempts == 3
    # 0.20 が最も中心（0.44）に近い
    assert 0.18 <= density <= 0.22
    assert path.is_file()
    assert not path.with_name(f"{path.stem}--best{path.suffix}").exists()


@pytest.mark.asyncio
async def test_does_not_retry_when_dense_enough_on_first_try(tmp_path: Path) -> None:
    """濃すぎる場合も引き直す。"""
    gen = _FakeGenerator([0.95, 0.35], tmp_path)
    _, density, attempts = await generate_with_density(
        gen, "prompt", filename="d.png", min_density=0.28, max_density=0.60
    )
    assert attempts == 2
    assert density <= 0.60
