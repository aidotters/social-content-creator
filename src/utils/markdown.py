"""Markdown処理ユーティリティ。"""

import re
import unicodedata
from pathlib import Path

import frontmatter
import markdown as md  # type: ignore[import-untyped]


def write_frontmatter_markdown(path: Path, metadata: dict[str, object], content: str) -> None:
    """front matter付きMarkdownファイルを書き出す。

    Args:
        path: 出力先パス
        metadata: front matterに含めるメタデータ
        content: Markdown本文
    """
    post = frontmatter.Post(content, **metadata)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter.dumps(post), encoding="utf-8")


def read_frontmatter_markdown(path: Path) -> tuple[dict[str, object], str]:
    """front matter付きMarkdownファイルを読み込む。

    Args:
        path: 読み込むファイルパス

    Returns:
        (メタデータ辞書, Markdown本文) のタプル
    """
    post = frontmatter.load(str(path))
    return dict(post.metadata), post.content


def generate_slug(title: str) -> str:
    """タイトルからURLスラッグを生成する。

    日本語はローマ字化せず除去し、英数字とハイフンのみ残す。

    Args:
        title: 記事タイトル

    Returns:
        URL用スラッグ文字列
    """
    # NFKCで正規化
    normalized = unicodedata.normalize("NFKC", title)
    # 小文字化
    lower = normalized.lower()
    # 英数字・スペース・ハイフン以外を除去
    cleaned = re.sub(r"[^a-z0-9\s\-]", "", lower)
    # 空白をハイフンに
    slugified = re.sub(r"[\s]+", "-", cleaned.strip())
    # 連続ハイフンを1つに
    slugified = re.sub(r"-+", "-", slugified)
    # 先頭末尾のハイフンを除去
    slugified = slugified.strip("-")
    return slugified or "untitled"


def markdown_to_html(text: str) -> str:
    """MarkdownテキストをHTMLに変換する。

    Args:
        text: Markdown形式のテキスト

    Returns:
        HTML文字列
    """
    return md.markdown(text, extensions=["extra", "nl2br", "sane_lists"])  # type: ignore[no-any-return]


def count_characters(text: str) -> int:
    """Markdownテキストの文字数をカウントする。

    Markdownの記法（見出し記号、リンク記法等）を除去してカウントする。

    Args:
        text: カウント対象のテキスト

    Returns:
        文字数
    """
    # Markdownの見出し記号を除去
    cleaned = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # 画像記法を除去（リンク記法より先に処理する）
    cleaned = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", cleaned)
    # リンク記法を除去（テキスト部分のみ残す）
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    # 強調記法を除去
    cleaned = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", cleaned)
    # コードブロックを除去
    cleaned = re.sub(r"```[\s\S]*?```", "", cleaned)
    # インラインコードを除去
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    # 空白行を除去してカウント
    cleaned = cleaned.strip()
    return len(cleaned)
