#!/usr/bin/env python3
"""Write reviews/<pmid>/criteria.json from the approved criteria.md (docs/schema.md section 2).

criteria.md is the source of truth; criteria.json is its machine-readable copy. The text of every
criterion is copied verbatim from the table rows (`| I1 | ... | ... |`). E texts keep the "does it
apply?" wording; the verdict direction (E: 1 = does not apply) is fixed by schema section 3, not here.
Rows of the `## 判定の補足` table (`| I2 | ... |`, the human's boundary decisions) become `note`.

Example:
  python3 scripts/criteria_to_json.py reviews/31190844 reviews/33746596 reviews/37168849
"""

import argparse
import json
import re
from pathlib import Path

ROW = re.compile(r"^\|\s*([IE]\d+)\s*\|\s*(.+?)\s*\|\s*[^|]*\|\s*$")  # | id | question | source |
NOTE = re.compile(r"^\|\s*([IE]\d+)\s*\|\s*(.+?)\s*\|\s*$")  # | id | note |  (in the 判定の補足 section)
NOTE_SECTION = "## 判定の補足"


def parse(md: str) -> dict:
    status = re.search(r"^状態：(.+)$", md, re.MULTILINE)
    if not status or not status.group(1).startswith("承認済み"):
        raise ValueError("criteria.md is not approved (状態：承認済み)")
    title_en = re.search(r"^元レビュー：(.+?)（", md, re.MULTILINE)
    criteria, notes, in_notes = [], {}, False
    for line in md.splitlines():
        if line.startswith("## "):
            in_notes = line.startswith(NOTE_SECTION)
        m = NOTE.match(line) if in_notes else ROW.match(line)
        if m and in_notes:
            notes.setdefault(m.group(1), []).append(m.group(2))
        elif m:
            cid, text = m.groups()
            criteria.append({"id": cid, "type": "inclusion" if cid[0] == "I" else "exclusion", "text": text})
    ids = [c["id"] for c in criteria]
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError(f"criteria ids missing or duplicated: {ids}")
    if set(notes) - set(ids):
        raise ValueError(f"notes for unknown criteria: {sorted(set(notes) - set(ids))}")
    for c in criteria:
        if c["id"] in notes:
            c["note"] = " ".join(notes[c["id"]])
    # schema: I1, I2, ..., E1, ... in ID order
    criteria.sort(key=lambda c: (c["id"][0] != "I", int(c["id"][1:])))
    doc = {"criteria": criteria}
    if title_en:  # criteria.md names the review by its original (English) title only
        doc["review_title"] = doc["review_title_en"] = title_en.group(1).strip()
    return doc


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("review_dirs", nargs="+", type=Path)
    args = ap.parse_args()
    for d in args.review_dirs:
        parsed = parse((d / "criteria.md").read_text(encoding="utf-8"))
        doc = {"review_pmid": d.name, **parsed}
        (d / "criteria.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{d / 'criteria.json'}: {[c['id'] for c in doc['criteria']]}")


if __name__ == "__main__":
    main()
