> **ステータス: 実装済み**
> 最終更新: 2026-04-28

# 機能設計書 (Functional Design Document)

## システム構成図

```mermaid
graph TB
    User[ユーザー]
    Skill["Claude Code スキル層<br/>/create-blog-post"]
    ImageSkill["画像生成スキル<br/>/generate-image"]
    Generator["記事生成エンジン<br/>generators/"]
    ImageGen["画像生成エンジン<br/>GeminiImageGenerator"]
    Template["テンプレート<br/>templates/"]
    Collector["情報収集ツール群<br/>collectors/"]
    Publisher["投稿先連携<br/>publishers/"]
    Storage["ローカル保存<br/>docs/drafts/ → docs/posts/"]
    ImageStorage["画像保存<br/>outputs/images/<br/>→ outputs/images/archive/"]
    XSkill["X投稿スキル<br/>/publish-to-x"]
    WPSkill["WordPress投稿スキル<br/>/publish-to-wordpress"]

    WebSearch[Web検索]
    URLFetcher[URL取得・解析]
    GeminiCLI[Gemini CLI]
    NotionAPI["Notion API<br/>(News / Paper / Medium DB)"]
    GitHubAPI[GitHub API]
    GeminiAPI["Gemini API<br/>(gemini-2.5-flash-image)"]

    WordPress["WordPress REST API<br/>upload_media + posts"]
    XAPI[X API v2]

    User --> Skill
    User --> XSkill
    User --> ImageSkill
    User --> WPSkill
    Skill --> Generator
    Generator --> Template
    Generator --> Collector
    Generator --> Storage

    ImageSkill --> ImageGen
    WPSkill --> ImageGen
    WPSkill --> Publisher
    ImageGen --> GeminiAPI
    ImageGen --> ImageStorage

    Collector --> WebSearch
    Collector --> URLFetcher
    Collector --> GeminiCLI
    Collector --> NotionAPI
    Collector --> GitHubAPI

    Publisher --> WordPress
    XSkill --> Publisher
    Publisher --> XAPI
```

## 技術スタック

| 分類 | 技術 | 選定理由 |
|------|------|----------|
| 言語 | Python 3.12+ | AI/MLエコシステムとの親和性 |
| パッケージ管理 | uv | 高速な依存関係解決 |
| HTTP通信 | httpx | async対応、モダンなHTTPクライアント |
| スキル層 | Claude Code Skills | 対話的な操作、柔軟な拡張性 |
| テスト | pytest | Python標準テストフレームワーク |
| Lint/Format | Ruff / Black | 高速なLint・フォーマット |
| 型チェック | mypy | 静的型チェック |

## データモデル定義

### エンティティ: BlogPost

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

type ContentType = Literal[
    "weekly-ai-news",
    "paper-review",
    "project-intro",
    "tool-tips",
    "market-analysis",
    "ml-practice",
    "cv",
    "feature",
]

type PostStatus = Literal["draft", "review", "ready", "published"]

class BlogPost(BaseModel):
    """ブログ記事のデータモデル"""
    title: str                              # 記事タイトル
    subtitle: str | None = None             # サブタイトル（補足情報）
    content: str                            # 記事本文（Markdown）
    content_type: ContentType               # コンテンツタイプ
    status: PostStatus = "draft"            # 記事ステータス
    slug: str                               # URLスラッグ
    categories: list[str] = []              # カテゴリ
    tags: list[str] = []                    # タグ
    created_at: datetime                    # 作成日時
    published_at: datetime | None = None    # 投稿日時
    wordpress_id: int | None = None         # WordPress投稿ID
    wordpress_url: str | None = None        # WordPress投稿URL
```

### エンティティ: ContentTemplate

```python
class TemplateSection(BaseModel):
    """テンプレートのセクション定義"""
    title: str                              # セクションタイトル
    description: str                        # セクション説明
    required: bool = True                   # 必須セクションかどうか

class ContentTemplate(BaseModel):
    """コンテンツタイプ別テンプレート"""
    content_type: ContentType               # コンテンツタイプ
    name: str                               # テンプレート名
    description: str                        # テンプレートの説明
    min_words: int                          # 最小文字数
    max_words: int                          # 最大文字数
    sections: list[TemplateSection]         # セクション構成
    style_guide: str                        # 文体ガイド
```

**テンプレートレジストリ** (`src/templates/__init__.py`):
```python
def get_template(content_type: ContentType) -> ContentTemplate:
    """指定タイプのテンプレートを取得する（未登録時 TemplateNotFoundError）"""
    ...

def list_templates() -> list[ContentTemplate]:
    """全テンプレートのリストを返す"""
    ...
```

### エンティティ: CollectedData

```python
class CollectedData(BaseModel):
    """情報収集結果"""
    source: str                             # 情報源（web_search, url, gemini, notion_news, notion_paper, notion_medium, github）
    title: str                              # タイトル
    url: str | None = None                  # URL
    content: str                            # 内容
    collected_at: datetime                  # 収集日時
    published_date: str | None = None       # ニュース発生日（YYYY-MM-DD形式、Notionコレクター用）
```

### エンティティ: PublishResult

```python
class PublishResult(BaseModel):
    """投稿結果"""
    success: bool                           # 成功/失敗
    post_id: int | None = None              # WordPress投稿ID
    url: str | None = None                  # 投稿URL
    error_message: str | None = None        # エラーメッセージ
```

### エンティティ: XPublishResult

```python
class XPublishResult(BaseModel):
    """X投稿結果のデータモデル"""
    success: bool                           # 成功/失敗
    tweet_id: str | None = None             # ツイートID
    tweet_url: str | None = None            # ツイートURL
    thread_ids: list[str] = []              # スレッド投稿時の全ツイートID
    error_message: str | None = None        # エラーメッセージ
```

## コンポーネント設計

### BlogPostGenerator（記事生成エンジン）

**責務**:
- コンテンツタイプに応じたテンプレートの選択
- 情報収集結果の統合
- 記事ドラフトの生成
- 文体ガイドの適用

**インターフェース**:
```python
class BlogPostGenerator:
    """ブログ記事の生成・保存・管理を行うジェネレーター"""

    def get_template(self, content_type: ContentType) -> ContentTemplate:
        """指定タイプのテンプレートを取得する"""
        ...

    def build_prompt_context(
        self,
        template: ContentTemplate,
        topic: str | None = None,
        source_url: str | None = None,
        collected_data: list[CollectedData] | None = None,
    ) -> str:
        """記事生成用のプロンプトコンテキストを構築する。
        スキル層（Claude LLM）が記事本文を生成するための情報を整理する。"""
        ...

    async def generate(
        self,
        content_type: ContentType,
        title: str,
        content: str,
        topic: str | None = None,
        source_url: str | None = None,
        collected_data: list[CollectedData] | None = None,
    ) -> BlogPost:
        """ブログ記事オブジェクトを生成する。
        記事本文はスキル層（Claude LLM）が生成し、このメソッドに渡される。"""
        ...

    async def save_draft(self, post: BlogPost) -> Path:
        """記事をドラフトとして保存する"""
        ...

    async def load_draft(self, path: Path) -> BlogPost:
        """ドラフトファイルから記事を読み込む"""
        ...

    async def move_to_published(self, post: BlogPost, draft_path: Path) -> Path:
        """ドラフトを投稿済みディレクトリに移動する"""
        ...
```

**備考**: 実際の設計では、記事本文の生成はスキル層（Claude LLM）が行い、`generate()` は構造化のみ担当する。`build_prompt_context()` でテンプレートと収集データからプロンプト情報を構築し、スキル層がそれを元に記事本文を生成する。

**依存関係**:
- ContentTemplate（テンプレート）
- Collector群（情報収集）

### GeminiImageGenerator（画像生成エンジン）

**責務**:
- Gemini API（`gemini-2.5-flash-image` / Nanobanana）を用いた画像生成
- 生成画像のローカル保存（`outputs/images/` 配下）
- アスペクト比指定（`1:1`, `3:4`, `4:3`, `9:16`, `16:9`）
- ファイル名のスラッグ自動生成

**インターフェース**:
```python
AspectRatio = Literal["1:1", "3:4", "4:3", "9:16", "16:9"]

class GeminiImageGenerator:
    """Gemini APIで画像生成するGenerator"""

    def __init__(
        self,
        *,
        output_dir: Path | None = None,
        api_key: str | None = None,
    ) -> None:
        """`GEMINI_API_KEY` 未設定時は `ImageGenerationError` を送出する"""
        ...

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
            aspect_ratio: アスペクト比（既定: 16:9）
            filename: 保存ファイル名（拡張子込み）。指定時は `slug` を無視
            slug: ファイル名の接頭辞。未指定時はプロンプトから自動生成

        Returns:
            保存した画像ファイルのパス

        Raises:
            ImageGenerationError: 空プロンプト・API呼び出し失敗・画像未取得・セーフティ拒否時
        """
        ...
```

**依存関係**:
- `google-genai`（Gemini API クライアント）
- `Pillow`（画像保存。`google-genai` の transitive 依存）
- 環境変数 `GEMINI_API_KEY`
- `src.errors.ImageGenerationError`

### PublisherProtocol（投稿共通プロトコル）

**インターフェース**:
```python
class PublisherProtocol(Protocol):
    """投稿先連携の共通プロトコル"""

    async def publish(self, post: BlogPost, **kwargs: object) -> PublishResult:
        """記事を投稿する"""
        ...
```

WordPressPublisher・XPublisher はこのプロトコルを実装する。

### WordPressPublisher（WordPress投稿）

**責務**:
- WordPress REST APIとの通信
- 認証処理（Application Passwords）
- 記事の投稿（下書き/公開）
- カテゴリ・タグの設定

**インターフェース**:

`PublisherProtocol`（共通プロトコル）の `publish()` を実装し、WordPress固有のメソッドを追加:

```python
class WordPressPublisher:
    """WordPress REST APIで記事を投稿するPublisher"""

    async def publish(
        self,
        post: BlogPost,
        status: Literal["draft", "publish"] = "draft",
        categories: list[str] | None = None,
        tags: list[str] | None = None,
        featured_image_path: Path | None = None,
        featured_image_alt: str | None = None,
        force_featured_image: bool = False,
        **kwargs: object,
    ) -> PublishResult:
        """記事をWordPressに投稿する。

        featured_image_path 指定時は事前に upload_media() でアップロードし、
        投稿payloadの featured_media にセットする。featured_image_alt が
        未指定の場合は post.title を使用。force_featured_image は publish()
        では未使用で、スキル層が set_featured_media() を直接呼ぶ際の互換引数。
        """
        ...

    async def upload_media(
        self,
        image_path: Path,
        alt_text: str,
        title: str | None = None,
    ) -> int:
        """画像をWordPressメディアライブラリにアップロードし media_id を返す。

        multipart で alt_text が反映されないケースに備え、別エンドポイントで
        alt_text/title を再更新する。成功時はローカルファイルを
        outputs/images/archive/ へ移動する。
        """
        ...

    async def set_featured_media(
        self,
        post_id: int,
        media_id: int,
        force: bool = False,
    ) -> None:
        """既存投稿に featured_media を設定する。

        既存アイキャッチが 0 以外の場合、force=False ならエラーを投げる。
        後付けでアイキャッチを設定する用途（スキル層の --post-id 経路）で使用。
        """
        ...

    async def get_post(self, post_id: int) -> dict[str, object]:
        """既存記事の情報をWordPress REST APIから取得する"""
        ...

    async def get_categories(self) -> list[dict[str, object]]:
        """WordPress上のカテゴリ一覧を取得する"""
        ...

    async def get_tags(self) -> list[dict[str, object]]:
        """WordPress上のタグ一覧を取得する"""
        ...
```

**投稿フロー上の補足**:
- `post.subtitle` が指定されている場合、`publish()` は投稿後に取得した `post_id` / `post_url` を用いて `excerpt` を 2 段階目で再更新する。最終的な `excerpt` は `"{subtitle}… <a class=\"more-link\" href=\"{post_url}\">続きを読む</a>"` 形式となる（一覧表示で「続きを読む」リンクを表示するため）。

**依存関係**:
- httpx（HTTP通信）
- 環境変数（認証情報）

### XPublisher（X投稿）

**責務**:
- X API v2との通信（OAuth 1.0a認証）
- 1ツイート投稿（280文字以内）
- スレッド投稿（複数ツイートの連鎖投稿）
- 文字数バリデーション
- リトライ処理（ネットワークエラー・サーバーエラー時に1回）

**インターフェース**:
```python
class XPublisher:
    """X API v2でツイートを投稿するPublisher"""

    async def publish(
        self,
        post: BlogPost,
        text: str | None = None,
        **kwargs: object,
    ) -> PublishResult:
        """記事の紹介ツイートを1件投稿する"""
        ...

    async def publish_thread(
        self,
        post: BlogPost,
        texts: list[str],
    ) -> XPublishResult:
        """スレッド形式で複数ツイートを投稿する"""
        ...

    def validate_text(self, text: str) -> None:
        """テキストの文字数バリデーション（280文字超過時にValueError）"""
        ...
```

**依存関係**:
- httpx（HTTP通信）
- authlib（OAuth 1.0a認証）
- 環境変数（X API認証情報: `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`）

### Collector群（情報収集ツール）

**責務**:
- 各情報源からのデータ取得
- 取得データの正規化

**インターフェース**:
```python
class CollectorProtocol(Protocol):
    """情報収集ツールの共通インターフェース"""

    async def collect(self, query: str, **kwargs: object) -> list[CollectedData]:
        """情報を収集する"""
        ...
```

**具象クラス**:
- `WebSearchCollector`: Web検索による情報収集
- `URLFetcherCollector`: 指定URLの内容取得・要約
- `GeminiCollector`: Gemini CLI経由の調査レポート生成
- `NotionNewsCollector`: Notion API経由でGoogle Alertニュース記事を取得（`date_from`/`date_to` で日付範囲指定可、デフォルト: 過去7日間）
- `NotionPaperCollector`: Notion API経由でArxiv論文データを取得（テーマ指定/過去1週間）
- `NotionMediumCollector`: Notion API経由でMedium Daily Digest記事を取得（`date_from`/`date_to` で日付範囲指定可、デフォルト: 過去7日間）
- `GitHubCollector`: GitHub API経由のリポジトリ情報取得

**共通基底クラス**: `NotionBaseCollector`（`notion_base.py`）
- Notion Database Query API呼び出し（ページネーション対応）
- プロパティ抽出ヘルパー（title, rich_text, url, date, multi_select, number, checkbox, select）
- `NOTION_TOKEN` による認証

**依存関係**:
- httpx（HTTP通信）
- Notion API（NotionNewsCollector, NotionPaperCollector, NotionMediumCollector）
- 各外部API

## ユースケース図

### ユースケース1: ブログ記事の生成と投稿

```mermaid
sequenceDiagram
    participant User as ユーザー
    participant Skill as Claude Code スキル
    participant Generator as 記事生成エンジン
    participant Collector as 情報収集ツール
    participant Template as テンプレート
    participant Publisher as WordPress投稿
    participant Storage as ローカル保存

    User->>Skill: /create-blog-post --type weekly-ai-news
    Skill->>Generator: get_template("weekly-ai-news")
    Generator-->>Skill: ContentTemplate
    Skill->>Generator: build_prompt_context(template, topic, collected_data)
    Generator-->>Skill: プロンプトコンテキスト
    Note over Skill: スキル層（Claude LLM）が記事本文を生成
    Skill->>Generator: generate(content_type, title, content)
    Generator-->>Skill: BlogPost(draft)
    Skill->>Generator: save_draft(post)
    Generator-->>Skill: 保存パス
    Skill-->>User: ドラフト表示・レビュー依頼
    User->>Skill: 修正指示 or 承認
    User->>Skill: 投稿指示
    Skill->>Publisher: publish(post, status="draft")
    Publisher-->>Skill: PublishResult
    Skill->>Generator: move_to_published(post, draft_path)
    Generator-->>Skill: 投稿済みパス
    Skill-->>User: 投稿結果（URL等）
```

**フロー説明**:
1. ユーザーがClaude Codeスキルで記事生成を指示
2. 記事生成エンジンがテンプレートを取得し、情報収集を実行
3. 収集データとテンプレートを基に記事ドラフトを生成
4. ユーザーがドラフトをレビューし、対話的に修正
5. 承認後、ローカルに保存してからWordPressに投稿
6. 投稿結果をユーザーに報告

### ユースケース2: アイキャッチ画像の自動生成と WordPress 添付

```mermaid
sequenceDiagram
    participant User as ユーザー
    participant Skill as /publish-to-wordpress スキル
    participant Prompt as build_featured_image_prompt
    participant ImageGen as GeminiImageGenerator
    participant GeminiAPI as Gemini API
    participant Publisher as WordPressPublisher
    participant WordPress as WordPress REST API
    participant FS as outputs/images/

    User->>Skill: /publish-to-wordpress {draft.md} --auto-generate-image
    Skill->>Prompt: build_featured_image_prompt(content_type, title, body_excerpt)
    Prompt-->>Skill: 英語プロンプト
    Skill->>ImageGen: generate(prompt, aspect_ratio="16:9", slug)
    ImageGen->>GeminiAPI: generate_content(gemini-2.5-flash-image)
    GeminiAPI-->>ImageGen: image bytes
    ImageGen->>FS: 画像を outputs/images/ に保存
    ImageGen-->>Skill: 画像ファイルパス
    Skill->>Publisher: upload_media(画像)
    Publisher->>WordPress: POST /wp-json/wp/v2/media
    WordPress-->>Publisher: media_id
    Skill->>Publisher: publish(post, featured_media=media_id)
    Publisher->>WordPress: POST /wp-json/wp/v2/posts
    WordPress-->>Publisher: PublishResult
    Skill->>FS: 画像を outputs/images/archive/ へ移動
    Publisher-->>Skill: PublishResult
    Skill-->>User: 投稿結果（URL等）
```

### ユースケース3: 情報収集のみ

```mermaid
sequenceDiagram
    participant User as ユーザー
    participant Skill as Claude Code スキル
    participant Collector as 情報収集ツール
    participant WebSearch as Web検索
    participant URLFetcher as URL取得

    User->>Skill: 記事のネタを調査して
    Skill->>Collector: collect("AI最新ニュース")
    Collector->>WebSearch: search("AI最新ニュース 2026")
    WebSearch-->>Collector: 検索結果
    Collector->>URLFetcher: fetch(urls)
    URLFetcher-->>Collector: 記事内容
    Collector-->>Skill: list[CollectedData]
    Skill-->>User: 調査結果のサマリー
```

## ファイル構造

### 記事保存形式

記事はステータスに応じて `docs/drafts/`（下書き）と `docs/posts/`（投稿済み）に分離して管理する。

#### ドラフト（下書き）

```
docs/drafts/
├── weekly-ai-news/
│   └── 20260213-weekly-ai-news-feb-w2.md
├── paper-review/
│   └── 20260210-arxiv-xxxx.md
└── tool-tips/
    └── 20260211-dify-tips.md
```

- `YYYYMMDD` は**作成日**（ドラフトを生成した日）
- コンテンツタイプ（ジャンル）別にディレクトリを分割

#### 投稿済み

```
docs/posts/
├── 2026/
│   └── 02/
│       ├── 20260213-weekly-ai-news-feb-w2.md
│       └── 20260215-paper-review-xxxx.md
```

- `YYYYMMDD` は**投稿日**（WordPressに投稿した日）であり、ドラフト作成日とは異なる場合がある

#### ドラフトのfront matter例

```markdown
---
title: "2026年2月第2週 AIニュースハイライト"
type: weekly-ai-news
status: draft
slug: weekly-ai-news-feb-w2
categories: [AI, ニュース]
tags: [AI, 週刊まとめ, 2026年2月]
date: 2026-02-13T18:00:00+00:00
---

# 2026年2月第2週 AIニュースハイライト

...記事本文...
```

#### 投稿済みのfront matter例

```markdown
---
title: "2026年2月第2週 AIニュースハイライト"
type: weekly-ai-news
status: published
slug: weekly-ai-news-feb-w2
categories: [AI, ニュース]
tags: [AI, 週刊まとめ, 2026年2月]
date: 2026-02-13T18:00:00+00:00
published_at: 2026-02-15T19:00:00+00:00
---

# 2026年2月第2週 AIニュースハイライト

...記事本文...
```

### テンプレート保存形式

```
src/templates/
├── weekly_ai_news.py
├── paper_review.py
├── project_intro.py
├── tool_tips.py
├── market_analysis.py
├── ml_practice.py
├── cv.py
└── feature.py
```

## ユーティリティ関数

### `src/utils/markdown.py`

| 関数 | 説明 |
|------|------|
| `write_frontmatter_markdown(path, metadata, content)` | front matter付きMarkdownファイルを書き出す |
| `read_frontmatter_markdown(path)` | front matter付きMarkdownファイルを読み込み `(metadata, content)` を返す |
| `generate_slug(title)` | タイトルからURLスラッグを生成する（日本語除去、英数字+ハイフンのみ） |
| `markdown_to_html(text)` | MarkdownテキストをHTMLに変換する（`markdown` ライブラリ使用） |
| `html_to_gutenberg_blocks(html)` | HTMLをWordPress Gutenbergブロック形式に変換（見出し/段落/リスト/コード/表/引用/区切りに対応） |
| `count_characters(text)` | Markdown記法を除去して文字数をカウントする |

### `src/utils/image_prompt.py`

| 関数 | 説明 |
|------|------|
| `build_featured_image_prompt(content_type, title, body_excerpt="")` | コンテンツタイプ別の被写体・構図指示と、サイト共通のブランド配色指示を組み合わせ、英語のアイキャッチ画像プロンプトを生成。`title` / `body_excerpt` は互換のため受け取るがプロンプトには含めない（日本語の文字描画を避けるため） |

## パフォーマンス最適化

- **非同期処理**: 情報収集ツールはasyncで並行実行し、記事生成の待ち時間を短縮
- **キャッシュ**: 頻繁にアクセスするカテゴリ・タグ一覧はキャッシュして再利用
- **ストリーミング**: 長文記事の生成時はストリーミング出力で体感速度を向上

## セキュリティ考慮事項

- **認証情報管理**: WordPress API認証情報は `.env` ファイルで管理し、`.gitignore` で除外
- **入力検証**: ユーザー入力（トピック、URL等）のバリデーション実施
- **API通信**: HTTPS必須、タイムアウト設定
- **ローカル保存**: 生成記事はローカルファイルとして保存し、投稿失敗時のデータ損失を防止

## エラーハンドリング

### エラーの分類

| エラー種別 | 処理 | ユーザーへの表示 |
|-----------|------|-----------------|
| WordPress API認証エラー | リトライ不可、設定確認を案内 | 「WordPress認証に失敗しました。.envの設定を確認してください」 |
| WordPress API通信エラー | リトライなし、即時エラー | 「WordPress接続に失敗しました。ローカルにドラフトを保存しました」 |
| 情報収集タイムアウト | スキップして利用可能なデータで生成 | 「一部の情報収集がタイムアウトしました。取得済みデータで記事を生成します」 |
| URL取得エラー | スキップ | 「指定URLの取得に失敗しました: {url}」 |
| テンプレート不存在 | TemplateNotFoundError を送出 | 「テンプレート '{content_type}' が見つかりません」 |
| 入力バリデーションエラー | 即時エラー | 「{field}が不正です: {reason}」 |
| X API認証エラー | リトライ不可、設定確認を案内 | 「認証に失敗しました。.envのX_API_KEY等を確認してください」 |
| X API通信エラー | 1回リトライ後に失敗 | 「通信エラー: {error}」 |
| X投稿文字数超過 | 投稿前にバリデーション | 「投稿テキストが280文字を超えています（{N}文字超過）」 |
| 画像生成エラー | `ImageGenerationError` を送出 | 「画像生成エラー: {原因}」（API呼び出し失敗・セーフティ拒否・空プロンプト等） |

## テスト戦略

### ユニットテスト
- BlogPostGenerator: テンプレート適用、ドラフト生成ロジック
- WordPressPublisher: API呼び出し（モック）、レスポンスパース
- XPublisher: ツイート投稿（モック）、スレッド投稿、文字数バリデーション、エラーハンドリング
- Collector群: 各情報源からのデータ取得（モック）
  - NotionBaseCollector: 共通ヘルパー（プロパティ抽出、ページネーション）
  - NotionNewsCollector: Google Alertニュース取得（created_timeフィルタ）
  - NotionPaperCollector: Arxiv論文取得（公開日フィルタ/テーマ指定）
  - NotionMediumCollector: Medium Daily Digest取得（Dateフィルタ/テーマ指定）
- ContentTemplate: テンプレートのロード・バリデーション

### 統合テスト
- 記事生成→ローカル保存の一連フロー
- 情報収集→記事生成の連携
- Notion API→週刊AIニュース記事生成の連携
- Notion API→論文レビュー記事生成の連携
- Notion API→Medium記事取得の連携
- テンプレート選択→記事構成の整合性

### E2Eテスト
- `/create-blog-post` コマンドの実行→記事生成→投稿の全フロー（WordPress APIはモック）
