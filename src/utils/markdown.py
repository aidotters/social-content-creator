"""Markdown処理ユーティリティ。"""

import re
import unicodedata
from pathlib import Path

import frontmatter
import markdown as md  # type: ignore[import-untyped]

_BLOCK_TAGS = r"h[1-6]|p|pre|ul|ol|table|blockquote|div|figure"


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


def html_to_gutenberg_blocks(html: str) -> str:
    """HTMLをWordPress Gutenbergブロック形式に変換する。

    素のHTMLをGutenbergのブロックコメントで囲み、
    WordPressエディタで個別ブロックとして編集可能にする。

    Args:
        html: 変換対象のHTML文字列

    Returns:
        Gutenbergブロック形式のHTML文字列
    """
    blocks: list[str] = []
    remaining = html.strip()

    while remaining:
        remaining = remaining.lstrip()
        if not remaining:
            break

        # <hr> / <hr/>
        m = re.match(r"<hr\s*/?>", remaining)
        if m:
            blocks.append(
                "<!-- wp:separator -->\n"
                '<hr class="wp-block-separator has-alpha-channel-opacity"/>\n'
                "<!-- /wp:separator -->"
            )
            remaining = remaining[m.end() :]
            continue

        # Block-level opening tag
        m = re.match(rf"<({_BLOCK_TAGS})(\s[^>]*)?>", remaining)
        if m:
            tag = m.group(1)
            attrs = m.group(2) or ""
            close_pos = _find_close_tag(remaining, tag, m.end())
            element = remaining[:close_pos]
            remaining = remaining[close_pos:]
            blocks.append(_to_gutenberg_block(tag, element, attrs))
            continue

        # Unrecognized content — collect until next block element or end
        next_match = re.search(
            rf"<(?:{_BLOCK_TAGS}|hr)[\s>/]", remaining[1:]
        )
        if next_match:
            end = 1 + next_match.start()
            fragment = remaining[:end].strip()
            remaining = remaining[end:]
        else:
            fragment = remaining.strip()
            remaining = ""

        if fragment:
            blocks.append(f"<!-- wp:html -->\n{fragment}\n<!-- /wp:html -->")

    return "\n\n".join(blocks)


def _find_close_tag(html: str, tag: str, start: int) -> int:
    """ネストを考慮して対応する閉じタグの終了位置を返す。"""
    depth = 1
    pos = start
    open_re = re.compile(rf"<{tag}[\s>]")
    close_re = re.compile(rf"</{tag}>")

    while depth > 0 and pos < len(html):
        next_open = open_re.search(html, pos)
        next_close = close_re.search(html, pos)

        if next_close is None:
            return len(html)

        if next_open and next_open.start() < next_close.start():
            depth += 1
            pos = next_open.end()
        else:
            depth -= 1
            pos = next_close.end()

    return pos


def _to_gutenberg_block(tag: str, element: str, attrs: str) -> str:
    """単一のHTML要素をGutenbergブロックに変換する。"""
    if re.match(r"h[1-6]$", tag):
        level = int(tag[1])
        if level == 2:
            header = "<!-- wp:heading -->"
        else:
            header = f'<!-- wp:heading {{"level":{level}}} -->'
        return f"{header}\n{element}\n<!-- /wp:heading -->"

    if tag == "p":
        return f"<!-- wp:paragraph -->\n{element}\n<!-- /wp:paragraph -->"

    if tag == "pre":
        return f"<!-- wp:code -->\n{element}\n<!-- /wp:code -->"

    if tag == "ul":
        return f"<!-- wp:list -->\n{element}\n<!-- /wp:list -->"

    if tag == "ol":
        return f'<!-- wp:list {{"ordered":true}} -->\n{element}\n<!-- /wp:list -->'

    if tag == "table":
        return (
            "<!-- wp:table -->\n"
            f"<figure class=\"wp-block-table\">{element}</figure>\n"
            "<!-- /wp:table -->"
        )

    if tag == "blockquote":
        return f"<!-- wp:quote -->\n{element}\n<!-- /wp:quote -->"

    return f"<!-- wp:html -->\n{element}\n<!-- /wp:html -->"


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
