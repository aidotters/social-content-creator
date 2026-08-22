---
name: generate-image
description: Gemini 2.5 Flash Image（Nanobanana）で画像を生成するスキル。ブログ記事のアイキャッチ画像やSNS投稿用画像の生成に使用。「画像生成」「アイキャッチ作って」「画像を作って」「Nanobananaで画像」などのリクエスト時に使用。/generate-image コマンドで呼び出す。
---

# generate-image スキル

Gemini 2.5 Flash Image（通称 Nanobanana）を使って画像を生成する。Google AI Studio の無料枠で動作するため、追加のAPI課金は不要。

## コマンド形式

```
/generate-image [--prompt <text>] [--aspect <ratio>] [--slug <slug>] [--filename <name>]
```

## 引数

| 引数 | 必須 | 説明 |
|------|:----:|------|
| `--prompt` | - | 画像生成プロンプト。未指定時は対話で確認 |
| `--aspect` | - | アスペクト比（`16:9` / `1:1` / `9:16` / `4:3` / `3:4`、デフォルト `16:9`） |
| `--slug` | - | ファイル名接頭辞。ブログ記事のslugを渡すと紐付けやすい |
| `--filename` | - | 保存ファイル名（例: `thumb.png`）。指定時は `--slug` を無視 |

## 実行フロー

### ステップ1: プロンプトの確認

1. `--prompt` が指定されていない場合、用途（アイキャッチ / SNS投稿 / その他）と画像のイメージをユーザーに確認する
2. ブログ記事のアイキャッチ用途の場合、記事のタイトル・主題から英語ベースのプロンプトを提案する
   - 日本語より英語のプロンプトの方がNanobananaは安定して動作する
   - **aidotters.com のアイキャッチなら、プロンプトを手書きせず `build_featured_image_prompt()` を使う**（サイトのトーンに合わせたブランド指示が入る）:
     ```bash
     uv run python -c "
     from src.utils.image_prompt import build_featured_image_prompt
     print(build_featured_image_prompt(content_type='weekly-ai-news', title='タイトル'))
     "
     ```
   - 手書きする場合もサイトのトーンに合わせる: **白地＋フラットベクターイラスト**、濃紺 `#17325b` / `#1d4e7c` を主役に、中間青 `#6fa3d6` / `#a8cbe8`、ティール `#4fb8a8` / ミント `#8fd8cc`、差し色にイエロー `#f2c94c` / サンド `#f7e2a3`。モチーフは記事内容が伝わる具体物（端末・グラフ・工具・ブロック等）。暗色地・ネオン発光・3D・写実・SF調のHUDは使わない
   - **プロンプトに hex のカラーコードを書かない**。画像モデルは hex を色として解釈せず、端末の画面などに `6FA32D6` のような崩れた文字列として描画する（実測で25枚中9枚）。上の hex は色を確認するための表記であって、プロンプトには色名だけを書く
   - 画像に文字は入れない。特に**新聞モチーフは見出しの "NEWS" を必ず描かせる**ので避ける
3. プロンプトをユーザーに確認してもらう

### ステップ2: アスペクト比の決定

用途別の推奨値:

| 用途 | 推奨 |
|------|------|
| ブログアイキャッチ（WordPress） | `16:9` |
| X（Twitter）投稿 | `16:9` または `1:1` |
| Instagram | `1:1` |
| ショート動画サムネ | `9:16` |

### ステップ3: 画像生成の実行

```bash
uv run python -c "
import asyncio
from src.generators.image import GeminiImageGenerator

gen = GeminiImageGenerator()
path = asyncio.run(gen.generate(
    prompt='''${PROMPT}''',
    aspect_ratio='${ASPECT}',
    slug='${SLUG}' if '${SLUG}' else None,
    filename='${FILENAME}' if '${FILENAME}' else None,
))
print(f'生成完了: {path}')
"
```

保存先はデフォルトで `outputs/images/` 配下。ファイル名は `YYYYMMDD-HHMMSS-{slug}.png` 形式で自動生成される。

### ステップ4: 確認と再生成

1. 生成された画像のパスをユーザーに表示する
2. 画像を確認してもらい、必要に応じてプロンプトを調整して再生成する
3. Nanobananaはプロンプトのニュアンスで結果が変わるため、何度か試行する前提でユーザーに案内する

### ステップ5: 後続処理（任意）

- **WordPress投稿と組み合わせる場合**: 生成した画像はWordPressメディアに別途アップロードする必要がある（現時点では手動）
- **記事ディレクトリに紐付ける場合**: `docs/drafts/<slug>/` 配下に画像をコピーする運用も可能（ただし `outputs/` は `.gitignore` 対象）

## 環境変数

`.env` に以下が必要:

```
GEMINI_API_KEY=your-gemini-api-key
```

Google AI Studio（https://aistudio.google.com/apikey）でキーを取得する。無料枠で `gemini-2.5-flash-image` が利用可能（日次リクエスト上限あり）。

未設定時のエラーメッセージ:
```
画像生成エラー: GEMINI_API_KEY が未設定です。.env または環境変数で設定してください。
```

## 制約・注意事項

- **無料枠の上限**: Google AI Studio の無料枠は日次リクエスト数に上限あり。大量生成時は枠超過に注意
- **セーフティ拒否**: プロンプトによってはコンテンツポリシーで拒否され、画像が返らないことがある。その場合は `レスポンスに画像が含まれていません` エラーになる
- **日本語プロンプト**: 基本的には英語プロンプトの方が品質が安定する。日本語も動作はするが、意図通りにならない場合は英訳して再試行する
- **生成物の管理**: `outputs/` は `.gitignore` 対象。コミットする場合は明示的に別ディレクトリにコピーする

## 使用例

```
# プロンプト指定で一発生成
/generate-image --prompt "A futuristic AI robot reading a newspaper, cinematic lighting, 16:9"

# 記事のアイキャッチ用（slug連携）
/generate-image --prompt "..." --slug 20260419-weekly-ai-news

# Instagram用の正方形画像
/generate-image --prompt "..." --aspect 1:1

# ファイル名を明示
/generate-image --prompt "..." --filename hero.png

# プロンプト未指定で対話から開始
/generate-image
```

## create-blog-post との連携

ブログ記事生成後にアイキャッチを作る場合、create-blog-post のステップ3（レビュー）以降で本スキルを呼び出す運用を推奨する。記事の `slug` を `--slug` に渡しておくと、後から画像と記事の対応付けが追いやすい。
