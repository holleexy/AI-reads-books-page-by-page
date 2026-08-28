# 設定一覧

定数と `BookConfig` は `read_books.py` 先頭付近にある。
環境変数はクライアント、モデル上書き、バッチ並列数である。

## 環境変数

| 名前 | 役割 |
| --- | --- |
| `XAI_API_KEY` | あれば xAI chat completions を使う（最優先） |
| `CURSOR_API_KEY` | API キーも OAuth も無いときの Cursor Grok |
| `XAI_OAUTH_AUTH_JSON` | Hermes `auth.json` の明示パス |
| `XAI_DISABLE_OAUTH` | `1` で OAuth を使わない |
| `HERMES_HOME` | 指定時は `$HERMES_HOME/auth.json` を先に見る |
| `XAI_BASE_URL` | xAI 端点。既定 `https://api.x.ai/v1` |
| `XAI_MODEL` | 主モデル。既定 `grok-4.6` |
| `XAI_FALLBACK_MODEL` | レート制限時。既定 `grok-4.5` |
| `MAX_BOOK_WORKERS` | バッチの同時冊数。既定 `2` |

## `read_books.py` の引数

| 引数 | 役割 |
| --- | --- |
| `PDF` | ファイル、または直下の `*.pdf` を読むディレクトリ。1 つ以上 |
| `--pages N` | 先頭 N ページだけ。省略時は全書 |
| `--interval N` | 区間要約の間隔。既定 20。`0` で最終要約だけ |

## `read_books.py` の定数

| 名前 | いまの値 | 役割 |
| --- | --- | --- |
| `BASE_URL` | `https://api.x.ai/v1` | xAI |
| `PRIMARY_MODEL` | `grok-4.6` | 抽出と要約の主モデル |
| `FALLBACK_MODEL` | `grok-4.5` | レート制限時に切替 |
| `SAVE_INTERVAL` | `10` | knowledge と progress の保存間隔（ページ） |

## `BookConfig`

| フィールド | 既定 | 役割 |
| --- | --- | --- |
| `pdf_path` | 必須 | 入力 PDF |
| `base_dir` | `book_analysis` | 出力ルート |
| `model` | `PRIMARY_MODEL` | ページ抽出 |
| `analysis_model` | `PRIMARY_MODEL` | 要約 |
| `analysis_interval` | `20` | 区間要約の間隔。`None` で無効 |
| `test_pages` | `60`（CLI では省略時 `None`） | 処理する最大ページ。`None` で全書 |
| `start_page` | `0` | 開始ページ（0 始まり）。progress があるときは大きい方が勝つ |
| `book_key_override` | `None` | 出力ファイル名の接頭辞。未指定なら PDF の stem |

## ローカルスキップ

次に当てはまるページは API を呼ばない。

- 空白を除いた文字数が 20 未満
- `copyright`、`all rights reserved`、ISBN、`奥付`、`発行所`、`printed in japan` を含み、かつ 300 文字未満

本文らしい短い見出しはスキップしない想定である。
