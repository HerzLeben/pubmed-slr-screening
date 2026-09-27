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
from rules import adjudicate, disagree_ids


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def screener(results: Path, who: str, rid: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for f in sorted((results / "screen" / who / rid).glob("batch_*.json")):
        for rec in load(f).get("records", []):
            out[str(rec["pmid"])] = rec.get("criteria", [])
    return out


def run(rid: str, results: Path) -> dict:
    cands = load(results / rid / "candidates.json")["records"]
    a, b = screener(results, "a", rid), screener(results, "b", rid)
    out_path = results / "adjudication" / f"{rid}.json"
    old = {str(r["pmid"]): r for r in load(out_path)["records"]} if out_path.exists() else {}
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
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"review_pmid": rid, "records": records}, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
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
    rids = [args.review] if args.review else sorted(
        p.parent.name for p in Path(args.reviews).glob("*/criteria.json") if (results / p.parent.name / "candidates.json").exists())
    for rid in rids:
        print(json.dumps(run(rid, results), ensure_ascii=False))


if __name__ == "__main__":
    main()
