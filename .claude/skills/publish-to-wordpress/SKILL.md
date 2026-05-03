---
name: publish-to-wordpress
description: ドラフト記事をWordPressに投稿するスキル。docs/drafts/配下のMarkdownファイルを指定してWordPressに下書きまたは公開投稿する。「WordPress投稿」「記事を投稿」「ブログを公開」「WPにアップ」などのリクエスト時に使用。/publish-to-wordpress コマンドで呼び出す。
---

# publish-to-wordpress スキル

ドラフト記事をWordPressに投稿する。アイキャッチ画像のアップロード・設定、既存記事へのアイキャッチ後付けにも対応。

## コマンド形式

```
# 通常投稿（新規）
/publish-to-wordpress <draft-path> [--status draft|publish] [--categories cat1,cat2] [--tags tag1,tag2]
                                   [--featured-image <path>] [--auto-generate-image]
                                   [--image-prompt "<text>"] [--image-alt "<text>"]

# 既存記事へのアイキャッチ後付け（Phase 3）
/publish-to-wordpress --post-id <id> [--featured-image <path>] [--auto-generate-image]
                                     [--image-prompt "<text>"] [--image-alt "<text>"] [--force]
```

## 引数

| 引数 | 必須 | 説明 |
|------|:----:|------|
| `<draft-path>` | ※ | ドラフトファイルのパス（docs/drafts/配下）。`--post-id` 指定時は不要 |
| `--status` | - | 投稿ステータス（デフォルト: draft） |
| `--categories` | - | カテゴリ名（カンマ区切り） |
| `--tags` | - | タグ名（カンマ区切り） |
| `--featured-image <path>` | - | アイキャッチに使う画像ファイルパス |
| `--auto-generate-image` | - | 画像未指定時に画像を自動生成（GeminiImageGenerator） |
| `--image-prompt "<text>"` | - | 自動生成プロンプトを上書き（未指定時は content_type + タイトル/本文から自動組み立て） |
| `--image-alt "<text>"` | - | alt属性を明示指定（未指定時は記事タイトル） |
| `--post-id <id>` | - | 既存記事へのアイキャッチ後付けモード |
| `--force` | - | 既存アイキャッチを上書き（`--post-id` 利用時に指定） |

## 実行フロー

### モード判定

- `--post-id` 指定 → **Phase 3（既存記事へのアイキャッチ後付けモード）** へ
- `--post-id` 未指定 → **通常モード** （ドラフトを新規投稿）

---

## 通常モード（新規投稿）

### ステップ1: ドラフトの確認

1. `<draft-path>` が未指定の場合、`docs/drafts/` 配下のドラフト一覧を表示してユーザーに選択させる
2. ドラフトファイルを読み込み、タイトル・サブタイトル（あれば）・内容をユーザーに表示する

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

### ステップ3: アイキャッチ画像の準備（任意）

#### `--featured-image <path>` 指定時

ファイルパスをそのまま `featured_image_path` に渡す（ステップ4参照）。事前に存在確認:

```bash
test -f "${FEATURED_IMAGE}" || echo "ファイルが存在しません: ${FEATURED_IMAGE}"
```

#### `--auto-generate-image` 指定時

画像生成プロンプトを組み立て → `GeminiImageGenerator.generate()` で生成 → 生成画像のパスを `featured_image_path` に渡す。

```bash
uv run python -c "
import asyncio
from pathlib import Path
from src.generators.image import GeminiImageGenerator
from src.generators.blog_post import BlogPostGenerator
from src.utils.image_prompt import build_featured_image_prompt

gen_image = GeminiImageGenerator()
gen_post = BlogPostGenerator()
post = asyncio.run(gen_post.load_draft(Path('${DRAFT_PATH}')))

# --image-prompt 指定時はそのまま、未指定時は自動組み立て
prompt = '''${IMAGE_PROMPT}''' or build_featured_image_prompt(
    content_type=post.content_type,
    title=post.title,
    body_excerpt=post.content[:300],
)
image_path = asyncio.run(gen_image.generate(
    prompt=prompt,
    aspect_ratio='16:9',
    slug=post.slug,
))
print(f'生成完了: {image_path}')
"
```

#### どちらも未指定

アイキャッチなしで投稿する。

### ステップ4: WordPress投稿

```bash
# categories にはカテゴリ名（str）のリストを渡す（IDではなく名前）
# featured_image_path はアイキャッチ画像のパス（Pathオブジェクト）。未指定時は None
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
    featured_image_path=Path('${FEATURED_IMAGE}') if '${FEATURED_IMAGE}' else None,
    featured_image_alt='${IMAGE_ALT}' if '${IMAGE_ALT}' else None,
))
if result.success:
    print(f'投稿成功: {result.url}')
    print(f'投稿ID: {result.post_id}')
else:
    print(f'投稿失敗: {result.error_message}')
"
```

### ステップ5: 投稿後処理

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

---

## Phase 3 モード（既存記事へのアイキャッチ後付け）

`--post-id <id>` 指定時はこのフローで動作する。**新規投稿は行わない。**

### ステップA: 画像の準備

#### A-1. `--featured-image <path>` 指定時

ファイルパスをそのまま使う。

#### A-2. `--auto-generate-image` 指定時

WordPress から既存記事のタイトル・本文を取得し、プロンプト組み立てに利用する。

> ⚠️ **注意**: WordPress REST API は `content_type` を返さないため、Phase 3 では `build_featured_image_prompt` のスタイル指定が必ず `feature`（cinematic hero image）にフォールバックする。記事タイプに合った画像にしたい場合は `--image-prompt "<text>"` で明示的にプロンプトを上書きすることを推奨する。

```bash
uv run python -c "
import asyncio
import re
from pathlib import Path
from src.publishers.wordpress import WordPressPublisher
from src.generators.image import GeminiImageGenerator
from src.utils.image_prompt import build_featured_image_prompt

pub = WordPressPublisher()
gen_image = GeminiImageGenerator()

post_data = asyncio.run(pub.get_post(${POST_ID}))
title = post_data['title']['rendered']
content_html = post_data['content']['rendered']
# 簡易的にHTMLタグを除去して本文冒頭を取得
body_excerpt = re.sub(r'<[^>]+>', '', content_html)[:300]

# --image-prompt 指定時はそのまま、未指定時は自動組み立て
# content_type は WordPress 側からは取得できないため、
# --image-prompt を渡すか、あるいは安全に 'feature' を既定値とする運用を推奨
prompt = '''${IMAGE_PROMPT}''' or build_featured_image_prompt(
    content_type='feature',
    title=title,
    body_excerpt=body_excerpt,
)
image_path = asyncio.run(gen_image.generate(
    prompt=prompt,
    aspect_ratio='16:9',
    slug=f'post-{${POST_ID}}',
))
print(f'生成完了: {image_path}')
"
```

### ステップB: アイキャッチアップロード＆設定

```bash
uv run python -c "
import asyncio
from pathlib import Path
from src.publishers.wordpress import WordPressPublisher

pub = WordPressPublisher()

# alt_text の決定: --image-alt 優先、なければ既存記事の title
alt_text = '${IMAGE_ALT}' if '${IMAGE_ALT}' else None
if alt_text is None:
    post_data = asyncio.run(pub.get_post(${POST_ID}))
    alt_text = post_data['title']['rendered']

media_id = asyncio.run(pub.upload_media(
    image_path=Path('${IMAGE_PATH}'),
    alt_text=alt_text,
))
print(f'メディアID: {media_id}')

asyncio.run(pub.set_featured_media(
    post_id=${POST_ID},
    media_id=media_id,
    force=${FORCE},
))
print(f'アイキャッチ設定完了: post_id={${POST_ID}}, media_id={media_id}')
"
```

### エラー時の案内

- **「投稿 {id} には既にアイキャッチ ... が設定されています」エラー**:
  既存アイキャッチを上書きする場合は `--force` を付与して再実行するよう案内する。
- **「画像ファイルが存在しません」エラー**:
  指定パスを確認するか、`--auto-generate-image` での生成を提案する。

---

## 環境変数

`.env` に以下が必要（`.env.example` 参照）:

```
WORDPRESS_URL=https://your-site.com
WORDPRESS_USER=your-username
WORDPRESS_APP_PASSWORD=your-app-password
```

`--auto-generate-image` 利用時は `GEMINI_API_KEY` も必要。

未設定時は `wordpress-setup` スキルでの初期設定を案内する。

## 使用例

```
# 通常投稿（アイキャッチなし）
/publish-to-wordpress docs/drafts/foo.md

# 通常投稿 + 既存画像をアイキャッチに
/publish-to-wordpress docs/drafts/foo.md --featured-image outputs/images/hero.png

# 通常投稿 + アイキャッチ自動生成
/publish-to-wordpress docs/drafts/foo.md --auto-generate-image

# 既存記事にアイキャッチを後付け
/publish-to-wordpress --post-id 12345 --featured-image outputs/images/hero.png

# 既存アイキャッチを上書き
/publish-to-wordpress --post-id 12345 --featured-image new.png --force
```
