# 本リポジトリと Semantica の適合調査

調査日は 2026-08-29 である。
対象は本リポジトリ（`AI-reads-books-page-by-page`）と [semantica-agi/semantica](https://github.com/semantica-agi/semantica) である。

**結論**：本の情報からオントロジーとナレッジグラフを作ることはできる。
ただし Semantica のソースをこのリポジトリへ丸ごと入れる必要はない。
いまの抽出結果を下流に渡すライブラリとして足すのが正しい。

詳細は次に分けた。

- [このリポジトリがすでにやっていること](01-this-repo.md)
- [Semantica が提供すること](02-semantica.md)
- [できることとできないことの対応表](03-gap-matrix.md)
- [つなぎ方の選択肢と落とし穴](04-integration.md)
- [推奨する進め方](05-recommendation.md)
- [知識 JSON 45 冊の書名](06-book-titles.md)
- [Hermes 側の Semantica を使うか](07-use-hermes-semantica.md)
- [同じ判断の平文](08-plain-language.md)
- [挙げた 4 項目は実現するか](09-will-those-four-land.md)
- [全部やったあとに実現する状態](10-end-state.md)
- [end-state の上に DeepTutor を足すと広がるか](13-deeptutor-on-end-state.md)
- [ページ番号は必須である](11-page-provenance.md)
- [既存コーパスは取り直さない](12-no-full-reextract.md)
- [品質のすきまを、プログラムを追わない人向けに](15-quality-gaps-plain.md)
- [同じすきまが戻らないようにした](16-quality-recurrence-plain.md)
