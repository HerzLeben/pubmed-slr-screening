---
name: eval
description: 評価（検索 Recall、Recall@20/50、最終候補の Recall または組み入れ研究の順位、抽出の Accuracy、取りこぼしの分類、前回との比較）を docs/eval/<名前>.md に記録する。人の判断が入る流れ（eval-1・eval-2）と、原著と同じ流れ（--run eval-3）の両方。人だけが起動する
disable-model-invocation: true
argument-hint: <eval の名前（例：eval-4）> [--run eval-3] [--results <dir>]
---

# 評価を実行して記録する

対象：$ARGUMENTS（1つ目が名前。`docs/eval/<名前>.md` に書く。`--run eval-3` があれば原著と同じ流れの評価、無ければ人の判断が入る流れの評価。`--results` があれば評価する results の置き場所）

この skill は人が `/eval` で起動したときだけ動く。起動されたら、下の順に進め、最後に止まる。
引数が評価の名前として読めない（文になっている、など）ときは、評価を始めずに止まって聞く。

## 流れの違い

| | 人の判断が入る流れ（既定） | 原著と同じ流れ（`--run eval-3`、`docs/eval/eval-3.md`） |
|---|---|---|
| results | `results/`（`--results` で変える） | `results/eval-3/`（`--results` で変える） |
| 基準・検索 | `reviews/<rid>/criteria.json`（承認済み）・`search.json` | `reviews/<rid>/eval-3/criteria.json`（案のまま）・`eval-3/search.json` |
| screener | A と B、adjudication、人の判断 | A だけ。adjudication と人の判断は無い |
| 主な指標 | 最終候補の Recall、Recall@20/50（A・B・A+B） | Recall@20/50（A のスコア順、全ヒットと原著と同じ作り方の2つの母集団）、組み入れ研究の順位、抽出の Accuracy |
| 定義の表 | `docs/eval/eval-1.md` | `docs/eval/eval-3.md` |
| 同じ名前の評価 | — | `docs/eval/eval-3.md` は既にあるので、新しい評価は別の名前（例：`eval-3b`） |

下の `<run>` は、原著と同じ流れのときだけ `--run eval-3` を付ける、という意味。`--results` はそのまま渡す。

## 0. 前提を確かめる（どれかが欠けたら止まって報告）

- `docs/eval/` に同じ名前のファイルが無いか（上書きしない）
- 人の判断が入る流れ：
  - `.venv/bin/python scripts/build_report.py --out results/report.html [--results <dir>]` を実行し、検査の警告が 0 件か
  - `.venv/bin/python scripts/eval_screening.py [--results <dir>]` の `undecided` が3本とも 0 か（要人判断が残っていたら評価しない）
- 原著と同じ流れ：
  - `.venv/bin/python scripts/build_report.py --run eval-3 [--results <dir>]` を実行し、検査の警告が 0 件か
  - `.venv/bin/python scripts/eval_screening.py --run eval-3 [--results <dir>]` が止まらずに終わるか（screener-a の判定が無い候補があると止まる）、`added_matches_record` が3本とも true か
  - 抽出も評価するなら：`results/extraction/human/` の採点が終わっているか（`score_extraction.py` の pending が 0）

## 1. 何を測るかを先に書く

`docs/eval/<名前>.md` を作り、実行の前に次を書く：
- 対象のレビュー、前回（同じ流れの `docs/eval/` の最も新しいもの）との違い（検索式・基準・枠・screener の条件など、DECISIONS から）
- 指標：前回と同じ定義（上の表の定義の表）。変えるなら理由

## 2. 実行する（数字はすべてこの出力から写す。手で数えない）

人の判断が入る流れ：
- `.venv/bin/python scripts/eval_screening.py [--results <dir>]`：検索 Recall、Recall@20/50（A・B・A+B）、最終候補の Recall、needs_human、取りこぼしの段
- `.venv/bin/python scripts/breakdown_final.py [--results <dir>]`：最終候補の内訳（区分、0 が付いた基準、スコアの累積、publication_types、rank の帯）
- `.venv/bin/python scripts/prisma_record.py [--results <dir>]`：PRISMA の件数（`<results>/prisma.json`）

原著と同じ流れ：
- `.venv/bin/python scripts/eval_screening.py --run eval-3 [--results <dir>]`：検索 Recall と取りこぼした PMID、`all_hits`・`original` の2つの母集団での Recall@20/50、組み入れ研究の順位（`included_ranks`）、`reference_without`（参考。原著との比較には使わない）
- 抽出も評価するなら `.venv/bin/python scripts/score_extraction.py`：Accuracy と 95% CI（Wilson）、レビュー別・研究別、参考の値（`results/extraction/score.json`）
- breakdown_final・prisma_record は使わない（adjudication と人の判断が無い）

どちらの流れでも：`bench/reviews.jsonl` の `included_pmids`（正解）と `bench/extraction/` の答えは、この段で初めて使う。判定・裁定・人の判断・抽出の値を正解に合わせて直さない（DECISIONS 2026-09-29）

## 3. 前回と比較する

前回の results（`results/archive/<前回>/`）があれば、同じスクリプトを同じ `<run>` と `--results` で実行し、同じ指標を並べた比較の表を作る。前回の md の数字と一致することを先に確かめる。
原著と同じ流れでは、原著の値（`docs/eval/eval-3.md` の「原著との比較」。arXiv 版の値）とも並べる。条件の違い（レビューの数、候補の母集団、モデル、抽出の入力と採点者の数）を表の下に書く

## 4. 失敗を分類する

人の判断が入る流れ：取りこぼした組み入れ研究を1件ずつ、design.md 5章の分類に振る：基準の粒度不足／abstract に情報が無い／引用の捏造（hook が捕まえた数）／2体とも誤り（相関）／ベンチマークの正解側の問題。加えて、検索の段（式に当たらない）と枠（スクリーニングしていない）。

原著と同じ流れ：検索で当たらなかった研究と、Recall@50 に入らなかった組み入れ研究を1件ずつ、どの基準が -1 か 0 で順位を下げたか（`included_ranks` の `minus` とスコア）で分ける。抽出は、不正解を「記載なし（全文に見つからなかった）」と「値の違い」に分け、答えの不備の疑いは別に数える。

理由は抄録・全文と判定の値から書き、臨床的な解釈は書かない

## 5. 記録して止まる

- `docs/eval/<名前>.md` に結果・比較・取りこぼし・読み取り（パイプラインの評価として）を書く
- 想定と違ったことは `docs/HARNESS.md` に日付つき1行
- 検索式・criteria・rules・agent 定義は変えない。直す案があれば「人が決めること」として書く
- commit と tag は人の指示を待つ。結果の要点を短く報告して止まる
