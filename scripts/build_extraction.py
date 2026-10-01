"""TrialReviewBench の data-extraction の CSV を bench/extraction/<PMID>.jsonl に整形する。

1行＝1研究（`pmid` と、答えの列名をそのまま key にした値）。列名・値は変えない。

使い方: python3 scripts/build_extraction.py 33746596 37168849
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "bench" / "raw" / "TrialReviewBench-data-extraction"
OUT = ROOT / "bench" / "extraction"


def convert(src: Path, dst: Path) -> tuple[int, list[str]]:
    with src.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        items = [c for c in reader.fieldnames if c != "PMID"]
        rows = list(reader)
    with dst.open("w", encoding="utf-8") as f:
        for r in rows:
            rec = {"pmid": r["PMID"].strip()}
            rec.update({c: r[c] for c in items})
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(rows), items


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pmids", nargs="+", help="レビューの PMID")
    pmids = ap.parse_args(argv).pmids
    OUT.mkdir(parents=True, exist_ok=True)
    for p in pmids:
        if not (RAW / f"{p}.csv").exists():
            sys.exit(f"{(RAW / f'{p}.csv').relative_to(ROOT)} が無い。README の「データの取り方」で TrialReviewBench を bench/raw/ に置く")
        n, items = convert(RAW / f"{p}.csv", OUT / f"{p}.jsonl")
        print(f"{p}\trows={n}\titems={len(items)}")


if __name__ == "__main__":
    main()
