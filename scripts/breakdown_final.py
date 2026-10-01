"""Break down the final include candidates (two screeners + adjudication + human) per review.

Reads the same inputs as eval_screening.py: bench/reviews.jsonl (included_pmids), results/<rid>/candidates.json,
results/screen/{a,b}/<rid>/batch_*.json, results/adjudication/<rid>.json, results/human/<rid>.json.

Final candidates (docs/schema.md section 8): agreed_include + needs_human that the human set to include.
For each review it reports:
- group: all criteria 1 in both A and B / has a 0 (with abstract) / has a 0 (no abstract) / other (1 and -1 only,
  a needs_human that the human included), with the included studies in each
- criteria that A or B set to 0, and the most common combinations of those criteria
- the A+B score distribution, cumulative counts for score >= s, and the included studies in them
- publication type, one per record by priority (PUBTYPE_ORDER)
- rank band in all hits (1-200 / 201-400 / 401-)

Usage:
    python scripts/breakdown_final.py [--bench ...] [--results results] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import load, load_adjudication, load_human, load_screener, read_jsonl
from rules import final_candidates, score

# (label, predicate on the list of publication types); the first match wins
PUBTYPE_ORDER = [
    ("Review", lambda ts: bool({"Review", "Systematic Review"} & ts)),
    ("Clinical Trial", lambda ts: any(t.startswith("Clinical Trial") for t in ts)),
    ("Case Reports", lambda ts: "Case Reports" in ts),
    ("Comment/Editorial/Letter", lambda ts: bool({"Comment", "Editorial", "Letter"} & ts)),
    ("Congress", lambda ts: "Congress" in ts),
]
BANDS = [("1-200", 1, 200), ("201-400", 201, 400), ("401-", 401, None)]
TOP_COMBOS = 5


def pubtype(types: list[str] | None) -> str:
    ts = set(types or [])
    return next((label for label, pred in PUBTYPE_ORDER if pred(ts)), "Other")


def band(rank: int) -> str:
    return next(label for label, lo, hi in BANDS if rank >= lo and (hi is None or rank <= hi))


def group(a: list[dict], b: list[dict], has_abstract: bool) -> str:
    """A 0 puts a record in a zero group even if it also has a -1 (a needs_human the human included)."""
    verdicts = [c["verdict"] for c in a + b]
    if 0 in verdicts:
        return "zero_with_abstract" if has_abstract else "zero_no_abstract"
    return "all_1" if all(v == 1 for v in verdicts) else "other"


def run(rid: str, included: list[str], results: Path) -> dict:
    inc = {str(p) for p in included}
    cands = {str(c["pmid"]): c for c in load(results / rid / "candidates.json")["records"]}
    a, b = load_screener(results, "a", rid), load_screener(results, "b", rid)
    adj = load_adjudication(results, rid)
    if not adj:
        sys.exit(f"{rid}: results/adjudication/{rid}.json が無い。先に scripts/adjudicate.py を実行する")
    final = sorted(final_candidates(adj, load_human(results, rid)))

    groups: Counter = Counter()
    groups_inc: Counter = Counter()
    group_inc_pmids: dict[str, list[str]] = {}
    zero_by: Counter = Counter()
    combos: Counter = Counter()
    scores: dict[str, int] = {}
    types: Counter = Counter()
    types_inc: Counter = Counter()
    bands: Counter = Counter()
    for p in final:
        c = cands[p]
        g = group(a[p], b[p], bool((c.get("abstract") or "").strip()))
        groups[g] += 1
        if p in inc:
            groups_inc[g] += 1
            group_inc_pmids.setdefault(g, []).append(p)
        zeros = {x["id"] for x in a[p] + b[p] if x["verdict"] == 0}
        zero_by.update(sorted(zeros))  # sorted: ties in most_common() keep a fixed order
        if zeros:
            combos["+".join(sorted(zeros))] += 1
        scores[p] = score(a[p]) + score(b[p])
        t = pubtype(c.get("publication_types"))
        types[t] += 1
        types_inc[t] += p in inc
        bands[band(c["rank"])] += 1

    dist = Counter(scores.values())
    cumulative, n, n_inc = [], 0, 0
    for s in sorted(dist, reverse=True):
        n += dist[s]
        n_inc += sum(1 for p, v in scores.items() if v == s and p in inc)
        cumulative.append({"score_ge": s, "n": n, "included": n_inc})
    n_final_inc = len(inc & set(final))
    reach_all = next((row for row in cumulative if row["included"] == n_final_inc), None)

    return {
        "review": rid,
        "n_final": len(final),
        "n_included": n_final_inc,
        "groups": {g: {"n": groups[g], "included": groups_inc[g], "included_pmids": group_inc_pmids.get(g, [])}
                   for g in ("all_1", "zero_with_abstract", "zero_no_abstract", "other")},
        "zero_by_criterion": dict(zero_by.most_common()),
        "zero_combos": dict(combos.most_common(TOP_COMBOS)),
        "score_cumulative": cumulative,
        "reach_all_included": reach_all,
        "publication_types": {t: {"n": types[t], "included": types_inc[t]}
                              for t in [label for label, _ in PUBTYPE_ORDER] + ["Other"]},
        "rank_bands": {label: bands[label] for label, _, _ in BANDS},
    }


def table(r: dict) -> str:
    g = r["groups"]
    lines = [f"## {r['review']}  final {r['n_final']} / included {r['n_included']}",
             "| group | n | included |", "|---|---|---|"]
    lines += [f"| {k} | {v['n']} | {v['included']} {' '.join(v['included_pmids'])} |" for k, v in g.items()]
    lines.append("zero by criterion: " + ", ".join(f"{k} {v}" for k, v in r["zero_by_criterion"].items()))
    lines.append("zero combos: " + ", ".join(f"{k} {v}" for k, v in r["zero_combos"].items()))
    lines.append("score >= s (n / included): "
                 + ", ".join(f"{x['score_ge']}: {x['n']}/{x['included']}" for x in r["score_cumulative"]))
    lines.append(f"reach all included: {r['reach_all_included']}")
    lines.append("publication types: " + ", ".join(f"{k} {v['n']} ({v['included']})"
                                                   for k, v in r["publication_types"].items()))
    lines.append("rank bands: " + ", ".join(f"{k} {v}" for k, v in r["rank_bands"].items()))
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default="bench/reviews.jsonl")
    ap.add_argument("--results", default="results")
    ap.add_argument("--json", action="store_true", help="print one JSON object per review instead of tables")
    args = ap.parse_args()
    for row in sorted(read_jsonl(Path(args.bench)), key=lambda r: r["PMID"]):
        r = run(str(row["PMID"]), row["included_pmids"], Path(args.results))
        print(json.dumps(r, ensure_ascii=False) if args.json else table(r) + "\n")


if __name__ == "__main__":
    main()
