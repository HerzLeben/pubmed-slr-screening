"""TrialReviewBench の study-search-screening.jsonl から対象レビューだけを bench/reviews.jsonl に整形する。

使い方: python3 scripts/build_bench.py 33746596 31190844 37168849
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "bench" / "raw" / "TrialReviewBench-study-search-screening.jsonl"
OUT = ROOT / "bench" / "reviews.jsonl"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pmids", nargs="+", help="レビューの PMID（書いた順に bench/reviews.jsonl に並ぶ）")
    pmids = ap.parse_args(argv).pmids
    if not RAW.exists():
        sys.exit(f"{RAW.relative_to(ROOT)} が無い。README の「データの取り方」で TrialReviewBench を bench/raw/ に置く")
    rows = {}
    for line in RAW.open(encoding="utf-8"):
        r = json.loads(line)
        rows[r["PMID"]] = r

    missing = [p for p in pmids if p not in rows]
    if missing:
        sys.exit(f"not found in raw: {missing}")

    with OUT.open("w", encoding="utf-8") as f:
        for p in pmids:
            r = rows[p]
            citations = r["Involved_Citations"]
            included = [str(c["pmid"]) for c in citations if c.get("pmid")]
            no_pmid = [c.get("title", "") for c in citations if not c.get("pmid")]
            rec = {
                "PMID": r["PMID"],
                "PICO": r["PICO"],
                "included_pmids": included,
                "Topic": r["Topic"],
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            dup = len(included) - len(set(included))
            print(f"{p}\tcitations={len(citations)}\twith_pmid={len(included)}\tunique={len(set(included))}\tdup={dup}\tno_pmid={len(no_pmid)}\t{r['Topic']}")
            for t in no_pmid:
                print(f"  no pmid: {t[:100]}")


if __name__ == "__main__":
    main()
