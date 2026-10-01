"""scripts/eval_screening.py --run eval-3 on a small made-up review. No network."""

import json
from pathlib import Path

import build_report
import eval_screening
import pytest
from eval_screening import run_eval3

IDS = ("I1", "I5", "E1")


def crit(*verdicts):
    return [{"id": i, "verdict": v} for i, v in zip(IDS, verdicts, strict=True)]


def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def make(root: Path, rid: str = "r") -> tuple[Path, Path]:
    reviews, results = root / "reviews", root / "results" / "eval-3"
    # pmid: (rank, A). "9" is not in all_pmids: it was added (--add-pmid)
    rows = {"1": (1, crit(1, 1, 1)), "2": (2, crit(1, 0, 1)), "3": (3, crit(1, -1, 1)),
            "4": (4, crit(-1, 1, 1)), "9": (5, crit(1, 1, 1))}
    write(reviews / rid / "eval-3" / "search.json", {"all_pmids": ["1", "2", "3", "4"]})
    write(results / rid / "search.json", {"added_pmids": ["9"]})
    write(results / rid / "candidates.json", {"records": [{"pmid": p, "rank": r[0]} for p, r in rows.items()]})
    write(results / "screen" / "a" / rid / "batch_01.json",
          {"records": [{"pmid": p, "criteria": r[1]} for p, r in rows.items()]})
    return reviews, results


def test_two_populations(tmp_path):
    reviews, results = make(tmp_path)
    out = run_eval3("r", ["3", "9", "404"], reviews, results)
    assert out["search"]["hit_all"] == 1 and out["search"]["missed"] == ["404", "9"]
    assert out["added_pmids"] == ["9"] and out["added_matches_record"]
    assert out["recall_at_k"]["all_hits"]["n"] == 4 and out["recall_at_k"]["all_hits"]["n_included_in_pool"] == 1
    assert out["recall_at_k"]["original"]["n"] == 5 and out["recall_at_k"]["original"]["n_included_in_pool"] == 2
    # order by A's score, ties by rank: 1 (3), 9 (3), 2 (2), 3 (1), 4 (1)
    pos = {x["pmid"]: x["position"] for x in out["included_ranks"]["original"]}
    assert pos == {"9": 2, "3": 4}
    assert out["included_ranks"]["original"][0]["added"] is True
    assert out["recall_at_k"]["original"]["@20"]["in_pool"]["recall"] == 1.0


def test_reference_without_a_criterion(tmp_path, monkeypatch):
    reviews, results = make(tmp_path)
    monkeypatch.setattr(eval_screening, "REF_DROP", {"r": "I5"})
    out = run_eval3("r", ["3"], reviews, results)
    ref = out["reference_without"]
    assert ref["criterion"] == "I5"
    # without I5: 1 (2), 2 (2), 3 (2), 9 (2), 4 (0) -> 3 is third
    assert ref["included_ranks"] == [{"pmid": "3", "position": 3, "score": 2}]
    assert out["included_ranks"]["original"][0]["position"] == 4


def test_missing_judgment_stops(tmp_path):
    reviews, results = make(tmp_path)
    write(results / "screen" / "a" / "r" / "batch_01.json", {"records": [{"pmid": "1", "criteria": crit(1, 1, 1)}]})
    with pytest.raises(SystemExit, match="判定が無い"):
        run_eval3("r", ["3"], reviews, results)


def test_report_lists_records_in_score_order(tmp_path):
    reviews, results = make(tmp_path)
    write(reviews / "r" / "eval-3" / "criteria.json", {"criteria": [{"id": i} for i in IDS]})
    rv = build_report.build_review_eval3("r", ["3", "9"], {"ja": "題", "en": "Title"}, reviews, results)
    assert [(r["pmid"], r["position"]) for r in rv["records"]] == [("1", 1), ("9", 2), ("2", 3), ("3", 4), ("4", 5)]
    assert [r["pmid"] for r in rv["records"] if r["included"]] == ["9", "3"]
    assert [r["pmid"] for r in rv["records"] if r["added"]] == ["9"]
    assert rv["eval"]["review"] == "r" and rv["title_en"] == "Title"


def test_report_page_gets_the_data_and_the_logos():
    html = build_report.fill("<img src=__LOGO_MARK__><script>const DATA = __DATA__;</script>", {"x": "</script>"})
    assert "__" not in html and 'src=data:image/png;base64,' in html
    assert '{"x": "<\\/script>"}' in html  # "</" cannot end the script early
