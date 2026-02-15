# create-blog-post スキル

ブログ記事の生成・レビュー・投稿を一括で行うスキルです。

## コマンド形式

```
/create-blog-post --type <content_type> [--topic <topic>] [--url <url>] [--repo <owner/repo>]
```

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `--type` | Yes | コンテンツタイプ（下記参照） |
| `--topic` | No | キーワード・トピック |
| `--url` | No | 参照URL |
| `--repo` | No | GitHubリポジトリ（owner/repo形式） |

## コンテンツタイプ

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

## 実行フロー

### ステップ1: 引数の解析と情報収集

1. **コマンド引数を解析**する
   - `--type`: 必須。テンプレート取得に使用
   - `--topic`: 記事のテーマとして使用
   - `--url`: URLFetcherCollectorで内容を取得
   - `--repo`: GitHubCollectorでリポジトリ情報を取得

2. **テンプレートを取得**する
   ```bash
   python -c "
   from src.templates import get_template
   import json
   t = get_template('${TYPE}')
   print(json.dumps(t.model_dump(), ensure_ascii=False, default=str))
   "
   ```

3. **タイプに応じた情報収集**を行う
   - `weekly-ai-news`:
     1. Notion MCP経由でGoogle Alertニュース取得（過去7日間）
        ```
        mcp__claude_ai_Notion__search でGoogle Alertデータベースを検索
        ```
     2. WebSearchで最新AIニュースを検索
   - `paper-review`:
     1. `--url` が指定されていればURLの内容を取得
     2. Notion MCP経由でArxiv論文データベースを検索
   - `project-intro`:
     1. `--repo` のGitHub情報を取得
   - その他:
     1. `--topic` に基づいてWebSearchで情報収集
     2. `--url` があれば内容を取得

### ステップ2: 記事の生成

1. **プロンプトコンテキストを構築**する
   ```bash
   python -c "
   from src.generators.blog_post import BlogPostGenerator
   from src.templates import get_template
   gen = BlogPostGenerator()
   template = get_template('${TYPE}')
   context = gen.build_prompt_context(template, topic='${TOPIC}')
   print(context)
   "
   ```

2. **記事本文を生成**する（Claude自身が生成）
   - テンプレートのセクション構成に従う
   - 文体ガイドに従ったです・ます調で記述
   - 収集データを適切に引用・参照
   - 文字数目安を意識して執筆

3. **BlogPostオブジェクトを作成し、ドラフト保存**する
   ```bash
   python -c "
   import asyncio
   from src.generators.blog_post import BlogPostGenerator
   gen = BlogPostGenerator()
   post = asyncio.run(gen.generate(
       content_type='${TYPE}',
       title='${TITLE}',
       content='''${CONTENT}''',
       topic='${TOPIC}',
   ))
   path = asyncio.run(gen.save_draft(post))
   print(f'保存先: {path}')
   "
   ```

### ステップ3: レビューと修正

1. 生成した記事を**ユーザーに表示**する
2. ユーザーに**修正ポイントを確認**する
3. 必要に応じて記事を**修正・再保存**する

### ステップ4: WordPress投稿（ユーザーが指示した場合）

1. ユーザーに**投稿ステータスを確認**する（下書き or 公開）
2. カテゴリ・タグを確認
3. **WordPress投稿を実行**
   ```bash
   python -c "
   import asyncio
   from src.publishers.wordpress import WordPressPublisher
   from src.generators.blog_post import BlogPostGenerator
   pub = WordPressPublisher()
   gen = BlogPostGenerator()
   post = asyncio.run(gen.load_draft(Path('${DRAFT_PATH}')))
   result = asyncio.run(pub.publish(post, status='${STATUS}'))
   if result.success:
       print(f'投稿成功: {result.url}')
       dest = asyncio.run(gen.move_to_published(post, Path('${DRAFT_PATH}')))
       print(f'移動先: {dest}')
   else:
       print(f'投稿失敗: {result.error_message}')
   "
   ```

## 使用例

```
# 週刊AIニュースハイライト
/create-blog-post --type weekly-ai-news

# 論文解説
/create-blog-post --type paper-review --url https://arxiv.org/abs/2401.12345

# GitHubプロジェクト紹介
/create-blog-post --type project-intro --repo langchain-ai/langchain

# トピック指定の記事
/create-blog-post --type tool-tips --topic "Claude Codeの活用法"
```

## 文体ガイド

- **です・ます調**で統一
- **丁寧かつ親しみやすい**トーンで執筆
- 技術的な内容は**具体例やコード例**を交えて解説
- 読者が「**自分でも試してみよう**」と思えるような記事を目指す
- 著者は「Aidotters」のAIエンジニアとして執筆
