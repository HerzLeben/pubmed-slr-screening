"""Decide status for every candidate by rule and write results/adjudication/<rid>.json.

The adjudicator subagent does NOT decide status. It only fills `summary` for
needs_human records afterwards. Re-running this script keeps existing summaries.

Usage:
    python scripts/adjudicate.py --reviews reviews --results results [--review 33746596]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import load, load_adjudication, load_screener, screened_reviews, write_json
from rules import adjudicate, disagree_ids


def run(rid: str, results: Path) -> dict:
    cands = load(results / rid / "candidates.json")["records"]
    a, b = load_screener(results, "a", rid), load_screener(results, "b", rid)
    old = load_adjudication(results, rid)
    records = []
    for c in sorted(cands, key=lambda r: r.get("rank", 0)):
        pmid = str(c["pmid"])
        ca, cb = a.get(pmid), b.get(pmid)
        status, reasons = adjudicate(ca, cb, c.get("abstract") or "", c.get("title") or "")
        rec = {"pmid": pmid, "status": status, "reasons": reasons, "disagree_criteria": disagree_ids(ca, cb)}
        prev = old.get(pmid, {})
        if prev.get("status") == status:  # keep the subagent's summary only if status is unchanged
            for k in ("summary", "summary_en"):
                if prev.get(k):
                    rec[k] = prev[k]
        records.append(rec)
    write_json(results / "adjudication" / f"{rid}.json", {"review_pmid": rid, "records": records})
    counts = {s: sum(r["status"] == s for r in records) for s in ("agreed_include", "agreed_exclude", "needs_human")}
    missing = sum(r["status"] == "needs_human" and not r.get("summary") for r in records)
    return {"review": rid, **counts, "needs_summary": missing}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviews", default="reviews")
    ap.add_argument("--results", default="results")
    ap.add_argument("--review", help="only this review PMID")
    args = ap.parse_args()
    results = Path(args.results)
    rids = [args.review] if args.review else screened_reviews(Path(args.reviews), results)
    for rid in rids:
        print(json.dumps(run(rid, results), ensure_ascii=False))


if __name__ == "__main__":
    main()
