# OAuth 403 構造修正の敵対検証

日付は 2026-09-01 である。
実装報告は信用していない。
コード、`git diff`、自分で回した unittest、inline の捨て確認を根拠にする。
コミットしていない。
修正はしていない。
実 OAuth トークンは書いていない。

## Verdict

**PASS**

成功条件 10 件は、コードとテストの両方から成立する。
実装者が直すべき欠陥は、この 10 件の範囲には残っていない。
追加の狩りで見つかったのは、判定を覆す欠陥ではなく、スコープ外の dirty working tree と、実装者が残リスクとして既に書いた Semantica 内部リトライである。

## Checklist

| # | 条件 | 判定 | 根拠 |
| --- | --- | --- | --- |
| 1 | `REFRESH_SKEW_SECONDS >= 3600` | **PASS** | `xai_oauth.py:18` は `REFRESH_SKEW_SECONDS = 3600`。HEAD は 120。inline 確認でも `SKEW 3600`。失効 3599 秒先は True、3601 秒先は False。 |
| 2 | 非 JWT / parse 失敗 / `exp` 欠落 → `access_token_needs_refresh` が True | **PASS** | `xai_oauth.py:76-90`。`.` 無し、`len(parts) < 2`、`exp` 非数値、`except` がすべて True。テスト `test_opaque_non_jwt_needs_refresh` / `test_unparseable_jwt_needs_refresh` / `test_jwt_missing_exp_needs_refresh`。 |
| 3 | refresh 全滅 → `None`。期限切れ `creds[0]["access"]` を返さない。次 candidate を試す | **PASS** | `xai_oauth.py:269-286`。refresh 失敗は `continue`、ファイル末尾も `continue`、関数末尾は `return None`。`return creds[0]["access"]` はリポジトリに無い。`test_returns_none_when_refresh_fails` と `test_skips_failed_file_and_tries_next_candidate`。 |
| 4 | 抽出 403 系で `force_refresh`、`XAI_API_KEY` 更新、その知識点を再試行。パターン NER に落ちない | **PASS** | `extract.py:66-81` と `_extract_one_item`。NER と関係の両方が `_call_llm_with_auth_retry`。再試行は 1 回。失敗は `LLMExtractionError`。`test_auth_error_refreshes_and_retries_without_pattern_ner`、`test_relation_auth_error_refreshes_and_retries`、`test_retry_still_auth_fails_raises`。 |
| 5 | 冊内並列でも refresh はロック一本 | **PASS** | `extract.py:24` の `_oauth_refresh_lock`。`_refresh_xai_access_token` が resolve と env 更新をロック内で行う。`test_concurrent_refresh_is_serialized_and_later_items_see_new_key` が `refresh_max == 1`。 |
| 6 | `read_books.py` は変えない | **PASS** | `git diff --stat -- read_books.py` は空。 |
| 7 | リポ `.venv` へ semantica を入れない。Hermes 作業記録に書かない。51 冊ライブを回さない。優先キューを殺さない | **PASS** | `.venv` の `import semantica` は `ModuleNotFoundError`。Hermes `semantica-knowledge-work.json` の mtime は Aug 30。`run_semantica_resume_queue.sh`（pid 1225704、Aug31 起動）が生存。今回の unittest はモックである。 |
| 8 | テストはモック。ライブ xAI は無い | **PASS** | `refresh_tokens` と `resolve_access_token` を patch。抽出テストは `extract_ents` / `extract_rels` を差し替え。実トークンエンドポイントは叩いていない。 |
| 9 | `test_keeps_expired_token_when_refresh_fails` を `None` 期待へ直す | **PASS** | 旧名はリポジトリに 0 件。`test_returns_none_when_refresh_fails` が `self.assertIsNone(resolved)`。 |
| 10 | fresh JWT テストは `exp ≈ now+7200` | **PASS** | `test_fresh_jwt_does_not_need_refresh` と `test_reads_valid_token_from_auth_json` と `test_prefers_fresh_pool_token_over_expired_provider` が `+ 7200`。 |

## Evidence

### 1. skew

```18:18:xai_oauth.py
REFRESH_SKEW_SECONDS = 3600
```

`git diff` は `120` から `3600` への 1 行置換である。

### 2. non-JWT / parse / missing exp

```75:90:xai_oauth.py
def access_token_needs_refresh(access_token: str, *, skew_seconds: int = REFRESH_SKEW_SECONDS) -> bool:
    if not isinstance(access_token, str) or "." not in access_token:
        return True
    try:
        parts = access_token.split(".")
        if len(parts) < 2:
            return True
        ...
        if not isinstance(exp, (int, float)):
            return True
        return float(exp) <= time.time() + max(0, int(skew_seconds))
    except Exception:
        return True
```

HEAD はこれらの分岐が `return False` だった。
実装報告の「更新不要にしない」は、この差分と一致する。

### 3. refresh 全滅は None。次ファイルへ

```265:286:xai_oauth.py
        if not force_refresh:
            for cred in creds:
                if not access_token_needs_refresh(cred["access"]):
                    return cred["access"]
        for cred in creds:
            try:
                payload = refresh_tokens(...)
            except XaiOAuthError:
                continue
            persist_tokens(...)
            return payload["access_token"]
        continue
    return None
```

HEAD は `if force_refresh: return None` のあと `return creds[0]["access"]` だった。
その return は消えている。

opaque access に `refresh_token` が無い場合、`iter_credentials` は `access and refresh` が揃わないので creds に入れない。
そのファイルは `if not creds: continue` でスキップする。
期限切れ leftover としても opaque としても返さない。
inline 確認: `opaque_no_refresh_none None`、`opaque_refresh_fail_none None`。

### 4. extract 403 リトライ

```66:81:book_semantica/extract.py
def _call_llm_with_auth_retry(fn, *args, fail_label: str, config):
    kwargs = _extract_llm_kwargs(config)
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        if not _is_auth_error(exc):
            raise LLMExtractionError(f"{fail_label}: {exc}") from exc
        token = _refresh_xai_access_token()
        if not token:
            raise LLMExtractionError(f"{fail_label}: {exc}") from exc
        retry_kwargs = _extract_llm_kwargs(config)
        retry_kwargs["api_key"] = token
        try:
            return fn(*args, **retry_kwargs)
        except Exception as retry_exc:
            raise LLMExtractionError(f"{fail_label}: {retry_exc}") from retry_exc
```

`_is_auth_error` は `unauthenticated`、`bad-credentials`、`invalid_api_key`、`unauthorized`、`403` を見る。
`read_books._is_auth_error` より `403` を足している。
認証エラー以外は即 `LLMExtractionError` であり、パターン NER 関数は呼ばない。

再試行は except の内側に 1 回だけある。
再試行も認証エラーならまた `LLMExtractionError` であり、ループしない。

NER と関係はどちらもこの関数を通る（`extract.py:175-192`）。

### 5. lock

```58:63:book_semantica/extract.py
def _refresh_xai_access_token() -> str | None:
    with _oauth_refresh_lock:
        token = xai_oauth.resolve_access_token(force_refresh=True)
        if token:
            os.environ["XAI_API_KEY"] = token
        return token
```

ロックは refresh の直列化であり、成功後の LLM 再呼び出しはロックの外である。
基準 5 の「一度に一本」は満たす。
2 本が両方 403 のとき、後着は古い key で再試行しない。
後着もロック内で `force_refresh=True` し、戻り値を `retry_kwargs["api_key"]` に書く。
合体（1 回の refresh を共有）はしていない。
2 回目の force_refresh は無駄になりうるが、古い key の再利用ではない。

### 6 / 7 / provider

`book_semantica/xai_provider.py` の `git diff --stat` は空である。
実装報告の「変えなかった」は正しい。

Semantica の `ProviderPool.get` は name と kwargs（`api_key` を含む）でキーを作る。
再試行で新しい `api_key` を渡すと、プールは古いクライアントを返さない。
この点は実装報告の説明と Semantica 0.6.5 のソースが一致する。

## Extra hunts

| 狩り | 判定 | 所見 |
| --- | --- | --- |
| 2 スレッド 403、ロック保持中に 2 本目が古い key で再試行するか | しない | 再試行は refresh の戻り値を `api_key` に固定する。最初の呼び出しは古い key のまま 403 するが、それは仕様である。 |
| リトライ 1 回 vs 無限 | 1 回 | 内側 `try` は 1 段。`test_retry_still_auth_fails_raises` は呼び出し 2 回で止まる。 |
| 関係抽出の認証エラー | 両方 | NER と関係が同じ `_call_llm_with_auth_retry`。関係専用テストあり。 |
| env 更新後も Semantica が死んだクライアントを持つか | 持たない（キーがプールに入る） | `providers.py` の pool key は全 kwargs。`api_key` が変われば別インスタンス。 |
| opaque で refresh 無しでも access を「有効」として返すか | 返さない | creds に入らない。`resolve_access_token` は `None`。基準 3 の精神は満たす。リポジトリ側にこのケースの unittest は無い。 |
| 旧挙動（skew 120、期限切れを返す）をまだ固定するテスト | 無し | `test_keeps_expired_*` は 0 件。fresh 系は +7200。`test_disable_env_skips_oauth` と `CreateClientOAuthTests` はまだ `+ 3600` だが、前者は disable、後者は `resolve_access_token` を patch しており、skew 判定を固定していない。 |
| 禁止ファイルを変えたか | 作業ツリーに混入あり | OAuth 許可集合以外で dirty なのは `scripts/run_semantica_newest_queue.sh`（`FORCE=1` で `--force`）。OAuth 修正とは無関係。実装報告は触れていない。優先 11 冊キュー本体（`run_semantica_resume_queue.sh`）は生きている。`book_analysis/semantica/**` も大量に dirty だが、走っているキューの成果物である。 |
| トークン漏洩 | 見つからない | テストは `opaque-provider-access`、`new-access-token`、自前の fake JWT（`alg: none`）だけ。docs に実トークンは無い。 |
| Semantica 内部リトライ | 残リスク（FAIL ではない） | `generate_structured` は同じ provider で最大 3 回、2s/4s 待ってから例外にする。外側の 403 リトライの前に、切れた key を最大 3 回叩く。実装報告の残リスクと同じ。基準 4 の「その知識点をもう一度」は外側で満たす。 |
| HEAD の抽出は直列だった | スコープ追加 | HEAD の `extract.py` に `ThreadPoolExecutor` は無い。今回の差分で冊内並列を足し、同時にロックを入れた。基準 5 は新しい並列の上で成立する。 |

`tests/test_book_semantica_extract.py` の 403 テストは `extract_ents` を直接差し替えている。
`kwargs["api_key"]` は `del kwargs` しており、関数引数としての差し替えは assert していない。
コードは `retry_kwargs["api_key"] = token` を書く。
テストの穴であり、コード欠陥ではない。

## Unittest stdout

リポ `.venv`:

```
.venv/bin/python -m unittest tests.test_xai_oauth tests.test_book_semantica_extract tests.test_book_semantica_batch tests.test_book_semantica_load -q
warning: The `fitz` API is deprecated and will be removed in future. Use `import pymupdf` instead.
----------------------------------------------------------------------
Ran 68 tests in 2.587s
OK
REPO_VENV_EXIT=0
```

Semantica venv:

```
PYTHONPATH=/opt/AI-reads-books-page-by-page \
  /var/lib/happy/.local/share/semantica/venv/bin/python -m unittest \
  tests.test_book_semantica_extract tests.test_book_semantica_pipeline -q
----------------------------------------------------------------------
Ran 16 tests in 27.098s
OK
SEMANTICA_VENV_EXIT=0
```

失敗 0、エラー 0。
実装報告の 68+16 は再現した。
Semantica venv 側は pipeline が Semantica の進捗ログを stderr に大量に出す。
集計行は上の 16 OK である。

inline（リポジトリ外、実トークン無し）:

```
PASS opaque
PASS expired
PASS fresh7200
PASS skew3599
PASS skew3601
PASS opaque_no_refresh_none None
PASS opaque_refresh_fail_none None
SKEW 3600
FAILS []
```

## git

OAuth 関連（許可ファイルと、混入したキュー脚本）:

```
 M book_semantica/extract.py
 M docs/usage/13-semantica-books.md
 M scripts/run_semantica_newest_queue.sh
 M tests/test_xai_oauth.py
 M xai_oauth.py
?? docs/plans/2026-09-01-oauth-403-fix-report.md
?? tests/test_book_semantica_extract.py
```

```
 book_semantica/extract.py             | 193 +++++++++++++++++++++++++++-------
 docs/usage/13-semantica-books.md      |   4 +
 scripts/run_semantica_newest_queue.sh |  23 ++--
 tests/test_xai_oauth.py               |  50 ++++++++-
 xai_oauth.py                          |  14 ++-
 5 files changed, 223 insertions(+), 61 deletions(-)
```

`tests/test_book_semantica_extract.py` は untracked のため `--stat` に出ない。
`read_books.py` と `book_semantica/xai_provider.py` は差分 0。
コミットは無い。
`git status --short` 全体は `book_analysis/semantica/**` のキュー成果物で埋まっている。
それはこの修正の差分ではない。

## Remaining defects

この 10 条件について、実装者が直すべき欠陥は無い。

作業ツリーの掃除（この検証の FAIL ではない）:

- `scripts/run_semantica_newest_queue.sh` の `FORCE` 変更は OAuth 許可集合の外である。OAuth コミットに混ぜるな。
- `book_analysis/semantica/**` は走っている優先キューの成果であり、OAuth コミットに混ぜるな。
