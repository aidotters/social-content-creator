---
name: publish-to-x
description: 記事の紹介をX（Twitter）に投稿するスキル。docs/posts/やdocs/drafts/配下のMarkdownファイルを指定してX投稿する。「X投稿」「ツイートする」「Xに投稿」などのリクエスト時に使用。/publish-to-x コマンドで呼び出す。
---

# publish-to-x スキル

記事の紹介文をX（Twitter）に投稿する。

## コマンド形式

```
/publish-to-x [<article-path>] [--thread]
```

## 引数

| 引数 | 必須 | 説明 |
|------|:----:|------|
| `<article-path>` | - | 記事ファイルのパス（docs/posts/ または docs/drafts/ 配下） |
| `--thread` | - | スレッド形式で投稿する |

## 実行フロー

### ステップ1: 記事の選択

1. `<article-path>` が指定された場合、そのファイルを読み込む
2. 未指定の場合、`docs/posts/` と `docs/drafts/` の記事一覧を表示してユーザーに選択させる
   ```
   Glob('docs/posts/**/*.md')
   Glob('docs/drafts/**/*.md')
   ```

### ステップ2: 記事の解析

1. 記事ファイルを読み込み、front matter から以下を取得:
   - `title`: 記事タイトル
   - `content_type`: コンテンツタイプ
   - `tags`: タグリスト
   - `wordpress_url`: WordPress投稿URL（docs/posts/ の場合）

### ステップ3: 紹介文の生成

記事の `content_type` に基づいて、以下のテンプレートパターンで紹介文を生成する。

#### コンテンツタイプ別テンプレート

**weekly-ai-news（週刊AIニュース）:**
```
📰 今週のAIニュースまとめを公開しました！

{記事から主要トピック2-3件を箇条書き}

詳しくはブログで👇
{wordpress_url}

#AI #AIニュース #機械学習
```

**paper-review（論文レビュー）:**
```
📄 論文レビューを公開しました

「{論文タイトル}」

{論文の要点を1-2文で要約}

ブログで詳しく解説しています👇
{wordpress_url}

#AI #論文レビュー #MachineLearning
```

**project-intro（プロジェクト紹介）:**
```
🚀 新しいプロジェクトを紹介する記事を公開しました

「{プロジェクト名}」- {一言説明}

{プロジェクトの特徴を1文で}

詳細はこちら👇
{wordpress_url}

#開発 #プログラミング #OSS
```

**汎用テンプレート（その他のcontent_type）:**
```
📝 新しい記事を公開しました

「{記事タイトル}」

{記事の要点を1-2文で要約}

{wordpress_url}

#AI #テック
```

#### テンプレート利用ルール

- テンプレートはあくまで雛形。記事の内容に合わせて自然な文章に調整すること
- **Xの加重文字数で280文字以内**に収めること（URLを含む）
  - 日本語・CJK文字・絵文字 = **2文字**としてカウント
  - URL = **23文字**固定（t.co短縮）
  - ASCII文字 = **1文字**
  - 例：日本語のみの場合は最大140文字、ASCII+日本語混合はさらに短くなる
- `wordpress_url` がない場合（ドラフト記事）はURL部分を省略
- ハッシュタグは記事の `tags` フィールドも参考に調整する

#### ハッシュタグ自動付与ルール

1. **固定タグ**: content_type に基づいて自動付与
   - weekly-ai-news: `#AI #AIニュース`
   - paper-review: `#AI #論文レビュー`
   - project-intro: `#開発 #プログラミング`
   - tool-tips: `#開発ツール #Tips`
   - market-analysis: `#AI #市場分析`
   - ml-practice: `#機械学習 #実践`
2. **記事タグ**: front matter の `tags` から関連性の高い1-2個を `#タグ名` 形式で追加
3. **合計**: ハッシュタグは最大4-5個に抑える

### ステップ4: ユーザー確認

1. 生成した紹介文をユーザーに表示する
2. 投稿形式を確認する:
   - **1ツイート**: 280文字以内の1投稿
   - **スレッド**: 複数ツイートに分けて投稿（`--thread` 指定時はスキップ）
3. ユーザーが紹介文を編集できるようにする
4. 最終確認後、投稿を承認してもらう

### ステップ5: X投稿

```bash
uv run python -c "
import asyncio
from pathlib import Path
from src.publishers.x import XPublisher

pub = XPublisher()
from src.models.blog_post import BlogPost
from datetime import datetime, UTC

post = BlogPost(
    title='${TITLE}',
    content='',
    content_type='${CONTENT_TYPE}',
    slug='${SLUG}',
    created_at=datetime.now(UTC),
    wordpress_url='${WORDPRESS_URL}' if '${WORDPRESS_URL}' else None,
)

# 1ツイート投稿の場合
result = asyncio.run(pub.publish(post, text='''${TWEET_TEXT}'''))

# スレッド投稿の場合
# texts = ['''${TWEET_1}''', '''${TWEET_2}''', ...]
# result = asyncio.run(pub.publish_thread(post, texts))

if result.success:
    print(f'投稿成功: {result.tweet_url}')
else:
    print(f'投稿失敗: {result.error_message}')
"
```

### ステップ6: 投稿後処理

投稿成功時:
- ツイートURLをユーザーに表示する

投稿失敗時:
- エラー内容を表示し、`.env` のOAuth 1.0a認証情報の設定を確認するよう案内する

## 環境変数

`.env` に以下が必要（OAuth 1.0a User Context）:

```
X_API_KEY=your-x-api-key
X_API_SECRET=your-x-api-secret
X_ACCESS_TOKEN=your-x-access-token
X_ACCESS_TOKEN_SECRET=your-x-access-token-secret
```

未設定時のエラーメッセージ:
```
X API認証情報が未設定です: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET。
.envファイルまたは環境変数で設定してください。

X APIのOAuth 1.0aキーは https://developer.x.com/ のDeveloper Portalから取得できます。
```
