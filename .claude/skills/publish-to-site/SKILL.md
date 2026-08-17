---
name: publish-to-site
description: ドラフト記事を静的サイト（aidotters.com / Astro）に公開するスキル。docs/drafts/配下のMarkdownをサイトリポジトリへ書き出し、ビルド検証してからコミットする。「サイトに公開」「記事を公開」「ブログを出す」などのリクエスト時に使用。/publish-to-site コマンドで呼び出す。WordPressへの投稿は publish-to-wordpress（移行前の旧経路）。
---

# publish-to-site スキル

ドラフト記事を静的サイト `aidotters-website` へ公開するスキルです。
WordPress REST API への投稿（`publish-to-wordpress`）を置き換えるものです。

## コマンド形式

```
/publish-to-site <draft-path> [--status draft|publish] [--image <path>] [--push]
```

## 引数

| 引数 | 必須 | 既定 | 説明 |
|------|------|------|------|
| `<draft-path>` | Yes | — | `docs/drafts/{type}/*.md` のパス |
| `--status` | No | `publish` | `publish` で公開、`draft` でサイト側のビルド対象外 |
| `--image` | No | 無し | アイキャッチ画像のローカルパス（`/generate-image` の出力）。WebP に変換して記事の隣に置く |
| `--push` | No | 無効 | commit 後に push する。**push した時点で本番サイトのデプロイが走る** |

## 前提条件

- `.env` に `AIDOTTERS_SITE_REPO`（サイトリポジトリのパス）が設定されていること
- サイトリポジトリで `npm install` 済みであること

## 実行フロー

### ステップ1: ドラフトの確認

ドラフトを読み込み、ユーザーに以下を提示して確認する。

- タイトル・サブタイトル・コンテンツタイプ
- **公開URL**（`/blog/{type}/{slug}/`）
- 公開かサイト側下書きか

```bash
uv run python -c "
import asyncio
from pathlib import Path
from src.generators.blog_post import BlogPostGenerator
from src.publishers.static_site import StaticSitePublisher

gen = BlogPostGenerator()
post = asyncio.run(gen.load_draft(Path('${DRAFT_PATH}')))
pub = StaticSitePublisher()
print(f'タイトル: {post.title}')
print(f'タイプ: {post.content_type}')
print(f'公開URL: /blog/{post.content_type}/{pub.resolve_slug(post)}/')
print(f'書き出し先: {pub.target_path(post)}')
"
```

週刊AIニュース（`weekly-ai-news`）のslugは**公開日（日本時間）ベース**で自動決定される。
タイトルの「第N週」表記は過去に重複した実績があるため使わない。

### ステップ2: サイトリポジトリへ書き出す

この時点では**コミットしない**。次のステップでビルドを検証してからコミットする。

```bash
uv run python -c "
import asyncio
from pathlib import Path
from src.generators.blog_post import BlogPostGenerator
from src.publishers.static_site import StaticSitePublisher

gen = BlogPostGenerator()
post = asyncio.run(gen.load_draft(Path('${DRAFT_PATH}')))
pub = StaticSitePublisher()
result = asyncio.run(pub.publish(post, status='${STATUS}', commit=False, featured_image_path=${IMAGE_PATH_OR_NONE}))
print(f'書き出し完了: {result.url}')
"
```

同じslugの記事が既にある場合はエラーで停止する。意図的な差し替えなら
`overwrite=True` を渡す。

### ステップ3: ビルド検証

**必ず実行する。** サイト側の zod スキーマと `migration-guard` が
frontmatter の不備・記事の欠落・旧URLの重複を検出する。

```bash
cd "$(uv run python -c 'from src.publishers.static_site import StaticSitePublisher; print(StaticSitePublisher().repo)')" && npm run build
```

- 成功: 記事数のログ（`記事 N 本を検証`）に、いま追加した1本が反映されているか確認する
- 失敗: **コミットせずに** 書き出したファイルを削除し、エラー内容をユーザーに報告する

### ステップ4: コミット

ビルドが通ってからコミットする。

```bash
uv run python -c "
import asyncio
from pathlib import Path
from src.generators.blog_post import BlogPostGenerator
from src.publishers.static_site import StaticSitePublisher

gen = BlogPostGenerator()
post = asyncio.run(gen.load_draft(Path('${DRAFT_PATH}')))
pub = StaticSitePublisher()
result = asyncio.run(pub.publish(post, status='${STATUS}', overwrite=True, featured_image_path=${IMAGE_PATH_OR_NONE}))
print(f'コミット完了: {result.url}')
"
```

### ステップ5: 投稿後処理

1. ドラフトの front matter を更新する
   - `status: published`
   - `published_at:` に現在日時
   - `site_url:` に公開URL（`/blog/{type}/{slug}/`）

2. ドラフトを投稿済みディレクトリへ移動する

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

3. **公開の確認**: `--push` が指定されていない場合、ユーザーに
   「サイトに反映しますか？（push するとデプロイが走ります）」と確認する。
   承認された場合のみ push する。

   ```bash
   cd "$(uv run python -c 'from src.publishers.static_site import StaticSitePublisher; print(StaticSitePublisher().repo)')" && git push
   ```

4. **X投稿の確認**: ユーザーに「Xにも投稿しますか？」と確認する。
   「はい」の場合は `/publish-to-x` スキルのフローを実行する。

## 注意事項

- **アイキャッチ画像**は `--image` で渡す。未指定なら `featured_image_path=None` にする。
  変換先は記事Markdownの隣（`{type}/{slug}.webp`）で、frontmatter には相対パスが入る。
  既に画像が置かれている記事を `--image` 無しで上書き publish しても参照は残る
- **コミット先ブランチ**は、サイトリポジトリでチェックアウト中のブランチになる。
  公開時は意図したブランチにいることを確認する
- frontmatter の形は `src/publishers/static_site.py` とサイト側の
  `src/content.config.ts` が対になっている。片方だけ変えるとビルドが落ちる
