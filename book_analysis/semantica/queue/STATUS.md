# 新着順ライブ batch（2026-08-30 14:52 開始）

負荷: 8 CPU、load 約 2、MemAvailable 約 5GB、swap は満杯。
並列は最大 2 を上限にした。初回キューの変数上書き不具合で空キーが落ちたあと直し、いま 3 プロセスが同時に動いている（先行 1 冊＋新キュー 2 冊）。先行が終われば 2 に戻る。これ以上は上げない。

順は知識 JSON の更新時刻が新しいものから。チャンクは `--limit 80`。全件はかけていない。『労務入門』は skip。

いま走っている冊:

1. バックオフィス業務のすべてがわかる本.ocr
2. 社内SE1年目から貢献！-情シス-企画・開発・運用-107のルール_00.ocr
3. toppuseerusu_dakeni_Tayora_nai_Soshiki_wo_Tsukuru__Jissen_seeruu_

キュー: `book_analysis/semantica/queue/pending-newest.txt`（50 冊）
進捗: `book_analysis/semantica/queue/run-20260830-145237/`
