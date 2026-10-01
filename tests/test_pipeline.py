"""The steps after the screeners on a small made-up review: scripts/common.py, adjudicate.py and the eval-2
metrics of eval_screening.py (eval-3 is tests/test_eval3.py). No network."""

import json
from pathlib import Path

import adjudicate
import pytest
from common import (
    load,
    load_adjudication,
    load_human,
    load_screener,
    read_jsonl,
    screened_reviews,
)
from eval_screening import run
from rules import final_candidates, id_key, ranked

RID = "999"
ABS = "Adults with relapsed lymphoma received CAR-T cells."
QUOTE = "Adults with relapsed lymphoma"


def crit(*verdicts):
    return [{"id": cid, "verdict": v, "quote": QUOTE if v else None}
            for cid, v in zip(("I1", "I2", "E1"), verdicts, strict=True)]


def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


# pmid: (A, B). 1 agreed include, 2 agreed exclude, 3 overall disagree, 4 a 0 against a 1 (agreed include)
JUDGED = {"1": (crit(1, 1, 1), crit(1, 1, 1)), "2": (crit(-1, 1, 1), crit(-1, 1, 1)),
          "3": (crit(1, 1, 1), crit(1, -1, 1)), "4": (crit(1, 0, 1), crit(1, 1, 1))}


@pytest.fixture
def project(tmp_path):
    reviews, results = tmp_path / "reviews", tmp_path / "results"
    write(reviews / RID / "criteria.json", {"review_pmid": RID, "criteria": [{"id": i} for i in ("I1", "I2", "E1")]})
    write(reviews / RID / "search.json", {"all_pmids": ["1", "2", "3", "4", "5"], "pmids": ["1", "2", "3", "4"]})
    write(results / RID / "candidates.json",
          {"records": [{"pmid": p, "rank": int(p), "title": "t", "abstract": ABS} for p in JUDGED]})
    for i, who in enumerate("ab"):
        write(results / "screen" / who / RID / "batch_01.json",
              {"records": [{"pmid": p, "criteria": v[i]} for p, v in JUDGED.items()]})
    return reviews, results


def test_common_readers(project, tmp_path):
    reviews, results = project
    assert screened_reviews(reviews, results) == [RID]
    assert load_screener(results, "b", RID)["3"][1]["verdict"] == -1
    assert load_adjudication(results, RID) == {} and load_human(results, RID) == {}
    (tmp_path / "x.jsonl").write_text('{"a": 1}\n\n{"a": 2}\n', encoding="utf-8")
    assert read_jsonl(tmp_path / "x.jsonl") == [{"a": 1}, {"a": 2}]


def test_load_screener_reports_a_pmid_in_two_batches(project):
    _, results = project
    write(results / "screen" / "a" / RID / "batch_02.json", {"records": [{"pmid": "1", "criteria": []}]})
    warn = []
    assert load_screener(results, "a", RID, warn)["1"] == []  # the later batch wins
    assert warn == [["dup_batch", {"who": "a", "pmid": "1", "file": "batch_02.json"}]]


def test_rules_order_and_final_list():
    assert sorted(["E1", "I10", "I2", "E2", "I1"], key=id_key) == ["I1", "I2", "I10", "E1", "E2"]
    assert ranked(["a", "b", "c"], {"a": 1, "b": 3, "c": 3}, {"a": 1, "b": 3, "c": 2}) == ["c", "b", "a"]
    adj = {"1": {"status": "agreed_include"}, "2": {"status": "agreed_exclude"},
           "3": {"status": "needs_human"}, "4": {"status": "needs_human"}}
    assert final_candidates(adj, {"3": {"decision": "include"}, "4": {"decision": "exclude"}}) == {"1", "3"}


def test_adjudicate_decides_status_by_rule(project):
    _, results = project
    counts = adjudicate.run(RID, results)
    assert counts == {"review": RID, "agreed_include": 2, "agreed_exclude": 1, "needs_human": 1, "needs_summary": 1}
    recs = {r["pmid"]: r for r in load(results / "adjudication" / f"{RID}.json")["records"]}
    assert recs["3"]["reasons"] == ["overall_disagree", "criterion_disagree"]
    assert recs["4"] == {"pmid": "4", "status": "agreed_include", "reasons": ["criterion_disagree"],
                         "disagree_criteria": ["I2"]}


def test_adjudicate_keeps_a_summary_only_while_the_status_holds(project):
    _, results = project
    adjudicate.run(RID, results)
    path = results / "adjudication" / f"{RID}.json"
    doc = load(path)
    for r in doc["records"]:
        r["summary"] = f"why {r['pmid']}"
    write(path, doc)
    # B now agrees on 3, so 3 is no longer needs_human and its summary is dropped
    write(results / "screen" / "b" / RID / "batch_01.json",
          {"records": [{"pmid": p, "criteria": v[0] if p == "3" else v[1]} for p, v in JUDGED.items()]})
    adjudicate.run(RID, results)
    recs = {r["pmid"]: r for r in load(path)["records"]}
    assert recs["3"]["status"] == "agreed_include" and "summary" not in recs["3"]
    assert recs["1"]["summary"] == "why 1"


def test_eval2_metrics(project):
    reviews, results = project
    adjudicate.run(RID, results)
    write(results / "human" / f"{RID}.json", {"records": [{"pmid": "3", "decision": "exclude", "note": "n"}]})
    out = run(RID, ["3", "4", "5", "6"], reviews, results)  # 5: hit but not screened, 6: not hit
    assert out["search"]["hit_all"] == 3 and out["search"]["hit_top200"] == 2
    assert out["final"]["two_plus_adjudication"] == {"n": 2, "hit": 1, "recall_all": 0.25, "recall_in_pool": 0.5}
    assert out["final"]["a_only"]["hit"] == 2  # A alone includes 3 and 4
    assert out["undecided"] == 0
    missed = {m["pmid"]: m for m in out["missed"]}
    assert (missed["5"]["stage"], missed["6"]["stage"]) == ("top200", "search")
    assert missed["3"]["stage"] == "human" and missed["3"]["human_note"] == "n"
    assert out["recall_at_k"]["a+b"]["@20"]["in_pool"] == {"hit": 2, "recall": 1.0}


def test_eval2_needs_the_adjudication(project):
    reviews, results = project
    with pytest.raises(SystemExit, match="adjudicate"):
        run(RID, ["1"], reviews, results)
