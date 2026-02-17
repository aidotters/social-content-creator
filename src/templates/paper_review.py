"""論文解説 テンプレート。"""

from src.models.template import ContentTemplate, TemplateSection


def create_template() -> ContentTemplate:
    """論文解説のテンプレートを作成する。"""
    return ContentTemplate(
        content_type="paper-review",
        name="論文解説",
        description="AI/ML分野の注目論文を分かりやすく解説する記事",
        min_words=5000,
        max_words=8000,
        sections=[
            TemplateSection(
                title="論文の概要",
                description=(
                    "導入段落の後に、以下のテーブルで論文情報を表示する:\n"
                    "\n"
                    "| 項目 | 内容 |\n"
                    "|------|------|\n"
                    "| **タイトル** | 原題（英語） |\n"
                    "| **著者** | 著者名（カンマ区切り） |\n"
                    "| **公開日** | YYYY年M月D日 |\n"
                    "| **arXiv** | [arXiv:XXXX.XXXXX](https://arxiv.org/abs/XXXX.XXXXX) |\n"
                    "| **キーワード** | キーワード（カンマ区切り） |\n"
                    "\n"
                    "テーブルの後に、論文の主要な貢献を2〜3段落で要約する。"
                ),
            ),
            TemplateSection(
                title="背景と課題",
                description=(
                    "この研究の背景と解決しようとしている課題を解説する。\n"
                    "h3見出しで「### 〇〇の現状」「### 既存アプローチの課題」のように\n"
                    "サブセクションに分けて構造化する。"
                ),
            ),
            TemplateSection(
                title="提案手法",
                description=(
                    "論文で提案されている手法の詳細な解説。\n"
                    "h3/h4見出しでアーキテクチャや主要コンポーネントを分けて説明する。\n"
                    "数式・図表・コード例がある場合は適宜引用する。"
                ),
            ),
            TemplateSection(
                title="実験結果",
                description=(
                    "主要な実験結果をテーブルで提示し、ベースラインとの比較を行う。\n"
                    "アブレーション研究がある場合はサブセクションで解説する。"
                ),
            ),
            TemplateSection(
                title="考察・インパクト",
                description=(
                    "実務への応用可能性や業界へのインパクトを考察する。\n"
                    "h3見出しで「影響」「限界と課題」等に分けて構造化する。"
                ),
            ),
            TemplateSection(
                title="まとめ",
                description=(
                    "以下の構成で記述する:\n"
                    "1. 論文の意義を1文で述べる\n"
                    "2. 「**論文の要点：**」として主要ポイントを箇条書き（4〜6項目）\n"
                    "3. 締めの段落（1〜2文）\n"
                    "4. 区切り線(---)の後に「**論文リンク**: [arXiv:XXXX.XXXXX](URL)」"
                ),
            ),
        ],
        style_guide="です・ます調。技術的に正確でありつつ、専門外の読者にも理解できるよう"
        "噛み砕いた表現を心がける。図表の説明を丁寧に行う。"
        "タイトルは「【論文解説】{手法名}「{論文タイトル}」〜{キャッチコピー}〜」の形式とする。"
        "見出し（h2/h3/h4）には「1. 」のような番号を付けないこと。"
        "WordPressテーマ（Cocoon）が目次を自動生成する際に二重番号になるため。"
        "論文情報は必ずテーブル形式で記載すること。"
        "まとめセクションの末尾に必ず論文リンクを記載すること。",
    )
