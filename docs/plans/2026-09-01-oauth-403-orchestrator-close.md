# OAuth 403 修正のオーケストレーター閉じ

日付は 2026-09-01 である。
コミットしていない。push していない。
優先11冊の resume キューは止めていない（pid 1225704、起動から約27時間生存）。
ライブ xAI は回していない。トークン文字列は書いていない。

実装は [Implementer](f67b83e6-3bde-498f-af17-c3279110c11b)。
敵対検証は [Verifier](f0b9c425-88b1-4ea3-9751-bc97a2c3ca6b)。
判定は検証報告を信用せず、コードと `git status` とキュー生存で突き合わせた。

## Verdict

**PASS**

handoff の成功条件 10 件は、実装と敵対検証の両方で成立する。
実装者が直すべき欠陥は残っていない。
このセッションでは直さない残リスクだけが残る。

根拠:

- [構造](2026-09-01-oauth-403-structural.md)
- [handoff](2026-09-01-oauth-403-fix-handoff.md)
- [実装報告](2026-09-01-oauth-403-fix-report.md)
- [敵対検証](2026-09-01-oauth-403-adversarial-verify.md)

## できたこと

1. `REFRESH_SKEW_SECONDS = 3600`。失効まで1時間を切った JWT は起動時に refresh する。
2. 非 JWT / パース失敗 / `exp` 欠落は `access_token_needs_refresh` が True。
3. ある auth ファイルの refresh が全部失敗したら `None`。期限切れ `creds[0]["access"]` は返さない。次の candidate ファイルを試す。
4. 抽出の NER / 関係が 403 系なら `force_refresh`、`XAI_API_KEY` 更新、その知識点を1回やり直す。パターン NER には落ちない。
5. 冊内並列（既定2）の refresh は `threading.Lock` 一本。再試行は新しい `api_key` を渡す。
6. `read_books.py` と `book_semantica/xai_provider.py` は未変更。
7. リポ `.venv` へ semantica は入っていない。Hermes 作業記録は書いていない。
8. unittest はモック。敵対検証が自分で再実行し、リポ `.venv` 68 OK、Semantica venv 16 OK。
9. `test_keeps_expired_token_when_refresh_fails` は消え、`test_returns_none_when_refresh_fails` が `None` を期待する。
10. fresh JWT テストは `exp = now + 7200`。

## 作業ツリー（混ぜるな）

OAuth 修正そのもの:

- `xai_oauth.py`
- `book_semantica/extract.py`（403 リトライとロック。HEAD 比では冊内並列も含む。並列は以前の未コミット作業）
- `tests/test_xai_oauth.py`
- `tests/test_book_semantica_extract.py`（untracked）
- `docs/usage/13-semantica-books.md`
- `docs/plans/2026-09-01-oauth-403-*.md`

OAuth コミットに入れない:

- `scripts/run_semantica_newest_queue.sh`（`FORCE` 変更。許可集合の外）
- `book_analysis/semantica/**`（走っている優先キューの成果）

## 走っているジョブへの効き方

今の resume ディスパッチャは生きている。
すでに起動している Python プロセスは、この修正を読み込まない。
次に立ち上がる抽出プロセスから効く。
キューを殺して入れ直すことは、この閉じではしない。

## 残リスク（今は直さない）

- 親環境に `XAI_API_KEY` があると起動時の OAuth 解決をスキップする。抽出中の 403 では上書きする。
- チャンクが1時間を超えると skew だけでは足りない。そのときは抽出中の 403 リトライが拾う。
- Semantica 内部は例外の前に同じ死んだキーで最大3回叩くことがある。外側の「その知識点をもう一度」は満たす。
- opaque access に refresh が無いファイルは creds に入らず `None`。期限切れ leftover としては返さない。

## 次

OAuth 許可ファイルはコミット済みである。push は頼まれたときだけ。
修正を今すぐライブに効かせたいときは、優先キューの次プロセス起動を待つか、明示してから差し替える。
FAISS / Neo4j / 51冊ライブ / `--all-points` はまだしない。
