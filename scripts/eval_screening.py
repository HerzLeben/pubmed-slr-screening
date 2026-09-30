"""Evaluate search and screening against TrialReviewBench included_pmids (docs/requirements.md item 10).

Reads bench/reviews.jsonl (included_pmids), reviews/<rid>/search.json (all_pmids, pmids = top 200),
results/<rid>/candidates.json, results/screen/{a,b}/<rid>/batch_*.json, results/adjudication/<rid>.json,
results/human/<rid>.json. Prints one JSON object per review.

Definitions:
- search recall: |included & all_pmids| / |included|, and the same for the top-200 pmids
- Recall@k: candidates sorted by score (scripts/rules.py) descending, ties by rank ascending; share of the
  included studies that are in the top k. Denominator: included studies among the screened candidates
  (`in_pool`; the top 200 in eval-1, all hits in eval-2) and all included studies (`all`). Score = A alone, B alone, and A + B
- final candidates (docs/schema.md section 8): A only = overall(A) is include; B only = overall(B) is
  include; two screeners = agreed_include + needs_human that the human set to include
- missed: every included study not in the two-screener final list, with the stage it was lost at

eval-3 (--run eval-3, docs/eval/eval-3.md): screener-a only, draft criteria, no adjudication and no human.
Reads reviews/<rid>/eval-3/search.json (all_pmids), results/eval-3/<rid>/candidates.json and
results/eval-3/screen/a/<rid>/batch_*.json. Recall@k by A's score in two populations:
- all_hits: the candidates that are in all_pmids
- original: all_hits plus the included studies the search missed (added with fetch_pubmed.py --add-pmid),
  the way the original paper builds its candidate set
Also lists the rank of every included study, and for the reviews in REF_DROP the same Recall@k with one
criterion left out of the score (reference only; not compared with the original paper).

Usage:
    python scripts/eval_screening.py [--bench bench/reviews.jsonl] [--reviews reviews] [--results results]
    python scripts/eval_screening.py --run eval-3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rules import overall, score

KS = (20, 50)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def screener(results: Path, who: str, rid: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for f in sorted((results / "screen" / who / rid).glob("batch_*.json")):
        for rec in load(f)["records"]:
            out[str(rec["pmid"])] = rec["criteria"]
    return out


def ratio(n: int, d: int) -> float | None:
    return round(n / d, 3) if d else None


def recall_at(order: list[str], included: set[str], k: int, denom: int) -> dict:
    hit = len(set(order[:k]) & included)
    return {"hit": hit, "recall": ratio(hit, denom)}


def run(rid: str, included: list[str], reviews: Path, results: Path) -> dict:
    inc = {str(p) for p in included}
    search = load(reviews / rid / "search.json")
    all_ids, top = {str(p) for p in search["all_pmids"]}, {str(p) for p in search["pmids"]}
    cands = load(results / rid / "candidates.json")["records"]
    rank = {str(c["pmid"]): c["rank"] for c in cands}
    a, b = screener(results, "a", rid), screener(results, "b", rid)
    adj = {str(r["pmid"]): r for r in load(results / "adjudication" / f"{rid}.json")["records"]}
    hum_path = results / "human" / f"{rid}.json"
    human = {str(r["pmid"]): r for r in load(hum_path)["records"]} if hum_path.exists() else {}

    in_pool = inc & set(rank)
    scores = {
        "a": {p: score(a[p]) for p in rank},
        "b": {p: score(b[p]) for p in rank},
        "a+b": {p: score(a[p]) + score(b[p]) for p in rank},
    }
    at_k = {}
    for name, sc in scores.items():
        order = sorted(rank, key=lambda p: (-sc[p], rank[p]))
        at_k[name] = {f"@{k}": {"in_pool": recall_at(order, inc, k, len(in_pool)),
                                "all": recall_at(order, inc, k, len(inc))} for k in KS}

    needs_human = [p for p, r in adj.items() if r["status"] == "needs_human"]
    undecided = [p for p in needs_human if p not in human]
    final = {
        "a_only": {p for p in rank if overall(a[p]) == "include"},
        "b_only": {p for p in rank if overall(b[p]) == "include"},
        "two_plus_adjudication": {p for p, r in adj.items() if r["status"] == "agreed_include"}
        | {p for p in needs_human if human.get(p, {}).get("decision") == "include"},
    }
    final_eval = {name: {"n": len(s), "hit": len(s & inc), "recall_all": ratio(len(s & inc), len(inc)),
                         "recall_in_pool": ratio(len(s & in_pool), len(in_pool))} for name, s in final.items()}

    missed = []
    for p in sorted(inc - final["two_plus_adjudication"]):
        row: dict = {"pmid": p}
        if p not in all_ids:
            row["stage"] = "search"
        elif p not in rank:  # hit by the search but not screened (eval-1: outside the top 200)
            row["stage"] = "top200"
        else:
            r = adj[p]
            row.update(rank=rank[p], status=r["status"], reasons=r["reasons"],
                       a_minus=[c["id"] for c in a[p] if c["verdict"] == -1],
                       b_minus=[c["id"] for c in b[p] if c["verdict"] == -1],
                       a_overall=overall(a[p]), b_overall=overall(b[p]))
            if r["status"] == "needs_human":
                row["stage"] = "human" if p in human else "undecided"
                row["human_note"] = human.get(p, {}).get("note")
            else:
                row["stage"] = "screener"
        missed.append(row)

    return {
        "review": rid,
        "n_included": len(inc),
        "search": {"n_all": len(all_ids), "recall_all": ratio(len(inc & all_ids), len(inc)),
                   "hit_all": len(inc & all_ids), "n_top": len(top),
                   "recall_top200": ratio(len(inc & top), len(inc)), "hit_top200": len(inc & top)},
        "recall_at_k": at_k,
        "needs_human": len(needs_human),
        "undecided": len(undecided),
        "final": final_eval,
        "missed": missed,
    }


REF_DROP = {"31190844": "I5"}  # DECISIONS 2026-09-29 指示書19 2章: reference only


def ranked(pool: list[str], sc: dict[str, int], rank: dict[str, int]) -> list[str]:
    return sorted(pool, key=lambda p: (-sc[p], rank[p]))


def at_k_block(order: list[str], inc: set[str]) -> dict:
    in_pool = inc & set(order)
    return {"n": len(order), "n_included_in_pool": len(in_pool),
            **{f"@{k}": {"in_pool": recall_at(order, inc, k, len(in_pool)),
                        "all": recall_at(order, inc, k, len(inc))} for k in KS}}


def run_eval3(rid: str, included: list[str], reviews: Path, results: Path) -> dict:
    inc = {str(p) for p in included}
    search = load(reviews / rid / "eval-3" / "search.json")
    all_ids = [str(p) for p in search["all_pmids"]]
    cands = load(results / rid / "candidates.json")["records"]
    rank = {str(c["pmid"]): c["rank"] for c in cands}
    added = sorted(set(rank) - set(all_ids), key=lambda p: rank[p])
    side = results / rid / "search.json"
    recorded = [str(p) for p in load(side).get("added_pmids", [])] if side.exists() else []
    a = screener(results, "a", rid)
    missing = sorted(set(rank) - set(a), key=lambda p: rank[p])
    if missing:
        sys.exit(f"{rid}: screener-a の判定が無い候補 {len(missing)} 件（{missing[:5]}…）")
    sc = {p: score(a[p]) for p in rank}
    pools = {"all_hits": [p for p in rank if p in set(all_ids)], "original": list(rank)}
    out: dict = {
        "review": rid, "run": "eval-3", "n_included": len(inc),
        "search": {"n_all": len(all_ids), "hit_all": len(inc & set(all_ids)),
                   "recall_all": ratio(len(inc & set(all_ids)), len(inc)),
                   "missed": sorted(inc - set(all_ids))},
        "added_pmids": added, "added_matches_record": added == recorded or (not added and not recorded),
        "recall_at_k": {}, "included_ranks": {},
    }
    for name, pool in pools.items():
        order = ranked(pool, sc, rank)
        out["recall_at_k"][name] = at_k_block(order, inc)
        out["included_ranks"][name] = [{"pmid": p, "position": order.index(p) + 1, "score": sc[p],
                                        "rank": rank[p], "overall": overall(a[p]), "added": p in added,
                                        "minus": [c["id"] for c in a[p] if c["verdict"] == -1]}
                                       for p in order if p in inc]
    out["max_score"] = max(len(v) for v in a.values())
    drop = REF_DROP.get(rid)
    if drop:
        sc2 = {p: sum(int(c.get("verdict", 0)) for c in a[p] if c["id"] != drop) for p in rank}
        out["reference_without"] = {"criterion": drop, "note": "参考。原著との比較には使わない",
                                    **{name: at_k_block(ranked(pool, sc2, rank), inc)
                                       for name, pool in pools.items()},
                                    "included_ranks": [{"pmid": p, "position": i + 1, "score": sc2[p]}
                                                       for i, p in enumerate(ranked(pools["original"], sc2, rank))
                                                       if p in inc]}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default="bench/reviews.jsonl")
    ap.add_argument("--reviews", default="reviews")
    ap.add_argument("--results", default=None)
    ap.add_argument("--run", default=None, choices=["eval-3"], help="eval-3: screener-a, draft criteria, two populations")
    args = ap.parse_args()
    if args.results is None:
        args.results = "results/eval-3" if args.run == "eval-3" else "results"
    fn = run_eval3 if args.run == "eval-3" else run
    bench = [json.loads(line) for line in Path(args.bench).read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in sorted(bench, key=lambda r: r["PMID"]):
        rid = str(row["PMID"])
        print(json.dumps(fn(rid, row["included_pmids"], Path(args.reviews), Path(args.results)), ensure_ascii=False))


if __name__ == "__main__":
    main()
