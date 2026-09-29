---
name: eval
description: スクリーニングの評価（検索 Recall、Recall@20/50、最終候補の Recall、取りこぼしの分類、前回との比較）を docs/eval/<名前>.md に記録する。人だけが起動する
disable-model-invocation: true
argument-hint: <eval の名前（例：eval-3）> [--results <dir>]
---

# 評価を実行して記録する

対象：$ARGUMENTS（1つ目が名前。`docs/eval/<名前>.md` に書く。`--results` があれば評価する results の置き場所）

この skill は人が `/eval` で起動したときだけ動く。起動されたら、下の順に進め、最後に止まる。

## 0. 前提を確かめる（どれかが欠けたら止まって報告）

- `.venv/bin/python scripts/build_report.py --out results/report.html` を実行し、検査の警告が 0 件か
- `.venv/bin/python scripts/eval_screening.py` の `undecided` が3本とも 0 か（要人判断が残っていたら評価しない）
- `docs/eval/` に同じ名前のファイルが無いか（上書きしない）

## 1. 何を測るかを先に書く

`docs/eval/<名前>.md` を作り、実行の前に次を書く：
- 対象のレビュー、前回（`docs/eval/` の最も新しいもの）との違い（検索式・基準・枠・screener の条件など、DECISIONS から）
- 指標：eval-1 と同じ定義（`docs/eval/eval-1.md` の定義の表）。変えるなら理由

## 2. 実行する（数字はすべてこの出力から写す。手で数えない）

- `.venv/bin/python scripts/eval_screening.py [--results <dir>]`：検索 Recall、Recall@20/50（A・B・A+B）、最終候補の Recall、needs_human、取りこぼしの段
- `.venv/bin/python scripts/breakdown_final.py [--results <dir>]`：最終候補の内訳（区分、0 が付いた基準、スコアの累積、publication_types、rank の帯）
- `.venv/bin/python scripts/prisma_record.py [--results <dir>]`：PRISMA の件数（`results/prisma.json`）
- `bench/reviews.jsonl` の `included_pmids`（正解）は、この段で初めて使う。判定・裁定・人の判断を正解に合わせて直さない（DECISIONS 2026-09-29）

## 3. 前回と比較する

前回の results（`results/archive/<前回>/`）があれば、同じスクリプトを `--results` で実行し、同じ指標を並べた比較の表を作る。前回の md の数字と一致することを先に確かめる

## 4. 失敗を分類する

取りこぼした組み入れ研究を1件ずつ、design.md 5章の分類に振る：基準の粒度不足／abstract に情報が無い／引用の捏造（hook が捕まえた数）／2体とも誤り（相関）／ベンチマークの正解側の問題。加えて、検索の段（式に当たらない）と枠（スクリーニングしていない）。理由は抄録と判定の値から書き、臨床的な解釈は書かない

## 5. 記録して止まる

- `docs/eval/<名前>.md` に結果・比較・取りこぼし・読み取り（パイプラインの評価として）を書く
- 想定と違ったことは `docs/HARNESS.md` に日付つき1行
- 検索式・criteria・rules・agent 定義は変えない。直す案があれば「人が決めること」として書く
- commit と tag は人の指示を待つ。結果の要点を短く報告して止まる
