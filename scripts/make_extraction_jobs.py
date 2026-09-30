"""Write one extractor job per (review, study) whose PMC full text has a body.

results/extraction/jobs/<review>/<pmid>.json:
  {review_pmid, pmid, fulltext: results/fulltext/<pmid>.txt, items: [names], output: results/extraction/out/<review>/<pmid>.json}

- Studies: the `pmid` column of bench/extraction/<review>.jsonl, kept only when results/fulltext/status.json says
  "body". Only the pmid column is read; the answer values are never loaded (they must not reach the extractor).
- Items: the numbered list of reviews/<review>/extraction_items.md, in that order, names only.
- 30396908 is in both reviews and gets one job per review (the items differ).
Refuses to run when a full-text .txt is missing (run scripts/fulltext_to_text.py first).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEWS = ("33746596", "37168849")
ITEM = re.compile(r"^\d+\.\s+(.+?)\s*$")


def read_items(md: Path) -> list[str]:
    return [m.group(1) for line in md.read_text(encoding="utf-8").splitlines() if (m := ITEM.match(line))]


def read_pmids(jsonl: Path) -> list[str]:
    return [str(json.loads(line)["pmid"]) for line in jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]


def make_jobs(root: Path, reviews=REVIEWS) -> list[dict]:
    status = json.loads((root / "results/fulltext/status.json").read_text(encoding="utf-8"))["studies"]
    jobs = []
    for rid in reviews:
        items = read_items(root / "reviews" / rid / "extraction_items.md")
        for pmid in read_pmids(root / "bench" / "extraction" / f"{rid}.jsonl"):
            if status.get(pmid, {}).get("status") != "body":
                continue
            txt = f"results/fulltext/{pmid}.txt"
            if not (root / txt).exists():
                raise SystemExit(f"{txt} が無い。先に scripts/fulltext_to_text.py を実行する")
            jobs.append({"review_pmid": rid, "pmid": pmid, "fulltext": txt, "items": items,
                         "output": f"results/extraction/out/{rid}/{pmid}.json"})
    return jobs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    args = ap.parse_args(argv)
    jobs = make_jobs(args.root)
    for job in jobs:
        path = args.root / "results/extraction/jobs" / job["review_pmid"] / f"{job['pmid']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{path.relative_to(args.root)}: {len(job['items'])} items")
    print(f"{len(jobs)} jobs, {sum(len(j['items']) for j in jobs)} data points")
    return 0


if __name__ == "__main__":
    sys.exit(main())
