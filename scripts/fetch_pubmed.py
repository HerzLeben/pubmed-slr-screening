#!/usr/bin/env python3
"""Fetch the top-N PubMed candidates (PMID + abstract) for a fixed query and publication-date cap.

Calls NCBI E-utilities (esearch -> efetch) directly. Results are sorted by PubMed relevance.

Outputs (under results/<review_pmid>/):
  search.json       query, date range, retrieval time, counts, top-N PMIDs in rank order (pmids) and
                    every hit's PMID in the same relevance order (all_pmids; for recall over all hits)
  candidates.jsonl  one record per PMID: rank, pmid, title, abstract, journal, year, publication_types,
                    pubdate, epubdate (esummary, verbatim) and how each compares with --maxdate

datetype=pdat matches either the print (pubdate) or the electronic (epubdate) date. search.json counts
records whose pubdate is after the cap while epubdate is within it (and the reverse), to show which date
made them match. --compare-maxdate records total_hits of the same query under other caps.

PubMed's relevance order is not reproducible between calls, so the top-N list of one run is frozen in
search.json (committed as reviews/<review_pmid>/search.json). --from-search rebuilds candidates.jsonl from
such a file without searching again: it efetches only the PMIDs not already in candidates.jsonl.
NCBI Bookshelf records (PubmedBookArticle) are read as well as journal articles.

NCBI_API_KEY and NCBI_EMAIL are read from the environment, after loading the repo's .env with
python-dotenv (variables already set in the shell win). They are never printed or written to disk.
All requests are POSTs so the key never appears in a URL (and so not in error messages).
Spec: https://www.ncbi.nlm.nih.gov/books/NBK25499/

Example:
  python3 scripts/fetch_pubmed.py --review-pmid 33746596 \
      --query '"CAR-T" AND "multiple myeloma"' --maxdate 2021/03/01 --n 200
  python3 scripts/fetch_pubmed.py --from-search reviews/33746596/search.json
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "pubmed-slr-screening"
EFETCH_BATCH = 200
ESEARCH_PAGE = 5000
ESEARCH_LIMIT = 10000  # PubMed esearch serves only the first 10,000 records of a search (NBK25499)
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
SEASONS = {"spring": (3, 5), "summer": (6, 8), "fall": (9, 11), "autumn": (9, 11), "winter": (12, 2)}


def base_params() -> dict:
    params = {"db": "pubmed", "tool": TOOL}
    if os.environ.get("NCBI_API_KEY"):
        params["api_key"] = os.environ["NCBI_API_KEY"]
    if os.environ.get("NCBI_EMAIL"):
        params["email"] = os.environ["NCBI_EMAIL"]
    return params


def request_interval() -> float:
    # NCBI limit: 3 requests/s without an API key, 10 requests/s with one.
    return 0.11 if os.environ.get("NCBI_API_KEY") else 0.34


def post(endpoint: str, params: dict, retries: int = 3) -> bytes:
    data = urllib.parse.urlencode({**base_params(), **params}).encode()
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(f"{EUTILS}/{endpoint}", data=data)
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
            time.sleep(request_interval())
            return body
        except urllib.error.HTTPError as e:
            # Report only the status; never the request (it carries the key).
            msg = f"{endpoint}: HTTP {e.code}"
        except urllib.error.URLError as e:
            msg = f"{endpoint}: {e.reason}"
        if attempt == retries:
            sys.exit(f"error: {msg} (after {retries} attempts)")
        time.sleep(2**attempt)
    raise AssertionError("unreachable")


def esearch(query: str, n: int, mindate: str, maxdate: str, retstart: int = 0) -> dict:
    body = post(
        "esearch.fcgi",
        {
            "term": query,
            "retmax": n,
            "retstart": retstart,
            "sort": "relevance",
            "datetype": "pdat",
            "mindate": mindate,
            "maxdate": maxdate,
            "retmode": "json",
        },
    )
    result = json.loads(body)["esearchresult"]
    if "ERROR" in result:
        sys.exit(f"error: esearch: {result['ERROR']}")
    return result


def collect_pmids(total: int, fetch_page, page_size: int = ESEARCH_PAGE) -> list[str]:
    """All PMIDs of a search, page by page. fetch_page(retstart, retmax) returns one page of PMIDs.
    PubMed esearch serves only the first ESEARCH_LIMIT records of a search, so more is an error."""
    if total > ESEARCH_LIMIT:
        raise ValueError(f"{total} hits exceed the esearch limit of {ESEARCH_LIMIT}")
    pmids: list[str] = []
    for start in range(0, total, page_size):
        pmids.extend(fetch_page(start, min(page_size, total - start)))
    return pmids


def esummary_dates(pmids: list[str]) -> dict[str, dict]:
    dates = {}
    for i in range(0, len(pmids), EFETCH_BATCH):
        chunk = pmids[i : i + EFETCH_BATCH]
        result = json.loads(post("esummary.fcgi", {"id": ",".join(chunk), "retmode": "json"}))["result"]
        for pmid in result.get("uids", []):
            doc = result[pmid]
            dates[pmid] = {"pubdate": doc.get("pubdate", ""), "epubdate": doc.get("epubdate", "")}
    return dates


def date_range(text: str) -> tuple[date, date] | None:
    """Earliest and latest day a PubMed date string can mean ("2021", "2021 Oct", "2021 Oct-Dec",
    "2021 Oct 5", "2020 Winter", "2020 Dec-2021 Jan"). None if empty or unparseable."""
    m = re.match(r"^(\d{4})\s*(.*)$", text.strip())
    if not m:
        return None
    year, rest = int(m.group(1)), m.group(2).strip().lower()
    if not rest:
        return date(year, 1, 1), date(year, 12, 31)
    words = re.findall(r"[a-z]+|\d+", rest)
    months = [MONTHS[w[:3]] for w in words if w[:3] in MONTHS]
    season = next((SEASONS[w] for w in words if w in SEASONS), None)
    if season:
        first, last = season
        end_year = year + 1 if last < first else year
        return date(year, first, 1), month_end(end_year, last)
    if not months:
        return date(year, 1, 1), date(year, 12, 31)
    # A second 4-digit number is the end year of a cross-year range ("2020 Dec-2021 Jan").
    years = [int(w) for w in words if w.isdigit() and len(w) == 4]
    days = [int(w) for w in words if w.isdigit() and len(w) <= 2]
    if len(months) == 1 and len(days) == 1 and not years:
        d = date(year, months[0], days[0])
        return d, d
    end_year = years[-1] if years else year
    return date(year, months[0], 1), month_end(end_year, months[-1])


def month_end(year: int, month: int) -> date:
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1)


def vs_cap(text: str, cap: date) -> str:
    """'within' / 'after' / 'straddles' (e.g. pubdate "2021" vs cap 2021/02/18) / 'none'."""
    r = date_range(text)
    if r is None:
        return "none"
    if r[1] <= cap:
        return "within"
    if r[0] > cap:
        return "after"
    return "straddles"


def count_hits(query: str, mindate: str, maxdate: str) -> dict:
    result = esearch(query, 0, mindate, maxdate)
    return {"maxdate": maxdate, "total_hits": int(result.get("count", 0))}


def text_of(elem) -> str:
    return "".join(elem.itertext()).strip() if elem is not None else ""


def abstract_of(parent) -> str:
    parts = []
    for ab in parent.findall("Abstract/AbstractText"):
        label = ab.get("Label")
        txt = text_of(ab)
        parts.append(f"{label}: {txt}" if label else txt)
    return "\n".join(parts)


def parse_article(article) -> dict:
    citation = article.find("MedlineCitation")
    art = citation.find("Article")
    year = text_of(art.find("Journal/JournalIssue/PubDate/Year")) or text_of(
        art.find("Journal/JournalIssue/PubDate/MedlineDate")
    )[:4]
    return {
        "pmid": text_of(citation.find("PMID")),
        "title": text_of(art.find("ArticleTitle")),
        "abstract": abstract_of(art),
        "journal": text_of(art.find("Journal/Title")),
        "year": year,
        "publication_types": [text_of(pt) for pt in art.findall("PublicationTypeList/PublicationType")],
    }


def parse_book_article(article) -> dict:
    """NCBI Bookshelf records (e.g. HTA reports). A chapter has its own ArticleTitle; a whole book has
    only the BookTitle. The book title (or the publisher, for a whole book) stands in for the journal."""
    doc = article.find("BookDocument")
    book_title = text_of(doc.find("Book/BookTitle"))
    chapter_title = text_of(doc.find("ArticleTitle"))
    return {
        "pmid": text_of(doc.find("PMID")),
        "title": chapter_title or book_title,
        "abstract": abstract_of(doc),
        "journal": book_title if chapter_title else text_of(doc.find("Book/Publisher/PublisherName")),
        "year": text_of(doc.find("Book/PubDate/Year")),
        "publication_types": [text_of(pt) for pt in doc.findall("PublicationType")],
    }


def parse_records(root) -> dict[str, dict]:
    records = {}
    for article in root.findall("PubmedArticle"):
        rec = parse_article(article)
        records[rec["pmid"]] = rec
    for article in root.findall("PubmedBookArticle"):
        rec = parse_book_article(article)
        records[rec["pmid"]] = rec
    return records


def efetch(pmids: list[str]) -> dict[str, dict]:
    records = {}
    for i in range(0, len(pmids), EFETCH_BATCH):
        chunk = pmids[i : i + EFETCH_BATCH]
        body = post("efetch.fcgi", {"id": ",".join(chunk), "rettype": "abstract", "retmode": "xml"})
        records.update(parse_records(ET.fromstring(body)))
    return records


def add_dates(records: dict[str, dict], cap: date) -> None:
    """Attach esummary pubdate/epubdate (verbatim) and how each compares with the cap."""
    dates = esummary_dates(list(records)) if records else {}
    for pmid, rec in records.items():
        d = dates.get(pmid, {"pubdate": "", "epubdate": ""})
        rec.update(d)
        rec["pubdate_vs_cap"] = vs_cap(d["pubdate"], cap)
        rec["epubdate_vs_cap"] = vs_cap(d["epubdate"], cap)


def record_stats(pmids: list[str], records: dict[str, dict]) -> dict:
    return {
        "n_with_record": sum(1 for p in pmids if p in records),
        "n_with_abstract": sum(1 for p in pmids if p in records and records[p]["abstract"]),
        "missing_pmids": [p for p in pmids if p not in records],
        "n_pubdate_after_epubdate_within": sum(
            1 for r in records.values() if r["pubdate_vs_cap"] == "after" and r["epubdate_vs_cap"] == "within"),
        "n_epubdate_after_pubdate_within": sum(
            1 for r in records.values() if r["epubdate_vs_cap"] == "after" and r["pubdate_vs_cap"] == "within"),
        "n_pubdate_straddles_cap": sum(1 for r in records.values() if r["pubdate_vs_cap"] == "straddles"),
        "n_no_epubdate": sum(1 for r in records.values() if r["epubdate_vs_cap"] == "none"),
    }


def write_candidates(path: Path, pmids: list[str], records: dict[str, dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for rank, pmid in enumerate(pmids, start=1):
            if pmid in records:
                f.write(json.dumps({"rank": rank, **records[pmid]}, ensure_ascii=False) + "\n")


def parse_cap(maxdate: str) -> date:
    return datetime.strptime(maxdate, "%Y/%m/%d").date()  # noqa: DTZ007 -- only the calendar date is used


def rebuild_from_search(search_path: Path, out_dir: str) -> None:
    """Re-create candidates.jsonl for a frozen search.json without searching again (relevance order is
    not reproducible). Records already in <out_dir>/<review>/candidates.jsonl are kept; only the PMIDs
    missing from it are fetched."""
    meta = json.loads(search_path.read_text(encoding="utf-8"))
    pmids = meta["pmids"]
    out = Path(out_dir) / meta["review_pmid"]
    out.mkdir(parents=True, exist_ok=True)
    cand_path = out / "candidates.jsonl"
    records = {}
    if cand_path.exists():
        for line in cand_path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            rec.pop("rank", None)
            records[rec["pmid"]] = rec
    todo = [p for p in pmids if p not in records]
    fetched = efetch(todo) if todo else {}
    add_dates(fetched, parse_cap(meta["maxdate"]))
    records.update(fetched)
    records = {p: records[p] for p in pmids if p in records}
    write_candidates(cand_path, pmids, records)
    meta.update(record_stats(pmids, records))
    meta["candidates_rebuilt_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    meta["n_fetched_on_rebuild"] = len(fetched)
    (out / "search.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"fetched={len(fetched)} with_record={meta['n_with_record']} "
          f"with_abstract={meta['n_with_abstract']} -> {out}/")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--review-pmid", help="PMID of the target review (output folder name)")
    ap.add_argument("--query", help="approved PubMed Boolean query")
    ap.add_argument("--maxdate", help="publication date cap, YYYY/MM/DD (review's publication date)")
    ap.add_argument("--mindate", default="1800/01/01", help="publication date floor, YYYY/MM/DD")
    ap.add_argument("--n", type=int, default=200, help="number of top candidates by relevance")
    ap.add_argument("--compare-maxdate", action="append", default=[],
                    help="also record total_hits under this cap, YYYY/MM/DD (repeatable)")
    ap.add_argument("--from-search", type=Path,
                    help="rebuild candidates.jsonl from this frozen search.json (no esearch); other inputs ignored")
    ap.add_argument("--out-dir", default="results")
    args = ap.parse_args()

    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
    if args.from_search:
        rebuild_from_search(args.from_search, args.out_dir)
        return
    if not (args.review_pmid and args.query and args.maxdate):
        ap.error("--review-pmid, --query and --maxdate are required unless --from-search is given")
    retrieved_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    search = esearch(args.query, args.n, args.mindate, args.maxdate)
    pmids = search.get("idlist", [])
    total_hits = int(search.get("count", 0))
    try:
        all_pmids = collect_pmids(
            total_hits,
            lambda start, size: esearch(args.query, size, args.mindate, args.maxdate, start).get("idlist", []),
        )
    except ValueError as e:
        sys.exit(f"error: {e}")
    records = efetch(pmids) if pmids else {}
    add_dates(records, parse_cap(args.maxdate))
    compare = [count_hits(args.query, args.mindate, m) for m in args.compare_maxdate]

    out = Path(args.out_dir) / args.review_pmid
    out.mkdir(parents=True, exist_ok=True)
    write_candidates(out / "candidates.jsonl", pmids, records)

    meta = {
        "review_pmid": args.review_pmid,
        "query": args.query,
        "query_translation": search.get("querytranslation", ""),
        "date_type": "pdat",
        "mindate": args.mindate,
        "maxdate": args.maxdate,
        "sort": "relevance",
        "retrieved_at": retrieved_at,
        "total_hits": total_hits,
        "n_all_pmids": len(all_pmids),
        # The top-n list should be the head of the full list (same query, same sort); False means the
        # order or the hits changed between the two requests.
        "top_n_is_head_of_all": all_pmids[: len(pmids)] == pmids,
        "n_requested": args.n,
        "n_returned": len(pmids),
        **record_stats(pmids, records),
        "compare_maxdate": compare,
        "api_key_used": bool(os.environ.get("NCBI_API_KEY")),
        "pmids": pmids,
        "all_pmids": all_pmids,
    }
    (out / "search.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"total_hits={meta['total_hits']} all_pmids={meta['n_all_pmids']} returned={meta['n_returned']} "
        f"with_abstract={meta['n_with_abstract']} -> {out}/"
    )


if __name__ == "__main__":
    main()
