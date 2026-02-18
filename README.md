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
| `NOTION_TOKEN` | Notion Integration Token（Notion Collector使用時は必須） |
| `NOTION_NEWS_DB_ID` | Google Alertニュース DB ID（NotionNewsCollector用） |
| `NOTION_PAPER_DB_ID` | Arxiv論文 DB ID（NotionPaperCollector用） |
| `NOTION_MEDIUM_DB_ID` | Medium Daily Digest DB ID（NotionMediumCollector用） |

### Notion API セットアップ

Notion Collector（ニュース・論文・Medium記事の収集）を使用するには、以下の手順でセットアップが必要です。

#### 1. Notion Integration の作成

1. [Notion Integrations](https://www.notion.so/profile/integrations) にアクセス
2. 「New integration」をクリック
3. 名前を入力（例: `social-content-creator`）し、関連するワークスペースを選択
4. 「Capabilities」で「Read content」が有効になっていることを確認
5. 「Save」をクリックし、表示された `secret_xxx...` トークンをコピー

#### 2. データベースへの接続

各データベースページで Integration を接続します:

1. Notion でデータベースページを開く
2. 右上の「...」メニュー → 「Connections」→ 作成した Integration を追加

対象データベース:

| Collector | DB名 | 主要プロパティ |
|---|---|---|
| NotionNewsCollector | Google Alerts 記事一覧DB | Title, Summary, Source, Tags, URL |
| NotionPaperCollector | LLM + RAG / FINETUNING | タイトル, 日本語訳, 概要, 公開日, URL |
| NotionMediumCollector | Medium Daily Digest 記事一覧DB | Title, Japanese Title, Author, Summary, Date, URL |

#### 3. DB ID の確認

データベースページのURLからIDを取得します:

```
https://www.notion.so/{workspace}/{database_id}?v={view_id}
                                  ^^^^^^^^^^^^
                                  この部分がDB ID
```

#### 4. .env への設定

```bash
NOTION_TOKEN=secret_xxxxxxxxxxxxxxxxxxxxx
NOTION_NEWS_DB_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
NOTION_PAPER_DB_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
NOTION_MEDIUM_DB_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```
