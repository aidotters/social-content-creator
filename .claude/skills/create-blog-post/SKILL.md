---
name: create-blog-post
description: ブログ記事の生成・レビュー・投稿を一括で行うスキル。コンテンツタイプ（weekly-ai-news, paper-review, project-intro等）を指定して記事を作成し、WordPress投稿まで対応。引数なしで起動するとブレストフェーズから開始。
---

# create-blog-post スキル

ブログ記事の生成・レビュー・投稿を一括で行うスキルです。

## コマンド形式

```
/create-blog-post [--type <content_type>] [--topic <topic>] [--url <url>] [--repo <owner/repo>] [--brief <path>]
```

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `--type` | No | コンテンツタイプ（下記参照）。未指定時はブレストフェーズから開始 |
| `--topic` | No | キーワード・トピック |
| `--url` | No | 参照URL |
| `--repo` | No | GitHubリポジトリ（owner/repo形式） |
| `--brief` | No | ブリーフファイルのパス（`docs/briefs/` 配下） |

## フロー分岐

```
--type 指定あり       → 従来フロー（ステップ1〜4）
--brief 指定あり      → ブリーフ読み込み → ステップ1〜4（type/topic等をブリーフから取得）
--type も --brief もなし → ステップ0: ブレスト → 方針確定 → ステップ1〜4
```

- `--type` が指定されていれば、従来通りステップ1（情報収集）から開始する
- `--brief` が指定されていれば、ブリーフファイルを読み込み、記載された `type`・方針・情報ソースを元にステップ1から開始する
- どちらも未指定の場合、ステップ0（ブレスト）から開始し、方針が固まったらステップ1に進む

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

### ステップ0: ブレスト（--type 未指定時のみ）

`--type` が指定されていない場合、記事の方向性を決めるブレストフェーズを実行する。

#### 0-1. ネタ出し

トピックが指定されていればそこを起点に、なければ以下をソースにしてネタを広げる。

- **Notion MCP** でストックしたニュース・論文・記事を検索
  ```
  mcp__claude_ai_Notion__search で関連データベースを検索
  ```
- **WebSearch** で最新トレンドを調査
- **ユーザーとの対話** で関心領域を掘り下げる

#### 0-2. 切り口の提案

3〜5つの切り口を提案し、ユーザーと壁打ちする。各切り口について以下を提示する:

- **タイトル案**
- **想定読者**
- **記事タイプ**（content_type）
- **概要**（2〜3文）

ユーザーのフィードバックを受けて絞り込む。必要に応じて提案を修正・追加する。

#### 0-3. 方針の確定

ユーザーが1つを選択、またはカスタマイズしたら、以下を確定する:

- 記事タイプ（content_type）
- タイトル（仮）
- ターゲット読者
- 記事の切り口・主張
- 必要な情報ソース

#### 0-4. ブリーフ保存

確定した方針を `docs/briefs/YYYYMMDD-slug.md` に保存する。

```markdown
---
date: YYYY-MM-DD
type: <content_type>
status: confirmed
---

# ブリーフ: {仮タイトル}

## 方針
- **切り口**: ...
- **ターゲット読者**: ...
- **主張/メッセージ**: ...

## 情報ソース
- ...

## メモ
- ブレスト時の議論ポイント
```

#### 0-5. 記事生成へ

確定した方針でステップ1（情報収集）に進む。ブレストで決まった `--type`, `--topic` 等の情報を引き継ぐ。ブリーフファイルも情報収集時の参照資料として活用する。

### ステップ1: 引数の解析と情報収集

1. **コマンド引数を解析**する
   - `--type`: テンプレート取得に使用（ブレスト経由の場合は確定済み）
   - `--topic`: 記事のテーマとして使用
   - `--url`: URLFetcherCollectorで内容を取得
   - `--repo`: GitHubCollectorでリポジトリ情報を取得
   - `--brief`: ブリーフファイルを読み込み、frontmatterの `type` と本文の方針情報を取得。`--type` や `--topic` が未指定の場合はブリーフの値を使用する

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
# ブレストから始める（--type なし）
/create-blog-post

# トピックを指定してブレストから始める
/create-blog-post --topic "AIエージェント"

# 週刊AIニュースハイライト（従来フロー）
/create-blog-post --type weekly-ai-news

# 論文解説（従来フロー）
/create-blog-post --type paper-review --url https://arxiv.org/abs/2401.12345

# GitHubプロジェクト紹介（従来フロー）
/create-blog-post --type project-intro --repo langchain-ai/langchain

# トピック指定の記事（従来フロー）
/create-blog-post --type tool-tips --topic "Claude Codeの活用法"

# ブリーフから記事を作成
/create-blog-post --brief docs/briefs/20260216-ai-agent-trends.md
```

## 文体ガイド

- **です・ます調**で統一
- **丁寧かつ親しみやすい**トーンで執筆
- 技術的な内容は**具体例やコード例**を交えて解説
- 読者が「**自分でも試してみよう**」と思えるような記事を目指す
- 著者は「Aidotters」のAIエンジニアとして執筆
