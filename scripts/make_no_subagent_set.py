#!/usr/bin/env python3
"""Build the item set for the no-subagent trial (design.md ch.6): the top 100 candidates of one review,
plus one of the first 50 (with an abstract) shown again later under a new ID.

Outputs (under results/no-subagent/<review_pmid>/):
  items.jsonl  what the judge sees, in order: id (S001..), title, abstract. No PMID, no rank.
  key.json     id -> pmid and rank, and which id repeats which. Not to be read until judging is done.

Example:
  python3 scripts/make_no_subagent_set.py --review-pmid 31190844
"""

import argparse
import json
import random
from pathlib import Path


def build(candidates: list[dict], n: int, seed: int) -> tuple[list[dict], dict]:
    rng = random.Random(seed)
    top = candidates[:n]
    half = n // 2
    first_half_with_abstract = [c for c in top[:half] if c["abstract"]]
    dup = rng.choice(first_half_with_abstract)
    # position in the final list (0-based) somewhere in the second half, after the original
    insert_at = rng.randint(half, n)
    order = list(top)
    order.insert(insert_at, dup)
    items, ids = [], {}
    for i, c in enumerate(order, start=1):
        item_id = f"S{i:03d}"
        items.append({"id": item_id, "title": c["title"], "abstract": c["abstract"]})
        ids[item_id] = {"pmid": c["pmid"], "rank": c["rank"]}
    dup_ids = [k for k, v in ids.items() if v["pmid"] == dup["pmid"]]
    key = {"seed": seed, "n": n, "ids": ids, "duplicate": {"pmid": dup["pmid"], "ids": dup_ids}}
    return items, key


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--review-pmid", required=True)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20260927)
    ap.add_argument("--results-dir", default="results")
    args = ap.parse_args()

    src = Path(args.results_dir) / args.review_pmid / "candidates.jsonl"
    candidates = [json.loads(line) for line in src.read_text(encoding="utf-8").splitlines()]
    items, key = build(candidates, args.n, args.seed)

    out = Path(args.results_dir) / "no-subagent" / args.review_pmid
    out.mkdir(parents=True, exist_ok=True)
    with (out / "items.jsonl").open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    (out / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Print only counts: the judge must not learn which items repeat.
    print(f"items={len(items)} with_abstract={sum(1 for i in items if i['abstract'])} -> {out}/")


if __name__ == "__main__":
    main()
