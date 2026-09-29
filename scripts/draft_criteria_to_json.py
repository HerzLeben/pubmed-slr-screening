#!/usr/bin/env python3
"""Write reviews/<pmid>/eval-3/criteria.json from the unapproved draft reviews/<pmid>/criteria_draft.md (eval-3).

eval-3 uses the LLM's criteria draft as it is (指示書19 2章). The criterion rows of the inclusion and
exclusion tables are copied verbatim, the same way as criteria_to_json.py. The draft's "## 人に決めてほしい点"
section is questions for a person, not criteria, and is not passed to the screener; only the handling the draft
had already settled in it is kept, as the `note` of that criterion (DRAFT_NOTES, near-verbatim from the
draft; which bullet was kept or dropped is listed in docs/DECISIONS.md).

Example:
  python3 scripts/draft_criteria_to_json.py reviews/31190844 reviews/33746596 reviews/37168849
"""

import argparse
import json
from pathlib import Path

from criteria_to_json import ROW

DRAFT_NOTES = {
    "33746596": {
        "I1": "multiple myeloma 以外の疾患も含む試験（例：複数の血液がんをまとめた phase 1）で、"
              "抄録に RRMM の結果が分けて書かれていないものは I1 を 0 とし、組み入れる側に倒す",
        "E1": "PubMed に載る学会抄録（journal supplement）は除外しない。case report（1例報告）は除外しない",
    },
    "31190844": {
        "E1": "case report は除外しない",
    },
    "37168849": {
        "I1": "AML と他の疾患（例：MDS、ALL）をまとめた試験で、抄録に RR-AML の結果が分けて書かれていないものは"
              " I1 を 0 とし、組み入れる側に倒す",
        "E1": "case report は除外しない",
    },
}
STOP_SECTION = "## 人に決めてほしい点"


def parse_draft(md: str, rid: str) -> dict:
    criteria = []
    for line in md.split(STOP_SECTION)[0].splitlines():
        m = ROW.match(line)
        if m:
            cid, text = m.groups()
            criteria.append({"id": cid, "type": "inclusion" if cid[0] == "I" else "exclusion", "text": text})
    ids = [c["id"] for c in criteria]
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError(f"criteria ids missing or duplicated: {ids}")
    notes = DRAFT_NOTES.get(rid, {})
    if set(notes) - set(ids):
        raise ValueError(f"notes for unknown criteria: {sorted(set(notes) - set(ids))}")
    for c in criteria:
        if c["id"] in notes:
            c["note"] = notes[c["id"]]
    criteria.sort(key=lambda c: (c["id"][0] != "I", int(c["id"][1:])))
    return {"review_pmid": rid, "source": "criteria_draft.md", "criteria": criteria}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("review_dirs", nargs="+", type=Path)
    args = ap.parse_args()
    for d in args.review_dirs:
        doc = parse_draft((d / "criteria_draft.md").read_text(encoding="utf-8"), d.name)
        out = d / "eval-3" / "criteria.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{out}: {[c['id'] for c in doc['criteria']]}")


if __name__ == "__main__":
    main()
