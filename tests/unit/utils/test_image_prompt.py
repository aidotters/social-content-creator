"""build_featured_image_prompt のテスト。"""

import pytest

from src.models.blog_post import ContentType
from src.utils.image_prompt import (
    _ANTI_STYLE_DIRECTIVE,
    _BRAND_STYLE_DIRECTIVE,
    _CONTENT_TYPE_STYLES,
    _CONTENT_TYPE_SUBJECTS,
    build_featured_image_prompt,
)


@pytest.mark.parametrize("content_type", list(_CONTENT_TYPE_STYLES.keys()))
def test_style_string_for_each_content_type(content_type: ContentType) -> None:
    """8種類すべての content_type で対応するスタイル指示文字列がプロンプトに含まれる。"""
    prompt = build_featured_image_prompt(
        content_type=content_type,
        title="サンプルタイトル",
    )
    assert _CONTENT_TYPE_STYLES[content_type] in prompt


def test_japanese_title_not_rendered_in_prompt() -> None:
    """日本語タイトルはプロンプトに含めない（画像への文字描画を防ぐため）。"""
    prompt = build_featured_image_prompt(
        content_type="weekly-ai-news",
        title="今週のAIニュース総まとめ",
    )
    assert "今週のAIニュース総まとめ" not in prompt


def test_japanese_body_excerpt_not_rendered_in_prompt() -> None:
    """日本語の本文冒頭はプロンプトに含めない（画像への文字描画を防ぐため）。"""
    excerpt = "この記事ではAIの最新動向を紹介します。"
    prompt = build_featured_image_prompt(
        content_type="weekly-ai-news",
        title="タイトル",
        body_excerpt=excerpt,
    )
    assert excerpt not in prompt


def test_no_body_excerpt_omits_context_section() -> None:
    """本文冒頭が空の場合は context セクションがプロンプトに含まれない。"""
    prompt = build_featured_image_prompt(
        content_type="cv",
        title="タイトル",
    )
    assert "Article context:" not in prompt


def test_prompt_includes_no_text_constraint() -> None:
    """生成画像にテキストを入れないよう強い制約が含まれる。"""
    prompt = build_featured_image_prompt(
        content_type="feature",
        title="特集記事",
    )
    assert "Absolutely no text" in prompt
    assert "no Japanese characters" in prompt


@pytest.mark.parametrize("content_type", list(_CONTENT_TYPE_STYLES.keys()))
def test_brand_directives_in_every_prompt(content_type: ContentType) -> None:
    """全 content_type で aidotters.com のブランド指示と禁止指示が含まれる。

    配色はタイプごとに振らずブランド共通で固定する、という方針を守るためのテスト。
    """
    prompt = build_featured_image_prompt(
        content_type=content_type,
        title="サンプルタイトル",
    )
    assert _BRAND_STYLE_DIRECTIVE in prompt
    assert _ANTI_STYLE_DIRECTIVE in prompt


def test_brand_palette_is_described_by_name() -> None:
    """パレットが色名の言語記述で指定されている。"""
    prompt = build_featured_image_prompt(
        content_type="weekly-ai-news",
        title="タイトル",
    )
    for color in (
        "white background",
        "deep navy",
        "brand navy blue",
        "medium blue",
        "light blue",
        "teal",
        "mint",
        "warm yellow",
        "sand",
    ):
        assert color in prompt


@pytest.mark.parametrize("content_type", list(_CONTENT_TYPE_STYLES.keys()))
def test_prompt_contains_no_hex_color_code(content_type: ContentType) -> None:
    """プロンプトに hex のカラーコードを含めない。

    画像モデルは hex を色として解釈せず、端末の画面などに "6FA32D6" のような
    崩れた文字列として描画してしまう（weekly-ai-news で複数枚の実測あり）。
    """
    prompt = build_featured_image_prompt(
        content_type=content_type,
        title="タイトル",
    )
    assert "#" not in prompt


def test_dark_scifi_style_is_forbidden() -> None:
    """旧スタイル（暗色地・ネオン・3D）を明示的に禁止している。"""
    prompt = build_featured_image_prompt(
        content_type="ml-practice",
        title="タイトル",
    )
    assert "dark or black backgrounds" in prompt
    assert "neon glow" in prompt
    assert "3D renders" in prompt


@pytest.mark.parametrize("content_type", list(_CONTENT_TYPE_STYLES.keys()))
def test_subject_string_for_each_content_type(content_type: ContentType) -> None:
    """8種類すべての content_type で対応する被写体の記述がプロンプトに含まれる。"""
    prompt = build_featured_image_prompt(
        content_type=content_type,
        title="サンプルタイトル",
    )
    assert _CONTENT_TYPE_SUBJECTS[content_type] in prompt


@pytest.mark.parametrize("content_type", list(_CONTENT_TYPE_STYLES.keys()))
def test_frame_structures_in_every_prompt(content_type: ContentType) -> None:
    """全 content_type で、上下の水平構造の指示がプロンプトに含まれる。

    白地にオブジェクトを浮かせただけだと上下の境目が無く絵が宙に浮くため、
    タイプごとの構造（レール・書棚・コンベア等）を必ず入れる。
    """
    from src.utils.image_prompt import _CONTENT_TYPE_FRAMES

    prompt = build_featured_image_prompt(content_type=content_type, title="タイトル")
    top, bottom = _CONTENT_TYPE_FRAMES[content_type]
    assert top in prompt
    assert bottom in prompt
    assert "Framing:" in prompt


def test_every_content_type_has_a_frame() -> None:
    """フレーム定義が全 content_type ぶん揃っている。"""
    from src.utils.image_prompt import _CONTENT_TYPE_FRAMES

    assert set(_CONTENT_TYPE_FRAMES) == set(_CONTENT_TYPE_STYLES)


def test_prompt_asks_for_dense_composition() -> None:
    """絵が薄くならないよう、大きさと重なりの指示が入っている。"""
    prompt = build_featured_image_prompt(content_type="weekly-ai-news", title="タイトル")
    assert "overlap each other slightly" in prompt
