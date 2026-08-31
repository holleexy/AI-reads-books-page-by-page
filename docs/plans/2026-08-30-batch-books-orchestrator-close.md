# 段1 量産オーケストレーションの閉じ

日付は 2026-08-30 である。
コミットしていない。51 冊のライブ LLM は回していない。

## Verdict

段1（ファイル量産の仕組み）は **PASS_WITH_GAPS** で閉じる。
前回 FAIL だった `.ocr` 冊のファイル誤認は消えた。
欠落 `extract_cache.json` で先頭スライスが落ちる経路も、本番 `run_batch` で消えた。

## できたこと

- `plan` / `batch` / `--dry-run` / 冊内 offset 再開 / マニフェスト
- 既存 `graph.json`（実体あり）は skip。『労務入門.ocr』は skip。pending は 50
- 空または entity 無しの `graph.json` は skip しない
- 出力先のファイル判定は `is_file()` と Hermes 作業記録の exact パスだけ。`.ocr` ディレクトリは通る
- キャッシュファイルが無い／不正 JSON のときは `next_offset` を捨てて先頭から取り直す
- `read_books.py` は未変更。FAISS / Neo4j は入れてない

## 残ギャップ（今は直さない）

- `extract_cache.json` が空 object `{}` のとき、読める dict として `next_offset` を信用する
- 非 UTF-8 のキャッシュは offset 判定では捨てるが、`pipeline._read_json` が `UnicodeDecodeError` で `batch` 行が fail する

どちらも欠落ファイルの本線ではない。
50 冊を通す作業の前提条件ではない。

## 次

ライブ `batch`（チャンク既定 80、全件は明示）を、未作成の冊に対して回すことである。
FAISS と Neo4j はまだ入れない。
