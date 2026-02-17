# Social Content Creator

AIエンジニア用のClaude Codeを利用した情報発信効率化ツール。ブログ記事生成・WordPress投稿・Notion連携・情報収集を一貫して行います。

## セットアップ

```bash
# 依存関係のインストール
uv sync --dev

# 環境変数の設定
cp .env.example .env
# .env ファイルを編集
```

## 使い方

### Claude Codeスキルで記事を生成

```bash
# 週刊AIニュースハイライト
/create-blog-post --type weekly-ai-news

# 論文解説
/create-blog-post --type paper-review --url https://arxiv.org/abs/xxxx

# GitHubプロジェクト紹介
/create-blog-post --type project-intro --repo owner/repo

# トピック指定
/create-blog-post --type tool-tips --topic "Claude Codeの活用法"
```

### コンテンツタイプ

| タイプ | 説明 | 文字数目安 |
|--------|------|-----------|
| `weekly-ai-news` | 週刊AIニュースハイライト | 3,000〜5,000字 |
| `paper-review` | 論文解説 | 5,000〜8,000字 |
| `project-intro` | GitHubプロジェクト紹介 | 3,000〜5,000字 |
| `tool-tips` | ツール・Tips紹介 | 3,000〜5,000字 |
| `market-analysis` | AI×株式投資・企業分析 | 3,000〜8,000字 |
| `ml-practice` | AI×データ分析・ML開発 | 3,000〜8,000字 |
| `cv` | 画像認識・コンピュータビジョン | 3,000〜8,000字 |
| `feature` | 特集記事 | 15,000〜20,000字 |

### WordPressに投稿

```bash
# ドラフト記事をWordPressに下書き投稿
/publish-to-wordpress docs/drafts/2026-02-17-example.md

# 公開投稿
/publish-to-wordpress docs/drafts/2026-02-17-example.md --status publish
```

### X（Twitter）に投稿

```bash
# 記事の紹介をXに投稿
/publish-to-x docs/posts/2026-02-17-example.md
```

## 開発

```bash
# テスト実行
uv run pytest tests/ -v

# Lint
uv run ruff check .

# 型チェック
uv run mypy src/

# フォーマット
uv run black .
```

## アーキテクチャ

```
スキル層（Claude Code Skills） ← ユーザーインターフェース
  ↕
ツール層（Python バックエンド） ← ビジネスロジック
  ├── generators/  記事生成
  ├── collectors/  情報収集
  ├── publishers/  投稿連携
  ├── templates/   テンプレート
  └── models/      データモデル
```

## 環境変数

| 変数名 | 説明 |
|--------|------|
| `WORDPRESS_URL` | WordPressサイトURL |
| `WORDPRESS_USER` | WordPressユーザー名 |
| `WORDPRESS_APP_PASSWORD` | WordPress Application Password |
| `GEMINI_API_KEY` | Gemini APIキー（オプション） |
| `GITHUB_TOKEN` | GitHub APIトークン（オプション） |
| `X_API_KEY` | X API Key（オプション） |
| `X_API_SECRET` | X API Secret（オプション） |
| `X_ACCESS_TOKEN` | X Access Token（オプション） |
| `X_ACCESS_TOKEN_SECRET` | X Access Token Secret（オプション） |
