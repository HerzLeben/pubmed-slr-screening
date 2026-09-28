#!/usr/bin/env python3
"""Split one review's candidates into screener input batches (docs/schema.md section 1).

For each batch the same records go to both screeners, each in its own file:
  results/batches/<rid>/a/batch_<nn>.json   criteria in ID order (I1, I2, ..., E1, ...)
  results/batches/<rid>/b/batch_<nn>.json   criteria in reverse order (..., E1, ..., I2, I1)
Each file holds review_pmid, screener, batch, the output path the screener must write, the criteria
(as in criteria.json, order as above) and the records (pmid, title, abstract) copied from
candidates.json. candidates.json stays the source of the text; the hooks match quotes against it.

A batch file that already exists is left as it is when the new one is identical, and the script stops
without writing anything when it would differ (a batch that has been screened must not change). This is
how candidates that grew from the top-N to all hits (fetch_pubmed.py --all-hits, ranks N+1.. appended)
get new batches after the screened ones.

Example:
  python3 scripts/make_batches.py --review-pmid 31190844 --size 20
"""

import argparse
import json
import sys
from pathlib import Path

SCREENERS = ("a", "b")


def batch_docs(rid: str, criteria: list[dict], candidates: list[dict], size: int) -> list[tuple[str, int, dict]]:
    """(screener, batch number, document) for every batch and screener."""
    ordered = sorted(candidates, key=lambda c: c["rank"])
    docs = []
    for n, start in enumerate(range(0, len(ordered), size), start=1):
        records = [{"pmid": str(c["pmid"]), "title": c.get("title", ""), "abstract": c.get("abstract") or ""}
                   for c in ordered[start : start + size]]
        for who in SCREENERS:
            crit = criteria if who == "a" else list(reversed(criteria))
            docs.append((who, n, {
                "review_pmid": rid,
                "screener": who,
                "batch": n,
                "output": f"results/screen/{who}/{rid}/batch_{n:02d}.json",
                "criteria_order": [c["id"] for c in crit],
                "criteria": crit,
                "records": records,
            }))
    return docs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--review-pmid", required=True)
    ap.add_argument("--size", type=int, default=20)
    ap.add_argument("--reviews-dir", default="reviews")
    ap.add_argument("--results-dir", default="results")
    args = ap.parse_args()

    rid = args.review_pmid
    criteria = json.loads((Path(args.reviews_dir) / rid / "criteria.json").read_text(encoding="utf-8"))["criteria"]
    candidates = json.loads((Path(args.results_dir) / rid / "candidates.json").read_text(encoding="utf-8"))["records"]
    docs = batch_docs(rid, criteria, candidates, args.size)
    planned = [(Path(args.results_dir) / "batches" / rid / who / f"batch_{n:02d}.json",
                json.dumps(doc, ensure_ascii=False, indent=1) + "\n") for who, n, doc in docs]
    changed = [str(path) for path, text in planned if path.exists() and path.read_text(encoding="utf-8") != text]
    if changed:
        sys.exit(f"{rid}: existing batches would change, nothing written: {', '.join(changed)}")
    new = 0
    for path, text in planned:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            new += 1
    print(f"{rid}: {len(docs) // len(SCREENERS)} batches x {len(SCREENERS)} screeners, {new} files new "
          f"-> {Path(args.results_dir) / 'batches' / rid}/")


if __name__ == "__main__":
    main()
