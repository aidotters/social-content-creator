"""Gemini画像生成エンジン（gemini-2.5-flash-image / Nanobanana）。"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types

from src.errors import ImageGenerationError

if TYPE_CHECKING:
    from collections.abc import Iterable

AspectRatio = Literal["1:1", "3:4", "4:3", "9:16", "16:9"]

_MODEL = "gemini-2.5-flash-image"
_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


class GeminiImageGenerator:
    """Gemini APIで画像生成するGenerator。

    Google AI Studioの無料枠で `gemini-2.5-flash-image` を利用する。
    環境変数 `GEMINI_API_KEY` が必須。
    """

    def __init__(
        self,
        *,
        output_dir: Path | None = None,
        api_key: str | None = None,
    ) -> None:
        load_dotenv()
        self._output_dir = output_dir or Path("outputs/images")
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self._api_key:
            raise ImageGenerationError(
                "GEMINI_API_KEY が未設定です。.env または環境変数で設定してください。"
            )
        self._client = genai.Client(api_key=self._api_key)

    async def generate(
        self,
        prompt: str,
        *,
        aspect_ratio: AspectRatio = "16:9",
        filename: str | None = None,
        slug: str | None = None,
    ) -> Path:
        """プロンプトから画像を生成し、ファイルに保存する。

        Args:
            prompt: 画像生成プロンプト
            aspect_ratio: アスペクト比（"16:9", "1:1", "9:16", "4:3", "3:4"）
            filename: 保存ファイル名（拡張子込み）。指定時は `slug` を無視
            slug: ファイル名の接頭辞。未指定時はプロンプトから自動生成

        Returns:
            保存した画像ファイルのパス

        Raises:
            ImageGenerationError: API呼び出しまたは画像抽出に失敗した場合
        """
        if not prompt.strip():
            raise ImageGenerationError("prompt が空です。")

        try:
            response = await self._client.aio.models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
                ),
            )
        except Exception as e:
            raise ImageGenerationError(f"Gemini API呼び出し失敗: {e}") from e

        image = _extract_first_image(response.parts)
        if image is None:
            raise ImageGenerationError(
                "レスポンスに画像が含まれていません。プロンプトがセーフティ拒否された可能性があります。"
            )

        output_path = self._resolve_output_path(filename=filename, slug=slug, prompt=prompt)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(output_path))
        return output_path

    def _resolve_output_path(self, *, filename: str | None, slug: str | None, prompt: str) -> Path:
        if filename:
            return self._output_dir / filename
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        base = _slugify(slug or prompt)
        return self._output_dir / f"{timestamp}-{base}.png"


# part.as_image() が返すのは PIL ではなく google-genai の Image。
# Pillow が入っていなかった間は PIL.Image を指したまま検査を素通りしていた。
def _extract_first_image(parts: Iterable[types.Part] | None) -> types.Image | None:
    if parts is None:
        return None
    for part in parts:
        if getattr(part, "inline_data", None):
            image = part.as_image()
            return image
    return None


def _slugify(text: str, max_length: int = 40) -> str:
    lowered = text.strip().lower()
    cleaned = _SLUG_PATTERN.sub("-", lowered).strip("-")
    if not cleaned:
        cleaned = "image"
    return cleaned[:max_length].rstrip("-") or "image"
