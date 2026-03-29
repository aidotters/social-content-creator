"""Markdownユーティリティのテスト。"""

from src.utils.markdown import count_characters, html_to_gutenberg_blocks


class TestCountCharacters:
    """count_characters()のテスト。"""

    def test_plain_text(self) -> None:
        """プレーンテキストの文字数を正しくカウントする。"""
        assert count_characters("Hello World") == 11

    def test_heading_removal(self) -> None:
        """見出し記号を除去してカウントする。"""
        text = "# 見出し1\n## 見出し2\n本文"
        result = count_characters(text)
        # "見出し1\n見出し2\n本文" = 見出し1(4) + \n(1) + 見出し2(4) + \n(1) + 本文(2) = 12
        assert result == 12

    def test_link_removal(self) -> None:
        """リンク記法を除去してテキスト部分のみカウントする。"""
        text = "[リンクテキスト](https://example.com)"
        result = count_characters(text)
        assert result == len("リンクテキスト")

    def test_image_removal(self) -> None:
        """画像記法を除去してaltテキスト部分のみカウントする。"""
        text = "![代替テキスト](https://example.com/image.png)"
        result = count_characters(text)
        assert result == len("代替テキスト")

    def test_bold_removal(self) -> None:
        """強調記法を除去してカウントする。"""
        text = "**太字テキスト**と*斜体テキスト*"
        result = count_characters(text)
        assert result == len("太字テキストと斜体テキスト")

    def test_code_block_removal(self) -> None:
        """コードブロックを除去してカウントする。"""
        text = "本文\n```python\nprint('hello')\n```\n残り"
        result = count_characters(text)
        assert result == len("本文\n\n残り")

    def test_inline_code_removal(self) -> None:
        """インラインコードの記法を除去してカウントする。"""
        text = "変数`foo`の値"
        result = count_characters(text)
        assert result == len("変数fooの値")

    def test_empty_string(self) -> None:
        """空文字列は0を返す。"""
        assert count_characters("") == 0

    def test_whitespace_only(self) -> None:
        """空白のみのテキストは0を返す。"""
        assert count_characters("   \n\n  ") == 0

    def test_complex_markdown(self) -> None:
        """複合的なMarkdown記法が正しく処理される。"""
        text = (
            "# タイトル\n\n"
            "これは**太字**と[リンク](https://example.com)を含む段落です。\n\n"
            "```\ncode\n```\n\n"
            "`inline`も含む。"
        )
        result = count_characters(text)
        plain = "タイトル\n\nこれは太字とリンクを含む段落です。\n\n\n\ninlineも含む。"
        expected = count_characters(plain)
        assert result == expected


class TestHtmlToGutenbergBlocks:
    """html_to_gutenberg_blocks()のテスト。"""

    def test_paragraph(self) -> None:
        """<p>がwp:paragraphブロックに変換される。"""
        result = html_to_gutenberg_blocks("<p>Hello</p>")
        assert "<!-- wp:paragraph -->" in result
        assert "<p>Hello</p>" in result
        assert "<!-- /wp:paragraph -->" in result

    def test_heading_h2(self) -> None:
        """<h2>がwp:headingブロックに変換される（level省略）。"""
        result = html_to_gutenberg_blocks("<h2>Title</h2>")
        assert "<!-- wp:heading -->" in result
        assert "<h2>Title</h2>" in result
        assert "<!-- /wp:heading -->" in result

    def test_heading_h3(self) -> None:
        """<h3>がwp:heading level:3ブロックに変換される。"""
        result = html_to_gutenberg_blocks("<h3>Subtitle</h3>")
        assert '{"level":3}' in result
        assert "<h3>Subtitle</h3>" in result

    def test_heading_with_id(self) -> None:
        """id属性付き<h2>が正しく変換される。"""
        result = html_to_gutenberg_blocks('<h2 id="section-1">Intro</h2>')
        assert "<!-- wp:heading -->" in result
        assert 'id="section-1"' in result

    def test_code_block(self) -> None:
        """<pre>がwp:codeブロックに変換される。"""
        result = html_to_gutenberg_blocks("<pre><code>print(1)</code></pre>")
        assert "<!-- wp:code -->" in result
        assert "<pre><code>print(1)</code></pre>" in result

    def test_unordered_list(self) -> None:
        """<ul>がwp:listブロックに変換される。"""
        result = html_to_gutenberg_blocks("<ul><li>A</li><li>B</li></ul>")
        assert "<!-- wp:list -->" in result
        assert "<!-- /wp:list -->" in result

    def test_ordered_list(self) -> None:
        """<ol>がwp:list orderedブロックに変換される。"""
        result = html_to_gutenberg_blocks("<ol><li>1</li><li>2</li></ol>")
        assert '{"ordered":true}' in result

    def test_table(self) -> None:
        """<table>がwp:tableブロックに変換される。"""
        html = "<table><tr><td>A</td></tr></table>"
        result = html_to_gutenberg_blocks(html)
        assert "<!-- wp:table -->" in result
        assert 'class="wp-block-table"' in result

    def test_blockquote(self) -> None:
        """<blockquote>がwp:quoteブロックに変換される。"""
        result = html_to_gutenberg_blocks("<blockquote><p>Quote</p></blockquote>")
        assert "<!-- wp:quote -->" in result

    def test_hr(self) -> None:
        """<hr>がwp:separatorブロックに変換される。"""
        result = html_to_gutenberg_blocks("<hr/>")
        assert "<!-- wp:separator -->" in result

    def test_multiple_blocks(self) -> None:
        """複数要素がそれぞれ独立したブロックに変換される。"""
        html = "<h2>Title</h2>\n<p>Text</p>\n<ul><li>A</li></ul>"
        result = html_to_gutenberg_blocks(html)
        assert "<!-- wp:heading -->" in result
        assert "<!-- wp:paragraph -->" in result
        assert "<!-- wp:list -->" in result
        # 3ブロック分の開始・終了コメント
        assert result.count("<!-- /wp:") == 3

    def test_nested_tags(self) -> None:
        """ネストしたタグが正しく処理される。"""
        html = "<div><div>inner</div></div>"
        result = html_to_gutenberg_blocks(html)
        assert "<div><div>inner</div></div>" in result

    def test_raw_html_fallback(self) -> None:
        """認識外のHTMLがwp:htmlブロックになる。"""
        result = html_to_gutenberg_blocks("<span>inline</span>")
        assert "<!-- wp:html -->" in result
        assert "<span>inline</span>" in result
