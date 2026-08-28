# 勝てるプロダクト開発の教科書

Windows の `Downloads\勝てるプロダクト開発の教科書.pdf` を Linux へ受け取り、全書処理する。
オーケストレーターは受け取り口と委譲だけ行い、処理本体はサブエージェントが担当する。

## 状態

- 全書処理完了（2026-08-28 12:18）
- 失敗ページなし

## タスク

- [x] Tailscale 受け取り口を起動する
- [x] `kindle_pdfs/勝てるプロダクト開発の教科書.pdf` を待つ
- [x] `./run.sh read_books.py ... --interval 0` で全書処理する
- [x] `book_analysis/summaries/` に最終要約が出たら完了
