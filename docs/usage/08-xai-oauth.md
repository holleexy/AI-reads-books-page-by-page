# xAI OAuth

xAI の Grok は、コンソールの API キーだけでなく、SuperGrok / X Premium+ の OAuth でも呼べる。
このプロジェクトは Hermes が `auth.json` に保存したトークンを Bearer にして `https://api.x.ai/v1/chat/completions` を使う。

## いつ使われるか

`create_client()` の順は次である。

1. `XAI_API_KEY`
2. Hermes の xAI OAuth（期限切れなら refresh）
3. `CURSOR_API_KEY`

OAuth が取れれば Cursor Agent SDK より速い。ページあたり十数秒かかる Cursor 経路は最後の控えである。

## トークンの場所

値はガイドに書かない。ファイルパスだけ示す。

| 優先 | 場所 |
| --- | --- |
| 明示 | `XAI_OAUTH_AUTH_JSON` が指す `auth.json` |
| Hermes ホーム | `$HERMES_HOME/auth.json` |
| 既定探索 | `~/.hermes/auth.json` |
| このマシン | `/opt/hermes-cli/.hermes/auth.json` |

store の形は次のどれでも読む。期限の残っている JWT を優先する。

- `providers.xai-oauth.tokens`
- Hermes のネスト `providers.xai-oauth.tokens.tokens`
- `credential_pool.xai-oauth[]`（Hermes が refresh した実体はこちらに残ることが多い）

## 無効化

```bash
XAI_DISABLE_OAUTH=1 ./run.sh smoke_test.py
```

refresh 先は `https` かつ `x.ai` / `*.x.ai` だけを許す。
OAuth が 403 になるときは契約プランが API を許していないことがある。そのときは `XAI_API_KEY` か Cursor へ落とす。
