"""絵の詰まり具合を見て、薄い画像を引き直す。

画像モデルは同じプロンプトでも、絵がフレームを埋めることもあれば、
中央に小さくまとまって周りが白いだけの絵になることもある。これは
プロンプトの書き方では安定せず（2026-08-22 に構図指示を複数試行）、
指示を重ねるとかえって構造だけが太って中身が薄くなった。

引き直しのほうが確実なので、生成後に密度を測り、薄ければ引き直す。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from PIL import Image

from src.utils.image_trim import content_density

if TYPE_CHECKING:
    from src.generators.image import AspectRatio

# 目標とする密度の範囲。手本にした市販のフラットイラスト2点は 39% / 41%。
# 下限はそこから少し譲った値で、これを下回ると絵が白地に浮いて見える。
# 上限は詰まりすぎてうるさくなる手前。
_MIN_DENSITY = 0.30
_MAX_DENSITY = 0.60
_MAX_ATTEMPTS = 3


class _ImageGenerator(Protocol):
    """必要な部分だけの GeminiImageGenerator の形。テストで差し替えられる。"""

    async def generate(
        self,
        prompt: str,
        *,
        aspect_ratio: AspectRatio = ...,
        filename: str | None = ...,
        slug: str | None = ...,
    ) -> Path: ...


async def generate_with_density(
    generator: _ImageGenerator,
    prompt: str,
    *,
    aspect_ratio: AspectRatio = "16:9",
    filename: str | None = None,
    slug: str | None = None,
    min_density: float = _MIN_DENSITY,
    max_density: float = _MAX_DENSITY,
    max_attempts: int = _MAX_ATTEMPTS,
) -> tuple[Path, float, int]:
    """密度が範囲に入るまで引き直しつつ生成する。

    範囲に入らないまま試行回数を使い切った場合は、いちばん範囲の中心に
    近かった1枚を返す。生成に失敗した場合の例外はそのまま呼び出し元へ通す。

    Returns:
        (画像パス, その画像の密度, 実際に生成した枚数)
    """
    target = (min_density + max_density) / 2
    best: tuple[Path, float] | None = None

    for attempt in range(1, max_attempts + 1):
        path = await generator.generate(
            prompt=prompt, aspect_ratio=aspect_ratio, filename=filename, slug=slug
        )
        with Image.open(path) as opened:
            density = content_density(opened.convert("RGB"))

        if min_density <= density <= max_density:
            return (path, density, attempt)

        # 引き直すと filename 指定時は同じパスを上書きするため、
        # 「いちばんマシな1枚」を残すには別名で控えておく必要がある。
        if best is None or abs(density - target) < abs(best[1] - target):
            keep = path.with_name(f"{path.stem}--best{path.suffix}")
            keep.write_bytes(path.read_bytes())
            best = (keep, density)

    assert best is not None
    kept, density = best
    final = kept.with_name(kept.stem.removesuffix("--best") + kept.suffix)
    final.write_bytes(kept.read_bytes())
    kept.unlink()
    return (final, density, max_attempts)
