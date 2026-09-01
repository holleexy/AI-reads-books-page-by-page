# OAuth 403 構造修正の実装報告

日付は 2026-09-01 である。
コミットしていない。push していない。
ライブ xAI は呼んでいない。優先11冊のキューは止めていない。
トークン文字列は書いていない。ライブ `auth.json` は触っていない。

## 何を変えたか

`xai_oauth.py` の `REFRESH_SKEW_SECONDS` を 120 から 3600 にした。
失効まで1時間を切った JWT は、起動時に refresh する。

`access_token_needs_refresh` は、`.` が無い文字列、パース失敗、`exp` 欠落を「更新不要」にしない。
いずれも True を返す。

`resolve_access_token` は、ある auth ファイルの refresh が全部失敗したとき、期限切れの `creds[0]["access"]` を返さない。
そのファイルは `None` 相当で次の candidate へ進む。全部だめなら `None` である。

`book_semantica/extract.py` は、NER と関係 LLM が認証エラー（HTTP 403、`unauthenticated`、`bad-credentials` など、`read_books._is_auth_error` と同じ系統）を見たら、`xai_oauth.resolve_access_token(force_refresh=True)` する。
取れたトークンがあれば `os.environ["XAI_API_KEY"]` に書き、その知識点だけもう一度 LLM を呼ぶ。
英語のパターン NER には落ちない。
refresh が `None`、またはやり直しでも認証エラーなら、従来どおり `LLMExtractionError` を上げる。

冊内同時実行（既定2）では refresh を `threading.Lock` で一本化する。
更新後の呼び出しは、新しい `XAI_API_KEY` を `api_key` として渡す。
Semantica の `create_provider` は `api_key` をプールのキーに含むので、古いクライアントを再利用しない。
`book_semantica/xai_provider.py` は変えなかった。

## テスト

リポ `.venv`:

```
.venv/bin/python -m unittest tests.test_xai_oauth tests.test_book_semantica_extract tests.test_book_semantica_batch tests.test_book_semantica_load -q
Ran 68 tests in 1.646s
OK
```

Semantica venv:

```
PYTHONPATH=/opt/AI-reads-books-page-by-page \
  /var/lib/happy/.local/share/semantica/venv/bin/python -m unittest \
  tests.test_book_semantica_extract tests.test_book_semantica_pipeline -q
Ran 16 tests in 22.110s
OK
```

失敗 0、エラー 0 である。

## 残るリスク

起動スクリプトは、親環境に `XAI_API_KEY` があると OAuth を見ない。
今回の抽出リトライは途中の 403 で上書きするが、起動時点の固定キーそのものは消していない。

チャンクが1時間を超えると、skew だけでは足りない。
その場合は抽出中の 403 リトライが拾う想定である。

Semantica 側の LLM 関数は、例外を上げる前に同じキーで内部リトライすることがある。
その間は切れたキーを叩きうる。
