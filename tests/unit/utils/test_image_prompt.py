"""build_featured_image_prompt のテスト。"""

import pytest

from src.models.blog_post import ContentType
from src.utils.image_prompt import _CONTENT_TYPE_STYLES, build_featured_image_prompt


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
