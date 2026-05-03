"""GeminiImageGeneratorのテスト。"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.errors import ImageGenerationError
from src.generators.image import GeminiImageGenerator


def _fake_response(with_image: bool = True, save_target: Path | None = None) -> MagicMock:
    response = MagicMock()
    if not with_image:
        response.parts = []
        return response

    part = MagicMock()
    part.inline_data = MagicMock()
    image = MagicMock()

    def _save(dest: str) -> None:
        if save_target is not None:
            save_target.write_bytes(b"fake-png")
        else:
            Path(dest).write_bytes(b"fake-png")

    image.save.side_effect = _save
    part.as_image.return_value = image
    response.parts = [part]
    return response


@pytest.fixture
def api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")


class TestGeminiImageGeneratorInit:
    def test_raises_when_api_key_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(ImageGenerationError, match="GEMINI_API_KEY"):
            GeminiImageGenerator()

    def test_uses_explicit_api_key(
        self, monkeypatch: pytest.MonkeyPatch, mocker: Any
    ) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        mocker.patch("src.generators.image.genai.Client")
        gen = GeminiImageGenerator(api_key="explicit")
        assert gen is not None


class TestGenerate:
    @pytest.mark.asyncio
    async def test_saves_image_with_auto_filename(
        self, api_key: None, tmp_path: Path, mocker: Any
    ) -> None:
        client_mock = MagicMock()
        client_mock.aio.models.generate_content = AsyncMock(return_value=_fake_response())
        mocker.patch("src.generators.image.genai.Client", return_value=client_mock)

        gen = GeminiImageGenerator(output_dir=tmp_path)
        path = await gen.generate("テスト画像", slug="hello-world")

        assert path.parent == tmp_path
        assert path.suffix == ".png"
        assert "hello-world" in path.name
        assert path.exists()

    @pytest.mark.asyncio
    async def test_saves_image_with_explicit_filename(
        self, api_key: None, tmp_path: Path, mocker: Any
    ) -> None:
        client_mock = MagicMock()
        client_mock.aio.models.generate_content = AsyncMock(return_value=_fake_response())
        mocker.patch("src.generators.image.genai.Client", return_value=client_mock)

        gen = GeminiImageGenerator(output_dir=tmp_path)
        path = await gen.generate("テスト画像", filename="thumb.png")

        assert path == tmp_path / "thumb.png"
        assert path.exists()

    @pytest.mark.asyncio
    async def test_passes_aspect_ratio_to_config(
        self, api_key: None, tmp_path: Path, mocker: Any
    ) -> None:
        client_mock = MagicMock()
        client_mock.aio.models.generate_content = AsyncMock(return_value=_fake_response())
        mocker.patch("src.generators.image.genai.Client", return_value=client_mock)

        gen = GeminiImageGenerator(output_dir=tmp_path)
        await gen.generate("test", filename="t.png", aspect_ratio="1:1")

        call_kwargs = client_mock.aio.models.generate_content.await_args.kwargs
        assert call_kwargs["model"] == "gemini-2.5-flash-image"
        assert call_kwargs["config"].image_config.aspect_ratio == "1:1"
        assert call_kwargs["config"].response_modalities == ["IMAGE"]

    @pytest.mark.asyncio
    async def test_raises_on_empty_prompt(
        self, api_key: None, tmp_path: Path, mocker: Any
    ) -> None:
        mocker.patch("src.generators.image.genai.Client")
        gen = GeminiImageGenerator(output_dir=tmp_path)
        with pytest.raises(ImageGenerationError, match="prompt"):
            await gen.generate("   ")

    @pytest.mark.asyncio
    async def test_raises_when_no_image_in_response(
        self, api_key: None, tmp_path: Path, mocker: Any
    ) -> None:
        client_mock = MagicMock()
        client_mock.aio.models.generate_content = AsyncMock(
            return_value=_fake_response(with_image=False)
        )
        mocker.patch("src.generators.image.genai.Client", return_value=client_mock)

        gen = GeminiImageGenerator(output_dir=tmp_path)
        with pytest.raises(ImageGenerationError, match="画像が含まれていません"):
            await gen.generate("test", filename="x.png")

    @pytest.mark.asyncio
    async def test_wraps_api_exceptions(
        self, api_key: None, tmp_path: Path, mocker: Any
    ) -> None:
        client_mock = MagicMock()
        client_mock.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("network down")
        )
        mocker.patch("src.generators.image.genai.Client", return_value=client_mock)

        gen = GeminiImageGenerator(output_dir=tmp_path)
        with pytest.raises(ImageGenerationError, match="Gemini API呼び出し失敗"):
            await gen.generate("test", filename="x.png")

    @pytest.mark.asyncio
    async def test_creates_output_directory(
        self, api_key: None, tmp_path: Path, mocker: Any
    ) -> None:
        client_mock = MagicMock()
        client_mock.aio.models.generate_content = AsyncMock(return_value=_fake_response())
        mocker.patch("src.generators.image.genai.Client", return_value=client_mock)

        output_dir = tmp_path / "nested" / "images"
        gen = GeminiImageGenerator(output_dir=output_dir)
        path = await gen.generate("test", filename="t.png")

        assert path.exists()
        assert path.parent == output_dir
