"""Reading the files under results/ and bench/ (docs/schema.md). Shared by the scripts; the rules themselves
(score, overall, adjudication, the final candidates) are in rules.py.
"""

from __future__ import annotations

import json
from pathlib import Path

# the reviews whose study characteristics are extracted (bench/extraction/<rid>.jsonl, docs/schema.md 10章)
EXTRACTION_REVIEWS = ("33746596", "37168849")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, doc, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")


def load_screener(results: Path, who: str, rid: str, warn: list | None = None) -> dict[str, list[dict]]:
    """PMID -> criteria of one screener (results/screen/<who>/<rid>/batch_*.json). A PMID seen in two batches
    keeps the later one; with `warn`, that is also reported there."""
    out: dict[str, list[dict]] = {}
    for f in sorted((results / "screen" / who / rid).glob("batch_*.json")):
        for rec in load(f).get("records", []):
            pmid = str(rec.get("pmid"))
            if warn is not None and pmid in out:
                warn.append(["dup_batch", {"who": who, "pmid": pmid, "file": f.name}])
            out[pmid] = rec.get("criteria", [])
    return out


def load_adjudication(results: Path, rid: str) -> dict[str, dict]:
    """PMID -> record of results/adjudication/<rid>.json ({} when the file is not there)."""
    path = results / "adjudication" / f"{rid}.json"
    return {str(r["pmid"]): r for r in load(path)["records"]} if path.exists() else {}


def load_human(results: Path, rid: str) -> dict[str, dict]:
    """PMID -> record of results/human/<rid>.json ({} before the human decided anything)."""
    path = results / "human" / f"{rid}.json"
    return {str(r["pmid"]): r for r in load(path)["records"]} if path.exists() else {}


def screened_reviews(reviews: Path, results: Path) -> list[str]:
    """Reviews that have both reviews/<rid>/criteria.json and results/<rid>/candidates.json."""
    return sorted(p.parent.name for p in reviews.glob("*/criteria.json")
                  if (results / p.parent.name / "candidates.json").exists())
