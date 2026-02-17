---
name: publish-to-wordpress
description: ドラフト記事をWordPressに投稿するスキル。docs/drafts/配下のMarkdownファイルを指定してWordPressに下書きまたは公開投稿する。「WordPress投稿」「記事を投稿」「ブログを公開」「WPにアップ」などのリクエスト時に使用。/publish-to-wordpress コマンドで呼び出す。
---

# publish-to-wordpress スキル

ドラフト記事をWordPressに投稿する。

## コマンド形式

```
/publish-to-wordpress <draft-path> [--status draft|publish] [--categories cat1,cat2] [--tags tag1,tag2]
```

## 引数

| 引数 | 必須 | 説明 |
|------|:----:|------|
| `<draft-path>` | ○ | ドラフトファイルのパス（docs/drafts/配下） |
| `--status` | - | 投稿ステータス（デフォルト: draft） |
| `--categories` | - | カテゴリ名（カンマ区切り） |
| `--tags` | - | タグ名（カンマ区切り） |

## 実行フロー

### ステップ1: ドラフトの確認

1. `<draft-path>` が未指定の場合、`docs/drafts/` 配下のドラフト一覧を表示してユーザーに選択させる
2. ドラフトファイルを読み込み、タイトル・内容をユーザーに表示する

### ステップ2: 投稿設定の確認

ユーザーに以下を確認する（引数で未指定の場合）:

1. **投稿ステータス**: 下書き（draft）or 公開（publish）
2. **カテゴリ**: WordPress上の既存カテゴリを取得して提示
   ```bash
   uv run python -c "
   import asyncio
   from src.publishers.wordpress import WordPressPublisher
   pub = WordPressPublisher()
   cats = asyncio.run(pub.get_categories())
   for c in cats:
       print(f'  - {c[\"name\"]} (id: {c[\"id\"]})')
   "
   ```
3. **タグ**: 任意で指定

### ステップ3: WordPress投稿

```bash
uv run python -c "
import asyncio
from pathlib import Path
from src.publishers.wordpress import WordPressPublisher
from src.generators.blog_post import BlogPostGenerator

pub = WordPressPublisher()
gen = BlogPostGenerator()
post = asyncio.run(gen.load_draft(Path('${DRAFT_PATH}')))
result = asyncio.run(pub.publish(
    post,
    status='${STATUS}',
    categories=${CATEGORIES},
    tags=${TAGS},
))
if result.success:
    print(f'投稿成功: {result.url}')
    print(f'投稿ID: {result.post_id}')
else:
    print(f'投稿失敗: {result.error_message}')
"
```

### ステップ4: 投稿後処理

投稿成功時:

1. ドラフトファイルのfront matterに `wordpress_url` を追記する（投稿結果の `result.url` を使用）
   - front matterの `---` ブロック内に `wordpress_url: ${RESULT_URL}` を追加
   - `status: published` に更新
   - `published_at:` に現在日時を記録

2. ドラフトを投稿済みディレクトリに移動する
   ```bash
   uv run python -c "
   import asyncio
   from pathlib import Path
   from src.generators.blog_post import BlogPostGenerator
   gen = BlogPostGenerator()
   post = asyncio.run(gen.load_draft(Path('${DRAFT_PATH}')))
   dest = asyncio.run(gen.move_to_published(post, Path('${DRAFT_PATH}')))
   print(f'移動先: {dest}')
   "
   ```
3. 投稿URLをユーザーに表示する

4. **X投稿の確認**: ユーザーに「Xにも投稿しますか？」と確認する
   - 「はい」の場合: `/publish-to-x` スキルのフローを実行する。投稿済み記事のパス（`docs/posts/` に移動後のパス）を使用し、front matterの `wordpress_url` が紹介文に含まれる
   - 「いいえ」の場合: 処理を終了する

投稿失敗時:
- エラー内容を表示し、`.env` の `WORDPRESS_URL`, `WORDPRESS_USER`, `WORDPRESS_APP_PASSWORD` の設定を確認するよう案内する

## 環境変数

`.env` に以下が必要（`.env.example` 参照）:

```
WORDPRESS_URL=https://your-site.com
WORDPRESS_USER=your-username
WORDPRESS_APP_PASSWORD=your-app-password
```

未設定時は `wordpress-setup` スキルでの初期設定を案内する。
