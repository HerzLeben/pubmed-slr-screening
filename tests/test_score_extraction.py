"""Scoring of the extraction (scripts/score_extraction.py, scripts/extraction_metrics.js). No network."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from score_extraction import (
    auto_score,
    load_human,
    load_items,
    metrics,
    quote_contexts,
    wilson,
)


def test_auto_score():
    assert auto_score("Eastern", " eastern ") == "correct"
    assert auto_score("57", "記載なし") is None  # 記載なし goes to the human too (2026-10-01)
    assert auto_score("Eastern", "China") is None
    assert auto_score("34/23", "34 / 23") is None  # only trim and case; the rest goes to the human


def test_wilson_known_value():
    lo, hi = wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-4) and hi == pytest.approx(0.7634, abs=1e-4)
    assert wilson(0, 0) == (None, None)


def test_quote_context():
    text = "A" * 300 + " the quoted words " + "B" * 300
    (c,) = quote_contexts(text, ["the quoted  words"], width=10)
    assert c["match"] == "the quoted words" and c["before"] == "…" + "A" * 9 + " " and c["after"].endswith("…")
    assert quote_contexts(text, ["missing"]) == [{"q": "missing", "nf": True}]


@pytest.fixture
def root(tmp_path):
    (tmp_path / "bench" / "extraction").mkdir(parents=True)
    (tmp_path / "bench" / "extraction" / "1.jsonl").write_text(
        json.dumps({"pmid": "11", "Country": "Eastern", "Sample size": "57", "Dose": "1x10^6"}) + "\n")
    jobs = tmp_path / "results" / "extraction" / "jobs" / "1"
    jobs.mkdir(parents=True)
    (jobs / "11.json").write_text(json.dumps({"review_pmid": "1", "pmid": "11", "fulltext": "results/fulltext/11.txt",
                                              "items": ["Country", "Sample size", "Dose"],
                                              "output": "results/extraction/out/1/11.json"}))
    (tmp_path / "results" / "fulltext").mkdir(parents=True)
    (tmp_path / "results" / "fulltext" / "11.txt").write_text("Patients in eastern regions received 10^6 cells.")
    out = tmp_path / "results" / "extraction" / "out" / "1"
    out.mkdir(parents=True)
    (out / "11.json").write_text(json.dumps({"review_pmid": "1", "pmid": "11", "items": [
        {"name": "Country", "value": "eastern", "quotes": ["eastern regions"]},
        {"name": "Sample size", "value": "記載なし", "quotes": []},
        {"name": "Dose", "value": "10^6 cells", "quotes": ["10^6 cells"]}]}))
    return tmp_path


def save_human(root, records):
    d = root / "results" / "extraction" / "human"
    d.mkdir(parents=True, exist_ok=True)
    (d / "1.json").write_text(json.dumps({"review_pmid": "1", "saved_at": "x", "records": records}))


def test_items_and_metrics(root):
    items = load_items(root, reviews=("1",), with_context=True)
    assert [it["auto"] for it in items] == ["correct", None, None]
    assert items[0]["ctx"][0]["match"] == "eastern regions"
    m = metrics(items, load_human(root, items, reviews=("1",)))
    assert m["overall"]["pending"] == 2 and m["overall"]["correct"] == 1 and m["overall"]["scored"] == 1
    save_human(root, [{"pmid": "11", "item": "Dose", "correct": True},
                      {"pmid": "11", "item": "Sample size", "correct": False}])
    m = metrics(items, load_human(root, items, reviews=("1",)))
    assert m["overall"]["pending"] == 0 and m["overall"]["accuracy"] == pytest.approx(2 / 3)
    assert m["by_pair"]["1/11"]["human_correct"] == 1


def test_human_cannot_score_rule_items(root):
    items = load_items(root, reviews=("1",))
    save_human(root, [{"pmid": "11", "item": "Country", "correct": False}])
    with pytest.raises(SystemExit):
        load_human(root, items, reviews=("1",))


def test_missing_output_stops(root):
    (root / "results" / "extraction" / "out" / "1" / "11.json").unlink()
    with pytest.raises(SystemExit):
        load_items(root, reviews=("1",))


NODE_RUN = ("const {extractionMetrics} = require(process.argv[1]); const a = JSON.parse(process.argv[2]);"
            "process.stdout.write(JSON.stringify(extractionMetrics(a.items, a.human)))")


@pytest.mark.skipif(shutil.which("node") is None, reason="node が無い")
def test_js_and_python_give_the_same_metrics():
    items = []
    autos = ["correct", None, None, None, None]
    for r, rid in enumerate(["A", "B"]):
        for p in range(3):
            for i in range(7):
                items.append({"review": rid, "pmid": str(10 * r + p), "name": f"item{i}", "auto": autos[(i + p + r) % 5]})
    human = {"A": {"0\titem2": True, "0\titem3": False, "1\titem1": True},
             "B": {"10\titem0": False, "11\titem4": True, "12\titem2": True}}
    py = metrics(items, human)
    js = json.loads(subprocess.run(
        ["node", "-e", NODE_RUN,
         str(SCRIPTS / "extraction_metrics.js"), json.dumps({"items": items, "human": human})],
        capture_output=True, text=True, check=True).stdout)
    assert js.keys() == py.keys() and js["by_pair"].keys() == py["by_pair"].keys()
    for scope in ("overall",):
        for k, v in py[scope].items():
            assert js[scope][k] == pytest.approx(v), k
    for group in ("by_review", "by_pair"):
        for key, m in py[group].items():
            for k, v in m.items():
                assert js[group][key][k] == pytest.approx(v), (group, key, k)
