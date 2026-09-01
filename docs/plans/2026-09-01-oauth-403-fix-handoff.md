# OAuth 403 修正 handoff

日付は 2026-09-01 である。
オーケストレーターがサブエージェントへ委譲する。
実装はコミットしない。push しない。
51 冊のライブ LLM は回さない。
優先11冊のキューは止めない。認証ファイルの中身（トークン）はログに出さない。

判断の根拠は [OAuth 403 は偶発ではなく構造](2026-09-01-oauth-403-structural.md) である。

## ゴール

Semantica 下流の抽出が、OAuth access の寿命切れでチャンクごと死なないようにする。
本読み本体 `read_books.py` の 403 → `force_refresh` → リトライと同じ役割を、冊グラフ抽出に足す。
起動時の「まだ使える」判定を、1チャンクの長さに合わせる。

## 成功条件

1. `REFRESH_SKEW_SECONDS` が 3600 以上である。失効まで1時間を切った JWT は起動時に refresh する。
2. JWT でない access は「更新不要」にしない。`access_token_needs_refresh` は True を返す。
3. ある auth ファイルの refresh が全部失敗したとき、期限切れ access を返さない。`None` を返し、次の candidate ファイルを試してよい。全部だめなら `None`。
4. 抽出（NER / 関係）が認証エラー（403、`unauthenticated`、`bad-credentials`）を見たら、`resolve_access_token(force_refresh=True)` して `os.environ["XAI_API_KEY"]` を更新し、その知識点をやり直す。パターン NER には落ちない。
5. 冊内並列（既定2）でも refresh は一度に一本である（ロック）。
6. `read_books.py` は変えない。
7. リポ `.venv` へ `pip install semantica` しない。Hermes 作業記録に書かない。
8. テストはモックで、skew・非 JWT・refresh 失敗・抽出の 403 リトライを証明する。ライブ xAI は不要。
9. `test_keeps_expired_token_when_refresh_fails` は「期限切れを返す」期待を捨て、`None` 期待に直す。
10. `test_fresh_jwt_does_not_need_refresh` と `test_reads_valid_token_from_auth_json` は、skew 3600 でも「十分新しい」JWT（例: now+7200）を使う。

## 触ってよいファイル

- `xai_oauth.py`
- `book_semantica/extract.py`
- `book_semantica/xai_provider.py`（キー差し替えに必要なら）
- `tests/test_xai_oauth.py`
- `tests/test_book_semantica_extract.py`
- `docs/usage/13-semantica-books.md`（認証の持ち方を1段落）
- `docs/plans/2026-09-01-oauth-403-fix-report.md`（実装報告）

## 禁止

- トークン文字列をファイルやログに書く
- `auth.json` のライブ書き換え（テストの一時ファイル以外）
- ライブ `batch` / `--force` / `--all-points`
- FAISS / Neo4j
- Semantica の pip install
- 走っている優先11冊キューの kill

## 検証コマンド

リポ `.venv`:

```bash
.venv/bin/python -m unittest tests.test_xai_oauth tests.test_book_semantica_extract tests.test_book_semantica_batch tests.test_book_semantica_load -q
```

Semantica venv（extract が semantica を import する経路があるとき）:

```bash
PYTHONPATH=/opt/AI-reads-books-page-by-page \
  /var/lib/happy/.local/share/semantica/venv/bin/python -m unittest \
  tests.test_book_semantica_extract tests.test_book_semantica_pipeline -q
```
