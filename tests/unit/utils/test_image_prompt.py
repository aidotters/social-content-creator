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


def test_title_included_in_prompt() -> None:
    """タイトルがプロンプトに含まれる。"""
    prompt = build_featured_image_prompt(
        content_type="weekly-ai-news",
        title="今週のAIニュース総まとめ",
    )
    assert "今週のAIニュース総まとめ" in prompt


def test_body_excerpt_included_when_provided() -> None:
    """本文冒頭が指定された場合にプロンプトへ含まれる。"""
    excerpt = "この記事ではAIの最新動向を紹介します。"
    prompt = build_featured_image_prompt(
        content_type="weekly-ai-news",
        title="タイトル",
        body_excerpt=excerpt,
    )
    assert excerpt in prompt


def test_body_excerpt_truncated_at_300_chars() -> None:
    """本文冒頭が300文字を超える場合に切り詰められる。"""
    long_excerpt = "あ" * 500
    prompt = build_featured_image_prompt(
        content_type="paper-review",
        title="タイトル",
        body_excerpt=long_excerpt,
    )
    assert "あ" * 300 in prompt
    # 切り詰めにより301文字目以降は含まれない（"あ" * 301 が含まれていないこと）
    assert "あ" * 301 not in prompt


def test_no_body_excerpt_omits_context_section() -> None:
    """本文冒頭が空の場合は context セクションがプロンプトに含まれない。"""
    prompt = build_featured_image_prompt(
        content_type="cv",
        title="タイトル",
    )
    assert "Article context:" not in prompt


def test_prompt_includes_no_text_constraint() -> None:
    """生成画像にテキストを入れないよう制約が含まれる。"""
    prompt = build_featured_image_prompt(
        content_type="feature",
        title="特集記事",
    )
    assert "No text" in prompt
