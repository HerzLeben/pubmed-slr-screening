"""criteria.md -> criteria.json, candidates -> screener batches, and the report's title quotes. No network."""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import build_report
from criteria_to_json import parse
from make_batches import batch_docs

MD = """# 適格基準 — PMID 999

状態：承認済み（2026-09-27、人が承認）
元レビュー：A review of something（J Test 2020）

## 包含基準
| ID | 問い | 出典 |
|---|---|---|
| I2 | 二つ目か | I |
| I1 | 一つ目か | P |

## 除外基準
| ID | 問い | 出典 |
|---|---|---|
| E1 | 二次文献か | PICO 外 |

## 判定の補足（上の決定事項の写し）
| ID | 補足 |
|---|---|
| I2 | 二重標的も満たす |
"""


def test_criteria_md_to_json():
    doc = parse(MD)
    assert [c["id"] for c in doc["criteria"]] == ["I1", "I2", "E1"]  # ID order
    assert doc["criteria"][1] == {"id": "I2", "type": "inclusion", "text": "二つ目か", "note": "二重標的も満たす"}
    assert doc["criteria"][2]["type"] == "exclusion"
    assert "note" not in doc["criteria"][0]
    assert doc["review_title_en"] == "A review of something"


def test_criteria_md_must_be_approved():
    with pytest.raises(ValueError, match="approved"):
        parse(MD.replace("状態：承認済み", "状態：案"))


def test_criteria_note_for_unknown_id():
    with pytest.raises(ValueError, match="unknown"):
        parse(MD + "| I9 | 知らない |\n")


def test_repo_criteria_json_matches_md():
    """criteria.json is a copy of the approved criteria.md (docs/schema.md section 2)."""
    for d in sorted((REPO / "reviews").glob("*/criteria.md")):
        on_disk = json.loads((d.parent / "criteria.json").read_text(encoding="utf-8"))
        assert on_disk == {"review_pmid": d.parent.name, **parse(d.read_text(encoding="utf-8"))}, d


CRIT = [{"id": "I1"}, {"id": "I2"}, {"id": "E1"}]


def test_batches_split_and_order():
    cands = [{"pmid": str(n), "rank": n, "title": f"t{n}", "abstract": None if n == 3 else f"a{n}"}
             for n in range(45, 0, -1)]
    docs = batch_docs("999", CRIT, cands, 20)
    assert [(w, n) for w, n, _ in docs] == [("a", 1), ("b", 1), ("a", 2), ("b", 2), ("a", 3), ("b", 3)]
    a1, b1 = docs[0][2], docs[1][2]
    assert a1["criteria_order"] == ["I1", "I2", "E1"]
    assert b1["criteria_order"] == ["E1", "I2", "I1"]  # screener-b reads in reverse
    assert a1["records"] == b1["records"]  # the same records for both
    assert [r["pmid"] for r in a1["records"]] == [str(n) for n in range(1, 21)]  # rank order
    assert a1["records"][2]["abstract"] == ""
    assert a1["output"] == "results/screen/a/999/batch_01.json"
    assert len(docs[4][2]["records"]) == 5


def test_report_marks_title_quotes(tmp_path):
    rid = "999"
    (tmp_path / "reviews" / rid).mkdir(parents=True)
    crit = [{"id": "I1", "type": "inclusion", "text": "x"}, {"id": "E1", "type": "exclusion", "text": "y"}]
    (tmp_path / "reviews" / rid / "criteria.json").write_text(json.dumps({"review_pmid": rid, "criteria": crit}))
    res = tmp_path / "results"
    (res / rid).mkdir(parents=True)
    cand = {"pmid": "1", "rank": 1, "title": "A review of CAR-T therapy", "abstract": "Patients with B‑cell lymphoma."}
    (res / rid / "candidates.json").write_text(json.dumps({"review_pmid": rid, "records": [cand]}))
    judged = {"review_pmid": rid, "screener": "a", "batch": 1, "records": [{"pmid": "1", "criteria": [
        {"id": "I1", "verdict": 1, "quote": "Patients with B-cell lymphoma"},
        {"id": "E1", "verdict": -1, "quote": "A review of CAR-T therapy"}]}]}
    for who in ("a", "b"):
        (res / "screen" / who / rid).mkdir(parents=True)
        (res / "screen" / who / rid / "batch_01.json").write_text(json.dumps({**judged, "screener": who}))
    rv = build_report.build_review(rid, tmp_path / "reviews", res)
    side = rv["records"][0]["a"]["crit"]
    assert side["I1"]["src"] == "abstract"
    assert side["E1"]["src"] == "title"
    start, end = side["E1"]["span"]
    assert cand["title"][start:end] == "A review of CAR-T therapy"
    assert not [w for w in rv["warnings"] if w[0].startswith("quote")]
