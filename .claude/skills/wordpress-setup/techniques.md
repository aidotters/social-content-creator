# Playwright × WordPress 操作テクニック集

WordPress管理画面をPlaywright MCPで自動化する際のテクニックと注意点。

## 1. cookie認証REST API

WordPress管理画面にログイン済みのブラウザセッションを使って、cookie認証でREST APIを呼び出す方法。

### nonce の取得

```javascript
// browser_evaluate で実行
const nonce = await fetch('/wp-admin/admin-ajax.php?action=rest-nonce', {
  credentials: 'same-origin'
}).then(r => r.text());
```

### REST API 呼び出しパターン

```javascript
// GET: データ取得
const data = await fetch('/wp-json/wp/v2/pages', {
  headers: { 'X-WP-Nonce': nonce },
  credentials: 'same-origin'
}).then(r => r.json());

// POST: データ作成
const result = await fetch('/wp-json/wp/v2/pages', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-WP-Nonce': nonce
  },
  credentials: 'same-origin',
  body: JSON.stringify({
    title: 'ページタイトル',
    status: 'publish',
    content: '<!-- wp:paragraph --><p>内容</p><!-- /wp:paragraph -->'
  })
}).then(r => r.json());

// PUT: データ更新
await fetch(`/wp-json/wp/v2/posts/${postId}`, {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    'X-WP-Nonce': nonce
  },
  credentials: 'same-origin',
  body: JSON.stringify({ title: '新しいタイトル' })
});

// DELETE: データ削除（ゴミ箱へ）
await fetch(`/wp-json/wp/v2/posts/${postId}`, {
  method: 'DELETE',
  headers: { 'X-WP-Nonce': nonce },
  credentials: 'same-origin'
});

// DELETE: 完全削除
await fetch(`/wp-json/wp/v2/posts/${postId}?force=true`, {
  method: 'DELETE',
  headers: { 'X-WP-Nonce': nonce },
  credentials: 'same-origin'
});
```

### nonce + 複数操作のまとめ実行

```javascript
// browser_evaluate で nonce取得 → 複数API呼び出しを一括実行
const nonce = await fetch('/wp-admin/admin-ajax.php?action=rest-nonce', {
  credentials: 'same-origin'
}).then(r => r.text());

const headers = {
  'Content-Type': 'application/json',
  'X-WP-Nonce': nonce
};

const categories = ['AI技術', 'ツール紹介', '論文解説'];
const results = [];

for (const name of categories) {
  const cat = await fetch('/wp-json/wp/v2/categories', {
    method: 'POST',
    headers,
    credentials: 'same-origin',
    body: JSON.stringify({ name, slug: name.toLowerCase() })
  }).then(r => r.json());
  results.push({ name, id: cat.id });
}

return JSON.stringify(results);
```

## 2. プラグインインストール

WordPress管理画面からプラグインをインストールする方法。UIの「今すぐインストール」ボタンからURLを取得して直接ナビゲートする。

### 手順

1. プラグイン検索ページにアクセス
   ```
   browser_navigate: /wp-admin/plugin-install.php?s=plugin-name&tab=search&type=term
   ```

2. `page.evaluate` でインストールURLを取得
   ```javascript
   const links = document.querySelectorAll('.install-now');
   const target = Array.from(links).find(
     el => el.getAttribute('data-slug') === 'target-plugin-slug'
   );
   return target ? target.getAttribute('href') : null;
   ```

3. 取得したURLに直接ナビゲート
   ```
   browser_navigate: <install-url>
   ```

4. インストール完了後、有効化リンクを取得して有効化
   ```javascript
   const activateLink = document.querySelector('.button-primary');
   return activateLink ? activateLink.getAttribute('href') : null;
   ```

### 注意点

- `browser_click` でインストールボタンを押すとAjaxで処理されるが、完了検知が難しい
- URLに直接ナビゲートする方が確実で、完了画面から有効化リンクも取得しやすい
- プラグインのスラッグは WordPress.org のURL（例: `wordpress.org/plugins/wp-multibyte-patch/`）から確認

## 3. ナビゲーションブロック編集

WordPress のブロックテーマ（FSE）ではナビゲーションメニューが `wp_navigation` ポストタイプとして管理される。

### ナビゲーション取得

```javascript
const navs = await fetch('/wp-json/wp/v2/navigation', {
  headers: { 'X-WP-Nonce': nonce },
  credentials: 'same-origin'
}).then(r => r.json());

// navs[0].id でメインナビゲーションのIDを取得
// navs[0].content.raw で現在のブロックマークアップを確認
```

### ナビゲーション更新

```javascript
// ブロックマークアップ形式でナビゲーションを構成
const content = [
  '<!-- wp:navigation-link {"label":"ホーム","url":"/","kind":"custom","isTopLevelLink":true} /-->',
  '<!-- wp:navigation-link {"label":"ブログ","url":"/blog/","kind":"custom","isTopLevelLink":true} /-->',
  '<!-- wp:navigation-link {"label":"お問い合わせ","url":"/contact/","kind":"custom","isTopLevelLink":true} /-->'
].join('\n');

await fetch(`/wp-json/wp/v2/navigation/${navId}`, {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    'X-WP-Nonce': nonce
  },
  credentials: 'same-origin',
  body: JSON.stringify({ content })
});
```

### ページリンク vs カスタムリンク

```
<!-- ページリンク（ページIDで参照） -->
<!-- wp:navigation-link {"label":"About","type":"page","id":123,"url":"/about/","kind":"post-type"} /-->

<!-- カスタムリンク（URL直接指定） -->
<!-- wp:navigation-link {"label":"外部リンク","url":"https://example.com","kind":"custom"} /-->
```

## 4. アプリケーションパスワード

REST APIの外部認証用にアプリケーションパスワードを発行する。

### REST API経由で発行

```javascript
const result = await fetch('/wp-json/wp/v2/users/me/application-passwords', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-WP-Nonce': nonce
  },
  credentials: 'same-origin',
  body: JSON.stringify({ name: 'App Name' })
}).then(r => r.json());

// result.password にアプリケーションパスワードが含まれる（この1回のみ表示）
return JSON.stringify({ password: result.password, uuid: result.uuid });
```

### 動作確認

```bash
# Basic認証でREST APIをテスト
curl -u "username:xxxx xxxx xxxx xxxx" https://example.com/wp-json/wp/v2/posts?per_page=1
```

## 5. トラブルシューティング

### スナップショットが大きすぎる

WordPress管理画面のスナップショット（`browser_snapshot`）は非常に大きくなることがある。

**対策:**
- `browser_snapshot` の代わりに `page.evaluate` でDOM要素を直接取得・操作
- 必要な情報だけを `page.evaluate` で抽出して返す
- フォーム操作は `browser_fill_form` や `browser_click` で個別に実行

### ブラウザサイズ

WordPress管理画面はレスポンシブ対応しており、小さいウィンドウではメニューが折りたたまれる。

**対策:**
```
browser_resize: width=1280, height=900
```
- 最低でも1280x900以上に設定
- 設定ページやプラグインページは高さが必要な場合がある

### REST APIが403エラーを返す

- nonceが期限切れの可能性がある → nonceを再取得
- ログインセッションが切れている → 再ログイン
- 権限不足 → 管理者アカウントでログインしているか確認

### プラグインインストールが失敗する

- ファイルシステムの権限問題の可能性
- FTP情報を求められる場合がある → `wp-config.php` に `define('FS_METHOD', 'direct');` を追加
- サーバーのPHPメモリ制限に引っかかる場合がある

### ナビゲーション更新が反映されない

- ブロックテーマでない場合、`wp_navigation` は使えない → 従来のメニュー管理を使用
- キャッシュプラグインが有効な場合、キャッシュクリアが必要
