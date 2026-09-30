# Cowork への引き継ぎ（2026-09-30 時点）

Cowork のセッションで、このプロジェクトの方針や結果を相談するための引き継ぎ。ここに書いたのは要約で、正本は各ファイル（下の「読む順序」）。数字は docs/eval/eval-3.md（原著との比較）と eval-2.md（人ありの流れ）から写した。

## 0. 状態

- **完成（2026-09-30）**：範囲は requirements 2章 #1 の ①〜⑥。⑦ 抽出は今回の範囲から外した（人の決定）。最新の tag は `snap/17-eval-3`
- 原著との比較は eval-3（人の判断なし）だけで行う。eval-1・eval-2 は人ありの流れの記録として残す

## 1. これは何か

- 系統的文献レビュー（SLR）のタイトル・抄録での一次スクリーニングを、Claude Code の subagent で行うワークフロー。TrialMind（Wang et al., npj Digital Medicine 2025）の手法を Claude Code で組み直した
- 人ありの流れ（eval-1・eval-2）：適格基準の案（`/pico-to-criteria`）→ 人が承認 → 検索式（query-builder が公式 PubMed コネクタで試す）→ 人が承認 → `fetch_pubmed.py` で抄録を一括取得 → screener-a（基準を正順で読む）と screener-b（逆順）が基準ごとに 1/0/-1 と逐語引用で判定 → `adjudicate.py` が規則で裁定、割れたものは adjudicator が理由を書いて人に回す → HTML レポートで人が判断
- 原著と同じ流れ（eval-3）：PICO → query-builder の検索式（案のまま）→ 基準の案のまま → screener-a（1体）→ A のスコアで順位 → Recall@k。人は判断しない
- 評価は TrialReviewBench の血液がん・CAR-T のレビュー3本（31190844、33746596、37168849）。正解は元のレビューが組み入れた論文のうち PMID のあるもの（7・9・11本）

## 2. 位置づけ（2026-09-29 人が決定）

- **業務での一次スクリーニングの代替ではなく、教育と手法（論文）の検証用**とする。実際の SLR は PubMed 以外も検索する必要があり、PubMed だけでは業務に足りない
- requirements.md、design.md、CLAUDE.md、レポートの注記に反映済み

## 3. 原著との比較（eval-3）

| 指標 | 原著（Immunotherapy） | eval-3（31190844／33746596／37168849） |
|---|---|---|
| 検索 Recall | 0.711〜0.834 | 1.000／1.000／0.909（計 26/27） |
| Recall@20 | 0.567 | 0.143／0.667／0.636（平均 0.482、合算 14/27） |
| Recall@50 | 0.713 | 0.429／1.000／0.909（平均 0.779、合算 22/27） |

- 母集団は「原著と同じ作り方」（全ヒット＋検索で拾えなかった組み入れ研究。足したのは 37168849 の 28864289 だけ）。全ヒットだけの値も eval-3.md にある
- 31190844 が低いのは、基準の案の I5（比較群）をそのまま使ったため。組み入れ研究7件のうち4件が I5 = -1。参考として I5 を外すと @50 は 0.714（原著との比較には使わない）
- 原著の値は arXiv 版。npj 掲載版とは照合しない（人の決定）
- レポート：`results/eval-3/report.html`（`build_report.py --run eval-3`、gitignore）

## 4. 人ありの流れの結果（eval-2、比較には使わない）

- 最終の Recall 22/27（0.815）、最終の候補 237件（145／59／33）、人に回った30件（正解は0件）
- 取りこぼし5件：検索で3件、screener で2件（どちらも承認済みの基準どおりの除外）。37168849 の3件は、元のレビュー自身の基準（CAR-T）と実際の組み入れが食い違うもの

## 5. これまでに人が決めたこと（要点）

- 「不明（0）」は組み入れる側に倒す。モデルはすべて Sonnet
- **答えを見たあとで検索式・基準・規則を動かさない**（2026-09-29）
- 原著との比較は人の判断を挟まない eval-3 だけで行う（2026-09-29、指示書19）
- 抽出（⑦）は今回の範囲外。npj 版との照合はしない。eval-3 の評価は、人の指示で Cowork が `eval_screening.py --run eval-3` を実行した（`/eval` skill は使っていない。HARNESS に記録）（2026-09-30）
- 詳細と理由：docs/DECISIONS.md

## 6. 残っていること（次の回）

- 抽出（⑦）：extractor の agent 定義 → 1本の試走 → 7組の抽出 → 完全一致は規則、残り約50件を人が採点 → Accuracy。準備（`bench/extraction/`、`fetch_pmc.py`、extraction_items.md）はそろっている
- `/eval` skill を人が打って動くかの確認（eval-3 では使っていない）

## 7. 分担と進め方

- Cowork：方針の相談、指示書の作成、Claude Code が読めない資料の確認、動画の切り出し。2026-09-30 は Cowork がリポジトリで直接、eval-3 の集計・レポート・docs を作った
- Claude Code（このリポジトリ）：指示書を受けて実装・実行し、節目で commit と `snap/*` tag。想定外のことや人の決定は HARNESS.md、設計の変更は DECISIONS.md に残す
- 指示書は人が Claude Code に貼り、hook が docs/prompts/log.md に記録する。番号は「指示書19」まで

## 8. 読む順序（リポジトリ：~/dev/pubmed-slr-screening）

1. CLAUDE.md（作業のルール）
2. docs/requirements.md（人が決めた要件。迷ったらここが正）
3. docs/eval/eval-3.md（原著との比較）、docs/eval/eval-2.md・eval-1.md（人ありの流れ）
4. docs/DECISIONS.md、docs/HARNESS.md
5. docs/design.md（冒頭に原著の3つの作業との対応表）

## 9. git の状態

- 最新の tag：`snap/17-eval-3`（eval-3 の評価、レポート、docs）。最新は `git log -1` で確かめる
