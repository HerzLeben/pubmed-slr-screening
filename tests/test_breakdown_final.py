"""scripts/breakdown_final.py on a small made-up review. No network."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from breakdown_final import band, group, pubtype, run

IDS = ("I1", "I2", "E1")


def crit(*verdicts):
    return [{"id": i, "verdict": v} for i, v in zip(IDS, verdicts, strict=True)]


def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def make_review(root: Path) -> None:
    # pmid: (rank, abstract, pubtypes, A, B, status, human decision)
    rows = {
        "1": (5, "abs", ["Clinical Trial, Phase I"], crit(1, 1, 1), crit(1, 1, 1), "agreed_include", None),
        "2": (150, "abs", ["Journal Article"], crit(1, 0, 1), crit(1, 1, 1), "agreed_include", None),
        "3": (250, "", ["Letter", "Comment"], crit(0, 0, 1), crit(0, 1, 1), "agreed_include", None),
        "4": (450, "abs", ["Review", "Clinical Trial"], crit(1, 0, 1), crit(-1, 1, 1), "needs_human", "include"),
        "5": (500, "abs", ["Case Reports"], crit(1, 1, 1), crit(-1, 1, 1), "needs_human", "exclude"),
        "6": (600, "abs", ["Journal Article"], crit(-1, 1, 1), crit(-1, 1, 1), "agreed_exclude", None),
    }
    write(root / "r" / "candidates.json", {"review_pmid": "r", "records": [
        {"pmid": p, "rank": r[0], "abstract": r[1], "publication_types": r[2]} for p, r in rows.items()]})
    for who, k in (("a", 3), ("b", 4)):
        write(root / "screen" / who / "r" / "batch_01.json",
              {"records": [{"pmid": p, "criteria": r[k]} for p, r in rows.items()]})
    write(root / "adjudication" / "r.json", {"records": [{"pmid": p, "status": r[5]} for p, r in rows.items()]})
    write(root / "human" / "r.json", {"records": [{"pmid": p, "decision": r[6]} for p, r in rows.items() if r[6]]})


def test_final_groups_and_cumulative(tmp_path):
    make_review(tmp_path)
    r = run("r", ["1", "3", "6"], tmp_path)
    assert (r["n_final"], r["n_included"]) == (4, 2)
    g = {k: (v["n"], v["included"]) for k, v in r["groups"].items()}
    # 4 has a 0 and a -1: counted in the zero group
    assert g == {"all_1": (1, 1), "zero_with_abstract": (2, 0), "zero_no_abstract": (1, 1), "other": (0, 0)}
    assert r["zero_by_criterion"] == {"I2": 3, "I1": 1}
    assert r["zero_combos"] == {"I2": 2, "I1+I2": 1}
    assert r["score_cumulative"] == [
        {"score_ge": 6, "n": 1, "included": 1},
        {"score_ge": 5, "n": 2, "included": 1},
        {"score_ge": 3, "n": 4, "included": 2},  # 3 (0+0+1 + 0+1+1) and 4 (1+0+1 + -1+1+1) tie
    ]
    assert r["reach_all_included"] == {"score_ge": 3, "n": 4, "included": 2}
    assert r["rank_bands"] == {"1-200": 2, "201-400": 1, "401-": 1}
    assert r["publication_types"]["Review"] == {"n": 1, "included": 0}


def test_pubtype_priority():
    assert pubtype(["Review", "Clinical Trial"]) == "Review"
    assert pubtype(["Systematic Review"]) == "Review"
    assert pubtype(["Clinical Trial, Phase II", "Case Reports"]) == "Clinical Trial"
    assert pubtype(["Case Reports", "Letter"]) == "Case Reports"
    assert pubtype(["Editorial"]) == "Comment/Editorial/Letter"
    assert pubtype(["Congress"]) == "Congress"
    assert pubtype(["Journal Article", "News"]) == "Other"
    assert pubtype(None) == "Other"


def test_band_and_group_edges():
    assert [band(x) for x in (1, 200, 201, 400, 401)] == ["1-200", "1-200", "201-400", "201-400", "401-"]
    assert group(crit(1, 1, 1), crit(1, 1, 1), False) == "all_1"
    assert group(crit(1, 1, 1), crit(1, -1, 1), True) == "other"
    assert group(crit(0, 1, 1), crit(1, 1, 1), False) == "zero_no_abstract"
