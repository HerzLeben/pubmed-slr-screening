"""Status of PMC full text (no_pmc / pmc_no_body / body) and extraction jsonl in scripts/ (no network)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import fetch_pmc
from build_extraction import convert
from fetch_pmc import classify

WITH_BODY = b"""<?xml version="1.0"?>
<pmc-articleset><article><front><article-meta><title-group><article-title>T</article-title></title-group>
</article-meta></front><body><sec><title>Methods</title><p>Twelve patients were enrolled.</p></sec></body>
</article></pmc-articleset>"""

NO_BODY = b"""<?xml version="1.0"?>
<pmc-articleset><article><front><article-meta><abstract><p>Abstract only.</p></abstract></article-meta>
</front></article></pmc-articleset>"""

EMPTY_BODY = b"""<?xml version="1.0"?>
<pmc-articleset><article><front/><body>  </body></article></pmc-articleset>"""


def test_no_pmc_record():
    assert classify(None) == "no_pmc"


def test_body_present():
    assert classify(WITH_BODY) == "body"


def test_front_matter_only():
    assert classify(NO_BODY) == "pmc_no_body"


def test_empty_body_counts_as_no_body():
    assert classify(EMPTY_BODY) == "pmc_no_body"


def test_fetch_one_writes_xml_only_when_linked(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_pmc, "elink_pmc", lambda pmid: {"1": ["111"], "2": []}[pmid])
    monkeypatch.setattr(fetch_pmc, "efetch_pmc", lambda pmcid: WITH_BODY)
    assert fetch_pmc.fetch_one("1", tmp_path) == {"pmid": "1", "pmcid": "PMC111", "status": "body",
                                                  "n_pmc_links": 1}
    assert fetch_pmc.fetch_one("2", tmp_path) == {"pmid": "2", "pmcid": None, "status": "no_pmc"}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["1.xml"]


def test_extraction_csv_keeps_column_names_and_values(tmp_path):
    src = tmp_path / "r.csv"
    src.write_text('PMID,Sample size,"Median age (range)"\n123 ,12,"55 (40-70)"\n', encoding="utf-8")
    n, items = convert(src, tmp_path / "r.jsonl")
    assert (n, items) == (1, ["Sample size", "Median age (range)"])
    rec = json.loads((tmp_path / "r.jsonl").read_text(encoding="utf-8"))
    assert rec == {"pmid": "123", "Sample size": "12", "Median age (range)": "55 (40-70)"}
