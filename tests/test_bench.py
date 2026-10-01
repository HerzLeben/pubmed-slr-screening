"""bench/ from the raw TrialReviewBench files: scripts/build_bench.py and scripts/build_extraction.py (no network)."""

import json

import build_bench
import pytest
from build_extraction import convert


def test_extraction_csv_keeps_column_names_and_values(tmp_path):
    src = tmp_path / "r.csv"
    src.write_text('PMID,Sample size,"Median age (range)"\n123 ,12,"55 (40-70)"\n', encoding="utf-8")
    n, items = convert(src, tmp_path / "r.jsonl")
    assert (n, items) == (1, ["Sample size", "Median age (range)"])
    rec = json.loads((tmp_path / "r.jsonl").read_text(encoding="utf-8"))
    assert rec == {"pmid": "123", "Sample size": "12", "Median age (range)": "55 (40-70)"}


@pytest.fixture
def bench(tmp_path, monkeypatch):
    raw, out = tmp_path / "raw.jsonl", tmp_path / "reviews.jsonl"
    rows = [{"PMID": "1", "PICO": {"P": "p"}, "Topic": "T", "Extra": "dropped",
             "Involved_Citations": [{"pmid": 11}, {"pmid": "12"}, {"title": "no pmid"}]},
            {"PMID": "2", "PICO": {}, "Topic": "U", "Involved_Citations": []}]
    raw.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    out.write_text("keep me\n", encoding="utf-8")
    monkeypatch.setattr(build_bench, "ROOT", tmp_path)
    monkeypatch.setattr(build_bench, "RAW", raw)
    monkeypatch.setattr(build_bench, "OUT", out)
    return out


def test_bench_keeps_the_answers_with_a_pmid(bench):
    build_bench.main(["2", "1"])
    got = [json.loads(line) for line in bench.read_text(encoding="utf-8").splitlines()]
    assert [r["PMID"] for r in got] == ["2", "1"]  # in the order given
    assert got[1] == {"PMID": "1", "PICO": {"P": "p"}, "included_pmids": ["11", "12"], "Topic": "T"}


def test_bench_without_arguments_does_not_empty_the_file(bench):
    with pytest.raises(SystemExit):
        build_bench.main([])
    assert bench.read_text(encoding="utf-8") == "keep me\n"


def test_bench_unknown_review_stops_before_writing(bench):
    with pytest.raises(SystemExit, match="not found"):
        build_bench.main(["1", "404"])
    assert bench.read_text(encoding="utf-8") == "keep me\n"
