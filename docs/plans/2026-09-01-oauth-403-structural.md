# OAuth 403 は偶発ではなく、再開バッチの認証の持ち方の問題である

日付は 2026-09-01 である。
優先11冊の再開で、同じ `unauthenticated:bad-credentials` が約1時間おきではなく、トークンの寿命の切れ目にまとまって出ている。

本読み本体（`read_books.py`）は 403 のあと OAuth を強制更新してリトライする。
Semantica 下流は、起動時に一度だけキーを固定し、切れても同じキーで3回叩いて終わる。

## 観測

`expires_in` は 21600 秒（6時間）である。
プール先頭の access の JWT 失効は 2026-09-01 19:46:30 だった。
法人営業とバックオフィスの FAIL は 19:47:43 と 19:47:44 である。
切れ目と失敗が1分以内で重なる。

ディスパッチャの環境に `XAI_API_KEY` は無かった。
親シェルが古いキーを配り続けた、という経路ではない。

## 構造

1. **更新の余裕がチャンクより短い**  
   `REFRESH_SKEW_SECONDS` は 120 秒である。
   失効の2分前までは「まだ使える」とみなして、ファイルの access をそのまま返す。
   1チャンクは 15 から 50 分である。
   残り寿命が 10 分のトークンで `batch` を始めると、途中で切れる。

2. **プロセスの途中で更新しない**  
   `run_book_semantica.sh` は起動時だけ `resolve_xai_key` する。
   `XAIProvider` は `__init__` で `api_key` を固定する。
   抽出ループは知識点ごとに LLM を呼ぶが、キーは差し替えない。
   Semantica 側の3回リトライも同じ死んだキーである。

3. **403 を更新の合図にしない**  
   `read_books.py` の `call_api` は認証エラーで `resolve_access_token(force_refresh=True)` してクライアントを作り直す。
   `book_semantica/extract.py` にその経路は無い。

4. **更新に失敗すると期限切れの access を返す**  
   `resolve_access_token` は refresh が全部失敗すると `creds[0]["access"]` を返す。
   テスト `test_keeps_expired_token_when_refresh_fails` がこの挙動を固定している。
   切れたキーで NER を始める。

5. **JWT でない access は「更新不要」になる**  
   `access_token_needs_refresh` は `.` が無い文字列を False にする。
   `/var/lib/happy/.hermes/auth.json` の provider access は JWT ではなく、refresh も無い。
   このファイルが先に選ばれると、更新されないキーが使われる。

6. **環境の `XAI_API_KEY` があると OAuth を見ない**  
   今回のディスパッチャには無かった。
   経路としては残っている。
   Hermes の `.env` を source したあと、空でなければ `resolve_xai_key` は走らない。

## これは偶発ではない

トークンは6時間生きる。
チャンクは最大約50分である。
余裕が2分しか無いので、6時間の窓の終端にかかったチャンクは必ず 403 になる。
並列2冊が同じプール先頭を共有するので、切れ目に同時に落ちる。

冊内同時2本は、切れ方を速くすることはある。
切れないトークンを配る設計にはなっていない。

## 直すなら

抽出の 403 で `force_refresh` してキーを差し替え、そのチャンクを続ける。
起動時の skew を、1チャンクの想定時間（少なく見積もっても 3600 秒）以上にする。
refresh 失敗時に期限切れ access を返さない。
JWT でないキーを「更新不要」扱いにしない。

Hermes 作業記録には書かない。
既存知識点は取り直さない。
