---
date: '2026-02-16'
slug: authlib-oauth1-json-body-bug
status: draft
title: 【Python】authlib × httpx で X API v2 に投稿できない？OAuth1Auth が JSON body を消すバグと回避策
type: tool-tips
tags:
  - Python
  - authlib
  - httpx
  - X API
  - OAuth1
  - トラブルシューティング
---

## はじめに

PythonでX（旧Twitter）API v2にツイートを投稿する仕組みを構築した際、`authlib` の `OAuth1Auth` と `httpx` の組み合わせでハマったポイントをまとめます。同じ構成を採用している方の参考になれば幸いです。

## 環境

- Python 3.12
- authlib 1.6.8
- httpx 0.28.x
- X API v2（`POST /2/tweets`）

## 発生した問題

### 症状

`httpx` で `json={"text": "ツイート内容"}` を指定してX API v2にPOSTすると、以下のエラーが返される。

```json
{
  "errors": [{"message": "Please include either text or media in your Tweet."}],
  "title": "Invalid Request",
  "detail": "One or more parameters to your request was invalid.",
  "type": "https://api.twitter.com/2/problems/invalid-request"
}
```

コード自体は非常にシンプルで、一見すると問題がなさそうに見えます。

```python
import httpx
from authlib.integrations.httpx_client import OAuth1Auth

auth = OAuth1Auth(
    client_id="...",
    client_secret="...",
    token="...",
    token_secret="...",
)

async with httpx.AsyncClient() as client:
    response = await client.post(
        "https://api.x.com/2/tweets",
        json={"text": "Hello, World!"},
        auth=auth,
    )
```

APIは「テキストかメディアを含めてください」と言っていますが、`json=` パラメータで `text` フィールドは確かに指定しています。では何が起きているのでしょうか？

## 原因の特定

### authlib の `ClientAuth.prepare()` メソッド

authlib の OAuth1Auth は、httpx の認証フロー（`auth_flow`）の中で `prepare()` メソッドを呼び出し、OAuth署名をリクエストに付与します。

問題は `prepare()` メソッド内のこのロジックにあります：

```python
def prepare(self, method, uri, headers, body):
    content_type = to_native(headers.get("Content-Type", ""))

    if CONTENT_TYPE_FORM_URLENCODED in content_type:
        # フォームエンコードの場合：bodyを署名に含め、bodyを保持 ✅
        uri, headers, body = self.sign(method, uri, headers, body)
    elif self.force_include_body:
        # bodyを署名に含める（カスタム用途）
        uri, headers, body = self.sign(method, uri, headers, body)
    else:
        # それ以外：bodyを署名に含めない ← ここが問題！
        uri, headers, _ = self.sign(method, uri, headers, b"")
        body = b""  # 🚨 bodyが空にリセットされる！

    return uri, headers, body
```

OAuth 1.0aの仕様では、`application/json` のbodyは署名ベース文字列に含めないのが正しい動作です。**しかし**、authlib は署名計算からbodyを除外するだけでなく、**body自体も空の `b""` にリセットしてしまいます**。

その結果、httpx が実際にサーバーに送信するリクエストのbodyが空になり、X APIは「テキストが含まれていない」と判断してエラーを返していたのです。

### `force_include_body=True` は解決策にならない

最初に試みたのは `force_include_body=True` の設定です。

```python
auth = OAuth1Auth(
    client_id="...",
    client_secret="...",
    token="...",
    token_secret="...",
    force_include_body=True,  # bodyを保持するために設定
)
```

これでbodyは保持されますが、**JSON bodyが OAuth署名のベース文字列に含まれてしまいます**。OAuth 1.0aの仕様ではJSON bodyは署名に含めるべきではないため、署名が不正になり、今度は **403 Forbidden** が返ってきます。

## 解決策

`OAuth1Auth` をサブクラス化し、署名計算後に元のbodyを復元するようにしました。

```python
import typing
import httpx
from authlib.integrations.httpx_client import OAuth1Auth
from authlib.integrations.httpx_client.utils import build_request


class OAuth1AuthJsonFix(OAuth1Auth):
    """authlib の OAuth1Auth が JSON body を破棄するバグの回避策。

    OAuth 1.0a の仕様に従い、JSON body は署名に含めず、
    かつ元の body を保持してリクエストに含める。
    """

    def auth_flow(
        self, request: httpx.Request
    ) -> typing.Generator[httpx.Request, httpx.Response, None]:
        original_body = request.content
        url, headers, body = self.prepare(
            request.method, str(request.url), request.headers, request.content
        )
        # prepare() が body を空にした場合、元の body を復元する
        if not body and original_body:
            body = original_body
        headers["Content-Length"] = str(len(body))
        yield build_request(
            url=url, headers=headers, body=body, initial_request=request
        )
```

使い方は `OAuth1Auth` と同じです：

```python
auth = OAuth1AuthJsonFix(
    client_id="...",
    client_secret="...",
    token="...",
    token_secret="...",
)

async with httpx.AsyncClient() as client:
    response = await client.post(
        "https://api.x.com/2/tweets",
        json={"text": "Hello, World!"},
        auth=auth,
    )
    print(response.status_code)  # 201 ✅
```

## おまけ：X APIの重複コンテンツ検知

デバッグ中にもう一つ遭遇した挙動として、X APIの**重複コンテンツ検知**があります。

同じ内容のツイートを短時間で再投稿しようとすると、以下のエラーが返ります：

```json
{
  "detail": "You are not allowed to create a Tweet with duplicate content.",
  "status": 403
}
```

HTTPステータスコードが **403** なので、認証エラーと混同しやすいです。エラーハンドリングでは `detail` フィールドのメッセージも確認するようにしましょう。

## まとめ

| 問題 | 原因 | 解決策 |
|------|------|--------|
| `json=` で送信したbodyが消える | authlib `prepare()` がJSON bodyを `b""` にリセット | `OAuth1Auth` をサブクラス化してbody復元 |
| `force_include_body=True` で403 | JSON bodyがOAuth署名に含まれてしまう | 使わない。サブクラスで対応 |
| 同一内容の再投稿で403 | X APIの重複コンテンツ検知 | テキストを変更して再投稿 |

authlib は OAuth フローの実装として広く使われていますが、JSON bodyを扱うAPIとの組み合わせでは今回のような落とし穴があります。X API v2のように `application/json` でのPOSTが必須のAPIでは、この回避策が必要になるケースがあるので注意してください。

## 参考リンク

- [authlib GitHub リポジトリ](https://github.com/lepture/authlib)
- [X API v2 ドキュメント - POST /2/tweets](https://developer.x.com/en/docs/x-api/tweets/manage-tweets/api-reference/post-tweets)
- [OAuth 1.0a 仕様 (RFC 5849)](https://datatracker.ietf.org/doc/html/rfc5849)
