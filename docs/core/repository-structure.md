> **ステータス: 実装済み**
> 最終更新: 2026-02-13

# リポジトリ構造定義書 (Repository Structure Document)

## プロジェクト構造

```
social-content-creator/
├── .claude/
│   ├── commands/               # スラッシュコマンド
│   ├── skills/                 # タスクモード別スキル
│   │   ├── create-blog-post/   # ブログ記事生成スキル
│   │   ├── publish-to-x/       # X（Twitter）投稿スキル
│   │   ├── publish-to-wordpress/ # WordPress投稿スキル
│   │   ├── wordpress-setup/    # WordPressセットアップスキル（Playwright MCP使用）
│   │   └── ...                 # 汎用スキル（steering, validation, prd-writing等）
│   └── settings.json           # Claude Code設定
├── src/
│   ├── generators/             # 記事生成ロジック
│   │   ├── __init__.py
│   │   └── blog_post.py
│   ├── collectors/             # 情報収集ツール群
│   │   ├── __init__.py
│   │   ├── base.py             # CollectorProtocol定義
│   │   ├── web_search.py
│   │   ├── url_fetcher.py
│   │   ├── gemini.py
│   │   ├── notion_news.py          # Notion Google Alertニュース取得
│   │   ├── notion_paper.py         # Notion Arxiv論文取得
│   │   └── github.py
│   ├── publishers/             # 投稿先プラットフォーム連携
│   │   ├── __init__.py
│   │   ├── base.py             # PublisherProtocol定義
│   │   ├── wordpress.py
│   │   └── x.py                # XPublisher（X API v2投稿）
│   ├── templates/              # コンテンツタイプ別テンプレート
│   │   ├── __init__.py
│   │   ├── weekly_ai_news.py
│   │   ├── paper_review.py
│   │   ├── project_intro.py
│   │   ├── tool_tips.py
│   │   ├── market_analysis.py
│   │   ├── ml_practice.py
│   │   ├── cv.py
│   │   └── feature.py
│   ├── models/                 # データモデル定義
│   │   ├── __init__.py
│   │   ├── blog_post.py
│   │   └── template.py
│   ├── utils/                  # 共通ユーティリティ
│   │   ├── __init__.py
│   │   └── markdown.py
│   └── errors.py               # カスタムエラークラス
├── tests/
│   ├── conftest.py             # テストフィクスチャ
│   ├── unit/
│   │   ├── generators/
│   │   │   └── test_blog_post.py
│   │   ├── models/
│   │   │   ├── test_blog_post.py
│   │   │   └── test_template.py
│   │   ├── collectors/
│   │   │   ├── test_web_search.py
│   │   │   ├── test_url_fetcher.py
│   │   │   ├── test_gemini.py
│   │   │   ├── test_notion_news.py
│   │   │   ├── test_notion_paper.py
│   │   │   └── test_github.py
│   │   ├── publishers/
│   │   │   ├── test_wordpress.py
│   │   │   └── test_x.py
│   │   ├── utils/
│   │   │   └── test_markdown.py
│   │   └── templates/
│   │       └── test_templates.py
│   └── integration/
│       └── test_generate_and_save.py
├── docs/
│   ├── core/                   # 中核ドキュメント
│   │   ├── product-requirements.md
│   │   ├── functional-design.md
│   │   ├── architecture.md
│   │   ├── repository-structure.md
│   │   ├── development-guidelines.md
│   │   ├── glossary.md
│   ├── refs/                   # 調査レポート・参考資料
│   │   └── wordpress-theme-research-2026.md  # WordPress テーマ調査レポート
│   ├── ideas/                  # アイデア・ブレインストーミング
│   │   └── 20260213-social-content-creator.md
│   ├── briefs/                 # ブレスト結果の方針メモ（記事生成前のブリーフ）
│   ├── drafts/                 # 下書き記事（作成日ベース）
│   │   ├── weekly-ai-news/
│   │   ├── paper-review/
│   │   ├── project-intro/
│   │   ├── tool-tips/
│   │   ├── market-analysis/
│   │   ├── ml-practice/
│   │   ├── cv/
│   │   └── feature/
│   └── posts/                  # 投稿済み記事（投稿日ベース）
│       └── YYYY/
│           └── MM/
│               └── YYYYMMDD-{type}-{slug}.md
├── .steering/                  # 作業計画・タスク管理
├── .env.example                # 環境変数テンプレート
├── .env                        # 環境変数（.gitignore対象）
├── .gitignore
├── pyproject.toml              # プロジェクト設定・依存関係
├── CLAUDE.md                   # Claude Code設定
└── README.md
```

## ディレクトリ詳細

### src/ (ソースコードディレクトリ)

#### generators/

**役割**: 記事生成のビジネスロジック

**配置ファイル**:
- `blog_post.py`: ブログ記事の生成エンジン

**命名規則**:
- ファイル名: snake_case、生成対象を表す名詞
- クラス名: PascalCase（例: `BlogPostGenerator`）

**依存関係**:
- 依存可能: `templates/`, `collectors/`, `models/`
- 依存禁止: `publishers/`（生成と投稿は分離）

**例**:
```
generators/
├── __init__.py
└── blog_post.py        # BlogPostGenerator クラス
```

#### collectors/

**役割**: 外部情報源からのデータ収集

**配置ファイル**:
- `base.py`: `CollectorProtocol` インターフェース定義
- `web_search.py`: Web検索による情報収集
- `url_fetcher.py`: 指定URLの内容取得
- `gemini.py`: Gemini CLI経由の調査レポート生成
- `notion_news.py`: Notion MCP経由でGoogle Alertニュース記事を取得
- `notion_paper.py`: Notion MCP経由でArxiv論文データを取得
- `github.py`: GitHub API経由のリポジトリ情報取得

**命名規則**:
- ファイル名: snake_case、情報源を表す名詞
- クラス名: PascalCase + Collector（例: `WebSearchCollector`）

**依存関係**:
- 依存可能: `models/`, `utils/`
- 依存禁止: `generators/`, `publishers/`, `templates/`

**例**:
```
collectors/
├── __init__.py
├── base.py             # CollectorProtocol
├── web_search.py       # WebSearchCollector
├── url_fetcher.py      # URLFetcherCollector
├── gemini.py           # GeminiCollector
├── notion_news.py      # NotionNewsCollector
├── notion_paper.py     # NotionPaperCollector
└── github.py           # GitHubCollector
```

#### publishers/

**役割**: 投稿先プラットフォームとの連携

**配置ファイル**:
- `base.py`: `PublisherProtocol` インターフェース定義
- `wordpress.py`: WordPress REST API連携
- `x.py`: X API v2連携（OAuth 1.0a認証）

**命名規則**:
- ファイル名: snake_case、プラットフォーム名
- クラス名: PascalCase + Publisher（例: `WordPressPublisher`, `XPublisher`）

**依存関係**:
- 依存可能: `models/`, `utils/`
- 依存禁止: `generators/`, `collectors/`, `templates/`

**例**:
```
publishers/
├── __init__.py
├── base.py             # PublisherProtocol
├── wordpress.py        # WordPressPublisher
└── x.py                # XPublisher
```

#### templates/

**役割**: コンテンツタイプ別の記事テンプレート定義

**配置ファイル**:
- 各コンテンツタイプに対応するテンプレートファイル

**命名規則**:
- ファイル名: snake_case、コンテンツタイプ名（例: `weekly_ai_news.py`）

**依存関係**:
- 依存可能: `models/`
- 依存禁止: `generators/`, `collectors/`, `publishers/`

#### models/

**役割**: データモデル（dataclass / Pydantic model）の定義

**配置ファイル**:
- `blog_post.py`: `BlogPost`, `PostStatus`, `ContentType`, `PublishResult`, `XPublishResult` 等
- `template.py`: `ContentTemplate` 等

**命名規則**:
- ファイル名: snake_case、エンティティ名
- クラス名: PascalCase

**依存関係**:
- 依存可能: なし（最下層）
- 依存禁止: 他の全モジュール

#### utils/

**役割**: 複数モジュールで共有するユーティリティ関数

**配置ファイル**:
- `markdown.py`: Markdown処理ユーティリティ

**命名規則**:
- ファイル名: snake_case、機能を表す名詞

**依存関係**:
- 依存可能: 標準ライブラリ、サードパーティライブラリのみ
- 依存禁止: `src/` 内の他モジュール

### tests/ (テストディレクトリ)

#### unit/

**役割**: ユニットテストの配置

**構造**:
```
tests/unit/
├── generators/
│   └── test_blog_post.py
├── models/
│   ├── test_blog_post.py
│   └── test_template.py
├── collectors/
│   ├── test_web_search.py
│   ├── test_url_fetcher.py
│   ├── test_gemini.py
│   ├── test_notion_news.py
│   ├── test_notion_paper.py
│   └── test_github.py
├── publishers/
│   ├── test_wordpress.py
│   └── test_x.py
├── utils/
│   └── test_markdown.py
└── templates/
    └── test_templates.py
```

**命名規則**:
- パターン: `test_[テスト対象ファイル名].py`
- 例: `blog_post.py` → `test_blog_post.py`

#### integration/

**役割**: 統合テストの配置

**構造**:
```
tests/integration/
└── test_generate_and_save.py
```

### docs/ (ドキュメントディレクトリ)

**配置ドキュメント**:
- `docs/core/`: 中核ドキュメント（PRD、設計書、ガイドライン等）
- `docs/ideas/`: アイデア・ブレインストーミング
- `docs/briefs/`: ブレスト結果の方針メモ（記事生成前のブリーフ）
- `docs/drafts/`: 下書き記事の保管（コンテンツタイプ別、ファイル名の `YYYYMMDD` は**作成日**）
- `docs/posts/`: 投稿済み記事の保管（年/月でサブディレクトリ分割、ファイル名の `YYYYMMDD` は**投稿日**）

## ファイル配置規則

### ソースファイル

| ファイル種別 | 配置先 | 命名規則 | 例 |
|------------|--------|---------|-----|
| 生成エンジン | `src/generators/` | `{target}.py` | `blog_post.py` |
| 情報収集ツール | `src/collectors/` | `{source}.py` | `web_search.py` |
| 投稿先連携 | `src/publishers/` | `{platform}.py` | `wordpress.py` |
| テンプレート | `src/templates/` | `{content_type}.py` | `weekly_ai_news.py` |
| データモデル | `src/models/` | `{entity}.py` | `blog_post.py` |
| ユーティリティ | `src/utils/` | `{function}.py` | `markdown.py` |

### テストファイル

| テスト種別 | 配置先 | 命名規則 | 例 |
|-----------|--------|---------|-----|
| ユニットテスト | `tests/unit/{layer}/` | `test_{対象}.py` | `test_blog_post.py` |
| 統合テスト | `tests/integration/` | `test_{シナリオ}.py` | `test_generate_and_save.py` |

### 設定ファイル

| ファイル種別 | 配置先 | 命名規則 |
|------------|--------|---------|
| 環境変数 | プロジェクトルート | `.env` / `.env.example` |
| ツール設定 | プロジェクトルート | `pyproject.toml` |
| Git設定 | プロジェクトルート | `.gitignore` |

## 命名規則

### ディレクトリ名

- **レイヤーディレクトリ**: 複数形、snake_case
  - 例: `generators/`, `collectors/`, `publishers/`, `templates/`, `models/`
- **テストディレクトリ**: src構造をミラー
  - 例: `tests/unit/generators/`, `tests/unit/collectors/`

### ファイル名

- **モジュールファイル**: snake_case
  - 例: `blog_post.py`, `web_search.py`, `wordpress.py`
- **テストファイル**: `test_` プレフィックス + snake_case
  - 例: `test_blog_post.py`, `test_wordpress.py`

## 依存関係のルール

### モジュール間の依存

```
models/          ← 最下層、依存なし
    ↑
utils/           ← 標準ライブラリのみ
    ↑
templates/       ← models
    ↑
collectors/      ← models, utils
publishers/      ← models, utils
    ↑
generators/      ← templates, collectors, models
```

**禁止される依存**:
- `models/` → 他の `src/` モジュール (最下層のため)
- `collectors/` → `generators/` (循環依存防止)
- `publishers/` → `generators/` (生成と投稿の分離)
- `templates/` → `collectors/`, `publishers/` (テンプレートは純粋なデータ)

## スケーリング戦略

### 機能の追加

**新しいCollectorの追加**（例: 新しい情報源を追加する場合）:
1. `src/collectors/` に新ファイルを作成
2. `CollectorProtocol` を実装
3. `tests/unit/collectors/` にテストを追加

**新しいPublisherの追加**:
1. `src/publishers/` に新ファイルを作成（例: `twitter.py`）
2. `PublisherProtocol` を実装
3. `tests/unit/publishers/` にテストを追加

**新しいテンプレートの追加**:
1. `src/templates/` に新ファイルを作成
2. テンプレートのメタ情報とプロンプトを定義
3. `tests/unit/templates/` にテストを追加

### ファイルサイズの管理

**ファイル分割の目安**:
- 1ファイル: 300行以下を推奨
- 300-500行: リファクタリングを検討
- 500行以上: 分割を強く推奨

## 特殊ディレクトリ

### .steering/ (ステアリングファイル)

**役割**: 特定の開発作業における「今回何をするか」を定義

**構造**:
```
.steering/
└── [YYYYMMDD]-[task-name]/
    ├── requirements.md      # 今回の作業の要求内容
    ├── design.md            # 変更内容の設計
    └── tasklist.md          # タスクリスト
```

### .claude/ (Claude Code設定)

**役割**: Claude Code設定とカスタマイズ

**構造**:
```
.claude/
├── commands/                # スラッシュコマンド
├── skills/                  # タスクモード別スキル
│   ├── create-blog-post/    # ブログ記事生成スキル
│   ├── publish-to-x/        # X（Twitter）投稿スキル
│   ├── publish-to-wordpress/ # WordPress投稿スキル
│   ├── wordpress-setup/     # WordPressセットアップスキル（Playwright MCP使用）
│   └── ...                  # 汎用スキル（steering, validation, prd-writing, glossary-creation等）
└── settings.json            # Claude Code設定
```

## 除外設定

### .gitignore

プロジェクトで除外すべきファイル:
- `.venv/`
- `__pycache__/`
- `*.pyc`
- `.env`
- `.steering/`
- `*.log`
- `.DS_Store`
- `dist/`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- `coverage/`
- `logs/`
