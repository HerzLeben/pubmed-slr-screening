---
name: prisma-record
description: タイトル・抄録の段の PRISMA の件数（検索 → 重複除去 → スクリーニング → 除外（理由別）→ 全文へ）を results/prisma.json に記録する。adjudicate と人の判断が終わった後に使う
argument-hint: [--results <dir>]
---

# PRISMA の件数を記録する

引数：$ARGUMENTS（無ければ `results/`。eval-1 のアーカイブなら `--results results/archive/eval-1`）

## 手順

1. `.venv/bin/python scripts/prisma_record.py $ARGUMENTS` を実行する。スクリプトが件数を数え、和が合うことを確かめてから `<results>/prisma.json` に書く。和が合わなければ書かずに止まるので、そのまま人に報告する
2. 出力の各行（review ごとの identified・duplicates・not screened・screened・excluded と理由別・awaiting human・to full text）を人に見せる
3. `awaiting human` が 0 でなければ、人の判断が残っていることを添えて止まる（全文へ進む件数がまだ決まっていない）

## 数え方（scripts/prisma_record.py の docstring が正本）

- identified は search.json の `total_hits`（PubMed だけ）。重複は `all_pmids` の重なり
- not_screened は検索で当たったがスクリーニングしていない件数（eval-1 の上位200件の枠の外）
- 除外理由は1件に1つ：`agreed_exclude` は criteria.json の並びで最初に A か B が -1 を付けた基準、人が除外した `needs_human` は `human`
- to_full_text は `agreed_include` と人が組み入れた `needs_human`
- `bench/reviews.jsonl`（正解）は読まない

## 手で直すとき

`results/prisma.json` を Write・Edit で直すと、PostToolUse の hook（`.claude/hooks/check_prisma.py`）が同じ和を検査し、合わなければ stderr で知らせる。知らされたら、数字を推測で合わせず、スクリプトを実行し直すか人に確認する
