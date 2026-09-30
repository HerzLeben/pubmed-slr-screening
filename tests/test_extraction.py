"""Extraction jobs (scripts/make_extraction_jobs.py): names only, never the answer values (no network)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from make_extraction_jobs import make_jobs, read_items

ITEMS_MD = """# 抽出の項目（1）

説明の段落。1. で始まらない行は項目にしない

1. Country
2. Sample size
3. Median age (range)
"""


@pytest.fixture
def root(tmp_path):
    (tmp_path / "reviews" / "1").mkdir(parents=True)
    (tmp_path / "reviews" / "1" / "extraction_items.md").write_text(ITEMS_MD, encoding="utf-8")
    (tmp_path / "bench" / "extraction").mkdir(parents=True)
    rows = [{"pmid": "11", "Country": "SECRET-COUNTRY", "Sample size": "SECRET-42", "Median age (range)": "x"},
            {"pmid": "12", "Country": "y", "Sample size": "y", "Median age (range)": "y"},
            {"pmid": "13", "Country": "z", "Sample size": "z", "Median age (range)": "z"}]
    (tmp_path / "bench" / "extraction" / "1.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    ft = tmp_path / "results" / "fulltext"
    ft.mkdir(parents=True)
    (ft / "status.json").write_text(json.dumps({"studies": {
        "11": {"status": "body"}, "12": {"status": "pmc_no_body"}, "13": {"status": "no_pmc"}}}))
    (ft / "11.txt").write_text("text")
    return tmp_path


def test_items_are_the_numbered_list_in_order(root):
    assert read_items(root / "reviews" / "1" / "extraction_items.md") == ["Country", "Sample size",
                                                                        "Median age (range)"]


def test_jobs_only_for_body_and_without_answers(root):
    jobs = make_jobs(root, reviews=("1",))
    assert [j["pmid"] for j in jobs] == ["11"]
    job = jobs[0]
    assert job == {"review_pmid": "1", "pmid": "11", "fulltext": "results/fulltext/11.txt",
                   "items": ["Country", "Sample size", "Median age (range)"],
                   "output": "results/extraction/out/1/11.json"}
    assert "SECRET" not in json.dumps(job)


def test_missing_text_stops(root):
    (root / "results" / "fulltext" / "11.txt").unlink()
    with pytest.raises(SystemExit):
        make_jobs(root, reviews=("1",))
