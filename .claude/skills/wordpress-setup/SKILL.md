# wordpress-setup スキル

WordPress サイトの初期セットアップを対話型で行うスキルです。Playwright MCP を使用してブラウザ自動化でWordPress管理画面を操作します。

## コマンド形式

```
/wordpress-setup <wp-admin-url>
```

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `<wp-admin-url>` | Yes | WordPress管理画面のURL（例: `https://example.com/wp-admin`） |

## 前提条件

- Playwright MCP が利用可能であること
- WordPress がインストール済みであること
- wp-admin にログイン可能な管理者アカウントがあること

## 実行フロー

### ステップ1: 事前準備・ログイン

1. **ブラウザをリサイズ**する（WordPress管理画面の操作には十分なサイズが必要）
   ```
   browser_resize: width=1280, height=900
   ```

2. **wp-admin にアクセス**する
   ```
   browser_navigate: <wp-admin-url>
   ```

3. **ログイン状態を確認**する
   - ログインページが表示された場合、ユーザーにログイン情報を質問してログインを実行
   - ダッシュボードが表示されれば次のステップへ

### ステップ2: 基本設定

**ユーザーに質問:**
- サイト名（サイトのタイトル）
- キャッチフレーズ

**実行内容:**

1. **設定 > 一般** (`/wp-admin/options-general.php`) にアクセス
2. サイトのタイトル・キャッチフレーズを設定
3. タイムゾーンを `Asia/Tokyo` (UTC+9) に設定
4. 日付形式・時刻形式を日本語向けに設定
5. **設定 > パーマリンク** (`/wp-admin/options-permalink.php`) にアクセス
6. パーマリンク構造を「投稿名」(`/%postname%/`) に設定

### ステップ3: 不要コンテンツ削除

**実行内容:**

1. cookie認証REST APIを使って既存コンテンツを確認
   ```javascript
   // ページ一覧取得
   const pages = await fetch('/wp-json/wp/v2/pages', {
     headers: { 'X-WP-Nonce': nonce }
   }).then(r => r.json());
   ```

2. デフォルトコンテンツを削除:
   - 「Hello world!」投稿
   - 「Sample Page」ページ
   - 「Privacy Policy」ページ（必要に応じて）

3. ユーザーに削除結果を報告

### ステップ4: テーマカスタマイズ

**ユーザーに質問:**
- ブランドカラー（プライマリカラー）
- テーマのスタイルバリエーション（利用可能な選択肢を提示）

**実行内容:**

1. **外観 > エディター** にアクセス
2. スタイルバリエーションを確認・選択
3. ブランドカラーを適用
4. `page.evaluate` でグローバルスタイル設定を更新

### ステップ5: ページ構成作成

**ユーザーに質問:**
- 必要なページ構成（例: ホーム、ブログ、お問い合わせ、プライバシーポリシー等）
- フロントページとして使用するページ
- 投稿ページとして使用するページ

**実行内容:**

1. **cookie認証REST API でページを作成**する（techniques.md 参照）
   ```javascript
   // nonce取得 → ページ作成
   const nonce = await fetch('/wp-admin/admin-ajax.php?action=rest-nonce',
     { credentials: 'same-origin' }).then(r => r.text());

   await fetch('/wp-json/wp/v2/pages', {
     method: 'POST',
     headers: {
       'Content-Type': 'application/json',
       'X-WP-Nonce': nonce
     },
     body: JSON.stringify({
       title: 'ページタイトル',
       status: 'publish',
       content: '<!-- wp:paragraph --><p>コンテンツ</p><!-- /wp:paragraph -->'
     })
   });
   ```

2. **表示設定を変更**する (`/wp-admin/options-reading.php`)
   - フロントページの表示: 「固定ページ」を選択
   - フロントページ・投稿ページを指定

### ステップ6: カテゴリ・メニュー設定

**ユーザーに質問:**
- カテゴリ構成（例: AI技術、ツール紹介、論文解説 等）
- ナビゲーションメニューに含める項目

**実行内容:**

1. **REST API でカテゴリを作成**
   ```javascript
   await fetch('/wp-json/wp/v2/categories', {
     method: 'POST',
     headers: {
       'Content-Type': 'application/json',
       'X-WP-Nonce': nonce
     },
     body: JSON.stringify({ name: 'カテゴリ名', slug: 'category-slug' })
   });
   ```

2. **デフォルトの「未分類」カテゴリをリネーム**（必要に応じて）

3. **ナビゲーションメニューを更新**する
   - REST API で `wp_navigation` ポストタイプを取得・更新
   ```javascript
   // ナビゲーション取得
   const navs = await fetch('/wp-json/wp/v2/navigation', {
     headers: { 'X-WP-Nonce': nonce }
   }).then(r => r.json());

   // ナビゲーション更新（ブロックマークアップ形式）
   await fetch(`/wp-json/wp/v2/navigation/${navId}`, {
     method: 'PUT',
     headers: {
       'Content-Type': 'application/json',
       'X-WP-Nonce': nonce
     },
     body: JSON.stringify({
       content: '<!-- wp:navigation-link {"label":"ホーム","url":"/"} /-->...'
     })
   });
   ```

### ステップ7: プラグイン導入

**ユーザーに質問:**
- 導入するプラグイン（推奨プラグインリストを提示）

**推奨プラグインリスト:**
- WP Multibyte Patch（日本語対応）
- Yoast SEO / All in One SEO（SEO対策）
- Contact Form 7（お問い合わせフォーム）
- UpdraftPlus（バックアップ）
- Wordfence Security（セキュリティ）
- WP Super Cache / W3 Total Cache（キャッシュ）
- その他ユーザー指定のプラグイン

**実行内容:**

1. **プラグインページにアクセス** (`/wp-admin/plugin-install.php`)
2. プラグインを検索
3. **`page.evaluate` でインストールURLを取得**して直接ナビゲート
   ```javascript
   // プラグインのインストールURLを取得
   const installLinks = document.querySelectorAll('.install-now');
   const targetPlugin = Array.from(installLinks).find(
     el => el.getAttribute('data-slug') === 'plugin-slug'
   );
   const installUrl = targetPlugin?.getAttribute('href');
   ```
4. インストールURL に直接ナビゲートしてインストール実行
5. 有効化リンクを取得して有効化

### ステップ8: REST API自動化設定

**実行内容:**

1. **アプリケーションパスワードを発行**する
   - `/wp-admin/profile.php` にアクセス
   - 「アプリケーションパスワード」セクションでパスワードを生成
   - または REST API 経由で発行:
   ```javascript
   await fetch('/wp-json/wp/v2/users/me/application-passwords', {
     method: 'POST',
     headers: {
       'Content-Type': 'application/json',
       'X-WP-Nonce': nonce
     },
     body: JSON.stringify({ name: 'Social Content Creator' })
   });
   ```

2. **REST API の動作確認**
   ```bash
   curl -u "username:application-password" https://example.com/wp-json/wp/v2/posts?per_page=1
   ```

3. **`.env` ファイルに認証情報を保存**（ユーザーに確認の上）
   ```
   WP_URL=https://example.com
   WP_USERNAME=admin
   WP_APP_PASSWORD=xxxx xxxx xxxx xxxx
   ```

4. 動作確認結果をユーザーに報告

## 完了時

全ステップ完了後、`checklist.md` に基づいてセットアップ状況のサマリーを表示する。

## 注意事項

- 各ステップで必ずユーザーに確認を取ってから実行する
- エラーが発生した場合は `techniques.md` のトラブルシューティングを参照
- WordPress管理画面のスナップショットが大きすぎる場合は `page.evaluate` でDOM直接操作に切り替える
- プロジェクト固有のコード（WordPressPublisher等）には依存しない汎用スキル
