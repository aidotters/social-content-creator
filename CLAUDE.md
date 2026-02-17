# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AIエンジニア「Aidotters」の情報発信効率化ツール。ブログ記事生成・WordPress投稿・Notion連携・情報収集を一貫して行う。

## Commands

### Running Tests
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/unit/generators/test_blog_post.py

# Run tests with verbose output
uv run pytest -v
```

### Linting/Formatting
```bash
uv run ruff check .
uv run black .
uv run mypy src/
```

## Architecture

### Key Directories
- `src/`: ソースコード
  - `src/models/`: データモデル（BlogPost, CollectedData, PublishResult, XPublishResult, ContentTemplate）
  - `src/generators/`: 記事生成エンジン（BlogPostGenerator）
  - `src/collectors/`: 情報収集ツール群（URL, GitHub, Gemini, WebSearch, NotionNews, NotionPaper）
  - `src/publishers/`: 投稿連携（WordPressPublisher, XPublisher）
  - `src/templates/`: コンテンツタイプ別テンプレート（8種類）
  - `src/utils/`: ユーティリティ（Markdown処理）
  - `src/errors.py`: カスタムエラークラス
- `tests/`: テストコード
  - `tests/unit/`: ユニットテスト
  - `tests/integration/`: 統合テスト
- `docs/`: ドキュメント
  - `docs/core/`: 中核ドキュメント
  - `docs/drafts/`: 下書き記事
  - `docs/posts/`: 投稿済み記事
  - `docs/ideas/`: アイデア・ブレインストーミング
  - `docs/briefs/`: ブレスト結果の方針メモ（記事生成前のブリーフ）
- `.claude/skills/create-blog-post/`: ブログ記事生成スキル
- `.claude/skills/publish-to-x/`: X（Twitter）投稿スキル
- `.claude/skills/publish-to-wordpress/`: WordPress投稿スキル
- `.claude/skills/wordpress-setup/`: WordPressセットアップスキル（Playwright MCP使用）
- `.steering/`: 作業計画・タスク管理ファイル

### Design Patterns
- **Protocol**: CollectorProtocol, PublisherProtocol で共通インターフェース定義
- **Registry**: テンプレートレジストリパターンで content_type からテンプレートを取得
- **2層アーキテクチャ**: スキル層（Claude Code）+ ツール層（Python）

### Configuration
- 環境変数: `.env` (`.env.example` を参照)
- 設定: `pyproject.toml`

## Testing
- テストフレームワーク: pytest + pytest-asyncio
- テストディレクトリ: `tests/`
- フィクスチャ: `tests/conftest.py`
- HTTPモック: respx
