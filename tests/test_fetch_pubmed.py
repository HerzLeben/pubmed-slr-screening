"""Date handling, PMID paging, record parsing and rebuild in scripts/fetch_pubmed.py (no network)."""

import json
import xml.etree.ElementTree as ET
from datetime import date

import fetch_pubmed
import pytest
from fetch_pubmed import (
    ESEARCH_LIMIT,
    collect_pmids,
    date_range,
    month_end,
    parse_records,
    vs_cap,
)

CAP = date(2021, 2, 18)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2021", (date(2021, 1, 1), date(2021, 12, 31))),
        ("2021 Oct", (date(2021, 10, 1), date(2021, 10, 31))),
        ("2021 Oct-Dec", (date(2021, 10, 1), date(2021, 12, 31))),
        ("2021 Oct 5", (date(2021, 10, 5), date(2021, 10, 5))),
        ("2021 Feb 18", (date(2021, 2, 18), date(2021, 2, 18))),
        ("2020 Winter", (date(2020, 12, 1), date(2021, 2, 28))),
        ("2021 Summer", (date(2021, 6, 1), date(2021, 8, 31))),
        ("2020 Dec-2021 Jan", (date(2020, 12, 1), date(2021, 1, 31))),
        ("  2021 Jan  ", (date(2021, 1, 1), date(2021, 1, 31))),
    ],
)
def test_date_range(text, expected):
    assert date_range(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "Oct 2021", "unknown"])
def test_date_range_unparseable(text):
    assert date_range(text) is None


def test_month_end_leap_year():
    assert month_end(2020, 2) == date(2020, 2, 29)
    assert month_end(2021, 2) == date(2021, 2, 28)
    assert month_end(2021, 12) == date(2021, 12, 31)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2021 Feb 18", "within"),  # the cap day itself is within
        ("2021 Feb 17", "within"),
        ("2020 Dec", "within"),
        ("2021 Feb 19", "after"),
        ("2021 Mar", "after"),
        ("2022", "after"),
        ("2021", "straddles"),  # year-only pubdate: cannot tell
        ("2021 Feb", "straddles"),
        ("2021 Jan-Mar", "straddles"),
        ("2020 Winter", "straddles"),  # 2020-12-01 .. 2021-02-28
        ("2020 Dec-2021 Mar", "straddles"),
        ("", "none"),
    ],
)
def test_vs_cap(text, expected):
    assert vs_cap(text, CAP) == expected


def fake_pages(pmids):
    """fetch_page over a fixed hit list; records each (retstart, retmax) call."""
    calls = []

    def fetch_page(start, size):
        calls.append((start, size))
        return pmids[start : start + size]

    return fetch_page, calls


def test_collect_pmids_pages_in_order():
    hits = [str(i) for i in range(1, 12)]
    fetch_page, calls = fake_pages(hits)
    assert collect_pmids(len(hits), fetch_page, page_size=5) == hits
    assert calls == [(0, 5), (5, 5), (10, 1)]


def test_collect_pmids_single_page():
    hits = ["3", "1", "2"]
    fetch_page, calls = fake_pages(hits)
    assert collect_pmids(3, fetch_page) == hits
    assert calls == [(0, 3)]


def test_collect_pmids_no_hits():
    fetch_page, calls = fake_pages([])
    assert collect_pmids(0, fetch_page) == []
    assert calls == []


def test_collect_pmids_limit():
    fetch_page, calls = fake_pages([])
    assert collect_pmids(ESEARCH_LIMIT, lambda s, n: ["x"] * n) == ["x"] * ESEARCH_LIMIT
    with pytest.raises(ValueError):
        collect_pmids(ESEARCH_LIMIT + 1, fetch_page)
    assert calls == []


ARTICLE_XML = """<PubmedArticleSet>
<PubmedArticle><MedlineCitation><PMID Version="1">111</PMID><Article>
<Journal><JournalIssue><PubDate><Year>2020</Year></PubDate></JournalIssue><Title>Blood</Title></Journal>
<ArticleTitle>A trial</ArticleTitle>
<Abstract><AbstractText Label="METHODS">Did it.</AbstractText><AbstractText Label="RESULTS">It worked.</AbstractText></Abstract>
<PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList>
</Article></MedlineCitation></PubmedArticle>
<PubmedBookArticle><BookDocument><PMID Version="1">222</PMID>
<Book><Publisher><PublisherName>CADTH</PublisherName></Publisher><BookTitle book="b">CADTH Report</BookTitle>
<PubDate><Year>2011</Year></PubDate></Book>
<ArticleTitle book="b" part="c">A chapter</ArticleTitle>
<PublicationType UI="D016454">Review</PublicationType>
<Abstract><AbstractText>Chapter text.</AbstractText></Abstract>
</BookDocument></PubmedBookArticle>
<PubmedBookArticle><BookDocument><PMID Version="1">333</PMID>
<Book><Publisher><PublisherName>CADTH</PublisherName></Publisher><BookTitle book="w">A whole book</BookTitle>
<PubDate><Year>2018</Year><Month>09</Month></PubDate></Book>
<PublicationType UI="D016454">Review</PublicationType>
</BookDocument></PubmedBookArticle>
</PubmedArticleSet>"""


def test_parse_records_article_and_books():
    recs = parse_records(ET.fromstring(ARTICLE_XML))
    assert set(recs) == {"111", "222", "333"}
    assert recs["111"] == {
        "pmid": "111", "title": "A trial", "abstract": "METHODS: Did it.\nRESULTS: It worked.",
        "journal": "Blood", "year": "2020", "publication_types": ["Journal Article"],
    }
    assert recs["222"] == {
        "pmid": "222", "title": "A chapter", "abstract": "Chapter text.",
        "journal": "CADTH Report", "year": "2011", "publication_types": ["Review"],
    }
    # a whole book: no ArticleTitle, no abstract
    assert recs["333"] == {
        "pmid": "333", "title": "A whole book", "abstract": "",
        "journal": "CADTH", "year": "2018", "publication_types": ["Review"],
    }


def test_rebuild_fetches_only_missing(tmp_path, monkeypatch):
    frozen = {"review_pmid": "999", "maxdate": "2021/02/18", "pmids": ["3", "1", "2"], "all_pmids": ["1", "2", "3", "4"]}
    search_path = tmp_path / "frozen.json"
    search_path.write_text(json.dumps(frozen))
    out = tmp_path / "results" / "999"
    out.mkdir(parents=True)
    kept = {"pmid": "1", "title": "kept", "abstract": "a", "year": "2020", "pubdate": "2020", "epubdate": "",
            "pubdate_vs_cap": "within", "epubdate_vs_cap": "none"}
    (out / "candidates.json").write_text(json.dumps({"review_pmid": "999", "records": [{"rank": 2, **kept}]}))

    asked = []

    def fake_efetch(pmids):
        asked.append(list(pmids))
        return {p: {"pmid": p, "title": f"new {p}", "abstract": ""} for p in pmids}

    monkeypatch.setattr(fetch_pubmed, "efetch", fake_efetch)
    monkeypatch.setattr(fetch_pubmed, "esummary_dates",
                        lambda pmids: {p: {"pubdate": "2021", "epubdate": "2021 Mar 1"} for p in pmids})

    fetch_pubmed.rebuild_from_search(search_path, str(tmp_path / "results"))

    assert asked == [["3", "2"]]
    doc = json.loads((out / "candidates.json").read_text())
    assert doc["review_pmid"] == "999"
    lines = doc["records"]
    assert [(x["rank"], x["pmid"]) for x in lines] == [(1, "3"), (2, "1"), (3, "2")]
    assert lines[1]["title"] == "kept"
    assert lines[1]["year"] == 2020  # schema section 4: year is an integer
    assert lines[0]["year"] is None
    assert all(set(x) >= {"pmid", "rank", "title", "abstract"} for x in lines)
    assert lines[0]["pubdate_vs_cap"] == "straddles"
    assert lines[0]["epubdate_vs_cap"] == "after"
    meta = json.loads((out / "search.json").read_text())
    assert meta["pmids"] == frozen["pmids"]
    assert meta["all_pmids"] == frozen["all_pmids"]
    assert meta["n_with_record"] == 3
    assert meta["n_with_abstract"] == 1
    assert meta["missing_pmids"] == []
    assert meta["n_fetched_on_rebuild"] == 2


def test_candidate_pmids_all_hits_keeps_top_ranks():
    meta = {"pmids": ["3", "1"], "all_pmids": ["1", "2", "3", "4"]}
    assert fetch_pubmed.candidate_pmids(meta, False) == ["3", "1"]
    assert fetch_pubmed.candidate_pmids(meta, True) == ["3", "1", "2", "4"]


def test_rebuild_all_hits(tmp_path, monkeypatch):
    frozen = {"review_pmid": "999", "maxdate": "2021/02/18", "pmids": ["3", "1"], "all_pmids": ["1", "2", "3", "4"]}
    search_path = tmp_path / "frozen.json"
    search_path.write_text(json.dumps(frozen))
    out = tmp_path / "results" / "999"
    out.mkdir(parents=True)
    kept = [{"pmid": p, "rank": r, "title": f"kept {p}", "abstract": "a", "year": 2020,
             "pubdate_vs_cap": "within", "epubdate_vs_cap": "none"} for r, p in ((1, "3"), (2, "1"))]
    (out / "candidates.json").write_text(json.dumps({"review_pmid": "999", "records": kept}))
    asked = []

    def fake_efetch(pmids):
        asked.append(list(pmids))
        return {p: {"pmid": p, "title": f"new {p}", "abstract": ""} for p in pmids}

    monkeypatch.setattr(fetch_pubmed, "efetch", fake_efetch)
    monkeypatch.setattr(fetch_pubmed, "esummary_dates", lambda pmids: {p: {"pubdate": "2020", "epubdate": ""} for p in pmids})

    fetch_pubmed.rebuild_from_search(search_path, str(tmp_path / "results"), all_hits=True)

    assert asked == [["2", "4"]]
    lines = json.loads((out / "candidates.json").read_text())["records"]
    assert [(x["rank"], x["pmid"], x["title"]) for x in lines] == [
        (1, "3", "kept 3"), (2, "1", "kept 1"), (3, "2", "new 2"), (4, "4", "new 4")]
    meta = json.loads((out / "search.json").read_text())
    assert meta["pmids"] == frozen["pmids"]
    assert meta["candidates_scope"] == "all_hits"
    assert meta["n_candidates"] == 4
    assert meta["n_with_record"] == 4


def test_rebuild_add_pmids_go_last(tmp_path, monkeypatch):
    frozen = {"review_pmid": "999", "maxdate": "2021/02/18", "pmids": ["3", "1"], "all_pmids": ["1", "2", "3"]}
    search_path = tmp_path / "frozen.json"
    search_path.write_text(json.dumps(frozen))
    monkeypatch.setattr(fetch_pubmed, "efetch",
                        lambda pmids: {p: {"pmid": p, "title": f"t {p}", "abstract": "a"} for p in pmids})
    monkeypatch.setattr(fetch_pubmed, "esummary_dates", lambda pmids: {p: {"pubdate": "2020", "epubdate": ""} for p in pmids})

    fetch_pubmed.rebuild_from_search(search_path, str(tmp_path / "results"), all_hits=True, add_pmids=["9", "2", "9"])

    out = tmp_path / "results" / "999"
    ranks = [(x["rank"], x["pmid"]) for x in json.loads((out / "candidates.json").read_text())["records"]]
    assert ranks == [(1, "3"), (2, "1"), (3, "2"), (4, "9")]
    meta = json.loads((out / "search.json").read_text())
    assert meta["added_pmids"] == ["9"]
    assert meta["all_pmids"] == frozen["all_pmids"]
    assert meta["n_candidates"] == 4
