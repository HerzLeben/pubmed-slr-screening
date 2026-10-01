"""Record PRISMA counts for the title/abstract stage in results/prisma.json (docs/design.md section 4, prisma-record).

Reads reviews/<rid>/search.json (total_hits, all_pmids), reviews/<rid>/criteria.json (criterion order),
results/<rid>/candidates.json, results/screen/{a,b}/<rid>/batch_*.json, results/adjudication/<rid>.json and
results/human/<rid>.json. Does not read bench/reviews.jsonl (PRISMA does not use the answers).

Per review:
    identified          total_hits of the search (PubMed only)
    duplicates_removed  identified PMIDs listed more than once in all_pmids
    after_duplicates    identified - duplicates_removed
    not_screened        hits that were not screened (eval-1: outside the top 200)
    screened            records in candidates.json
    excluded            agreed_exclude + needs_human the human excluded
    excluded_by_reason  one reason per record: the first criterion, in criteria.json order, that A or B set
                        to -1 (agreed_exclude); "human" for a needs_human the human excluded
    awaiting_human      needs_human without a human decision
    to_full_text        agreed_include + needs_human the human included

check() holds the sums; .claude/hooks/check_prisma.py runs the same check after Claude writes or edits
results/prisma.json.

Usage:
    python scripts/prisma_record.py [--reviews reviews] [--results results] [--out results/prisma.json]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import load, load_adjudication, load_human, load_screener, write_json

COUNTS = ("identified", "duplicates_removed", "after_duplicates", "not_screened", "screened", "excluded",
          "awaiting_human", "to_full_text")
DETAIL = ("agreed_include", "agreed_exclude", "needs_human", "human_include", "human_exclude", "undecided")


def reason(order: list[str], a: list[dict], b: list[dict]) -> str:
    minus = {c["id"] for c in a + b if c["verdict"] == -1}
    return next((cid for cid in order if cid in minus), "no_minus1")


def record(rid: str, reviews: Path, results: Path) -> dict:
    search = load(reviews / rid / "search.json")
    order = [c["id"] for c in load(reviews / rid / "criteria.json")["criteria"]]
    screened = [str(c["pmid"]) for c in load(results / rid / "candidates.json")["records"]]
    a, b = load_screener(results, "a", rid), load_screener(results, "b", rid)
    adj = {p: r["status"] for p, r in load_adjudication(results, rid).items()}
    human = {p: r.get("decision") for p, r in load_human(results, rid).items()}

    all_pmids = [str(p) for p in search["all_pmids"]]
    identified = search["total_hits"]
    duplicates = len(all_pmids) - len(set(all_pmids))
    detail = dict.fromkeys(DETAIL, 0)
    by_reason = {cid: 0 for cid in order} | {"human": 0}
    for p in screened:
        status = adj[p]
        detail[status] += 1
        if status == "agreed_exclude":
            r = reason(order, a[p], b[p])
            by_reason[r] = by_reason.get(r, 0) + 1
        elif status == "needs_human":
            d = human.get(p)
            key = {"include": "human_include", "exclude": "human_exclude"}.get(d, "undecided")
            detail[key] += 1
            if key == "human_exclude":
                by_reason["human"] += 1
    return {
        "review_pmid": rid,
        "database": "PubMed",
        "search_retrieved_at": search.get("retrieved_at"),
        "maxdate": search.get("maxdate"),
        "identified": identified,
        "duplicates_removed": duplicates,
        "after_duplicates": identified - duplicates,
        "not_screened": identified - duplicates - len(screened),
        "screened": len(screened),
        "excluded": detail["agreed_exclude"] + detail["human_exclude"],
        "excluded_by_reason": by_reason,
        "awaiting_human": detail["undecided"],
        "to_full_text": detail["agreed_include"] + detail["human_include"],
        "detail": detail,
    }


def check(doc: dict) -> list[str]:
    """Problems with the sums in a prisma.json document; empty if it holds together."""
    errs: list[str] = []
    reviews = doc.get("reviews") if isinstance(doc, dict) else None
    if not isinstance(reviews, list) or not reviews:
        return ["top level must be an object with a non-empty list 'reviews'"]
    for r in reviews:
        rid = r.get("review_pmid", "?") if isinstance(r, dict) else "?"
        if not isinstance(r, dict):
            errs.append(f"{rid}: each review must be an object")
            continue
        bad = [k for k in COUNTS if not (isinstance(r.get(k), int) and not isinstance(r.get(k), bool) and r[k] >= 0)]
        if bad:
            errs.append(f"{rid}: counts must be integers >= 0: {', '.join(bad)}")
            continue
        reasons = r.get("excluded_by_reason")
        if not isinstance(reasons, dict) or not all(isinstance(v, int) and v >= 0 for v in reasons.values()):
            errs.append(f"{rid}: excluded_by_reason must map reasons to integers >= 0")
            continue

        def need(ok: bool, what: str, got: str, rid: str = rid) -> None:
            if not ok:
                errs.append(f"{rid}: {what} ({got})")

        need(r["identified"] - r["duplicates_removed"] == r["after_duplicates"],
             "identified - duplicates_removed != after_duplicates",
             f"{r['identified']} - {r['duplicates_removed']} vs {r['after_duplicates']}")
        need(r["screened"] + r["not_screened"] == r["after_duplicates"],
             "screened + not_screened != after_duplicates",
             f"{r['screened']} + {r['not_screened']} vs {r['after_duplicates']}")
        need(r["excluded"] + r["awaiting_human"] + r["to_full_text"] == r["screened"],
             "excluded + awaiting_human + to_full_text != screened",
             f"{r['excluded']} + {r['awaiting_human']} + {r['to_full_text']} vs {r['screened']}")
        need(sum(reasons.values()) == r["excluded"], "sum of excluded_by_reason != excluded",
             f"{sum(reasons.values())} vs {r['excluded']}")
        d = r.get("detail")
        if d is not None:
            if not (isinstance(d, dict) and all(isinstance(d.get(k), int) for k in DETAIL)):
                errs.append(f"{rid}: detail must have integer {', '.join(DETAIL)}")
                continue
            need(d["agreed_include"] + d["agreed_exclude"] + d["needs_human"] == r["screened"],
                 "detail: agreed_include + agreed_exclude + needs_human != screened",
                 f"{d['agreed_include']} + {d['agreed_exclude']} + {d['needs_human']} vs {r['screened']}")
            need(d["human_include"] + d["human_exclude"] + d["undecided"] == d["needs_human"],
                 "detail: human_include + human_exclude + undecided != needs_human",
                 f"{d['human_include']} + {d['human_exclude']} + {d['undecided']} vs {d['needs_human']}")
            need(d["agreed_include"] + d["human_include"] == r["to_full_text"],
                 "detail: agreed_include + human_include != to_full_text",
                 f"{d['agreed_include']} + {d['human_include']} vs {r['to_full_text']}")
            need(d["agreed_exclude"] + d["human_exclude"] == r["excluded"],
                 "detail: agreed_exclude + human_exclude != excluded",
                 f"{d['agreed_exclude']} + {d['human_exclude']} vs {r['excluded']}")
            need(d["undecided"] == r["awaiting_human"], "detail: undecided != awaiting_human",
                 f"{d['undecided']} vs {r['awaiting_human']}")
            need(reasons.get("human", 0) == d["human_exclude"], "excluded_by_reason.human != detail.human_exclude",
                 f"{reasons.get('human', 0)} vs {d['human_exclude']}")
    return errs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviews", default="reviews")
    ap.add_argument("--results", default="results")
    ap.add_argument("--out", default=None, help="default: <results>/prisma.json")
    args = ap.parse_args()
    results = Path(args.results)
    rids = sorted(p.name for p in (results / "adjudication").glob("*.json"))
    doc = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "generator": "scripts/prisma_record.py",
        "stage": "title/abstract",
        "reviews": [record(Path(r).stem, Path(args.reviews), results) for r in rids],
    }
    errs = check(doc)
    if errs:
        sys.exit("prisma counts do not add up:\n" + "\n".join(errs))
    out = Path(args.out) if args.out else results / "prisma.json"
    write_json(out, doc)
    for r in doc["reviews"]:
        print(f"{r['review_pmid']}: identified {r['identified']}, duplicates {r['duplicates_removed']}, "
              f"not screened {r['not_screened']}, screened {r['screened']}, excluded {r['excluded']} "
              f"{r['excluded_by_reason']}, awaiting human {r['awaiting_human']}, to full text {r['to_full_text']}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
