#!/usr/bin/env python3
"""Fetch the top-N PubMed candidates (PMID + abstract) for a fixed query and publication-date cap.

Calls NCBI E-utilities (esearch -> efetch) directly. Results are sorted by PubMed relevance.

Outputs (under results/<review_pmid>/):
  search.json       query, date range, retrieval time, counts, PMIDs in rank order
  candidates.jsonl  one record per PMID: rank, pmid, title, abstract, journal, year, publication_types

NCBI_API_KEY and NCBI_EMAIL are read from the environment, after loading the repo's .env with
python-dotenv (variables already set in the shell win). They are never printed or written to disk.
All requests are POSTs so the key never appears in a URL (and so not in error messages).
Spec: https://www.ncbi.nlm.nih.gov/books/NBK25499/

Example:
  python3 scripts/fetch_pubmed.py --review-pmid 33746596 \
      --query '"CAR-T" AND "multiple myeloma"' --maxdate 2021/03/01 --n 200
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "pubmed-slr-screening"
EFETCH_BATCH = 200


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


def esearch(query: str, n: int, mindate: str, maxdate: str) -> dict:
    body = post(
        "esearch.fcgi",
        {
            "term": query,
            "retmax": n,
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


def text_of(elem) -> str:
    return "".join(elem.itertext()).strip() if elem is not None else ""


def parse_article(article) -> dict:
    citation = article.find("MedlineCitation")
    art = citation.find("Article")
    parts = []
    for ab in art.findall("Abstract/AbstractText"):
        label = ab.get("Label")
        txt = text_of(ab)
        parts.append(f"{label}: {txt}" if label else txt)
    year = text_of(art.find("Journal/JournalIssue/PubDate/Year")) or text_of(
        art.find("Journal/JournalIssue/PubDate/MedlineDate")
    )[:4]
    return {
        "pmid": text_of(citation.find("PMID")),
        "title": text_of(art.find("ArticleTitle")),
        "abstract": "\n".join(parts),
        "journal": text_of(art.find("Journal/Title")),
        "year": year,
        "publication_types": [text_of(pt) for pt in art.findall("PublicationTypeList/PublicationType")],
    }


def efetch(pmids: list[str]) -> dict[str, dict]:
    records = {}
    for i in range(0, len(pmids), EFETCH_BATCH):
        chunk = pmids[i : i + EFETCH_BATCH]
        body = post("efetch.fcgi", {"id": ",".join(chunk), "rettype": "abstract", "retmode": "xml"})
        root = ET.fromstring(body)
        for article in root.findall("PubmedArticle"):
            rec = parse_article(article)
            records[rec["pmid"]] = rec
    return records


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--review-pmid", required=True, help="PMID of the target review (output folder name)")
    ap.add_argument("--query", required=True, help="approved PubMed Boolean query")
    ap.add_argument("--maxdate", required=True, help="publication date cap, YYYY/MM/DD (review's publication date)")
    ap.add_argument("--mindate", default="1800/01/01", help="publication date floor, YYYY/MM/DD")
    ap.add_argument("--n", type=int, default=200, help="number of top candidates by relevance")
    ap.add_argument("--out-dir", default="results")
    args = ap.parse_args()

    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
    retrieved_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    search = esearch(args.query, args.n, args.mindate, args.maxdate)
    pmids = search.get("idlist", [])
    records = efetch(pmids) if pmids else {}

    out = Path(args.out_dir) / args.review_pmid
    out.mkdir(parents=True, exist_ok=True)
    missing = [p for p in pmids if p not in records]
    with (out / "candidates.jsonl").open("w", encoding="utf-8") as f:
        for rank, pmid in enumerate(pmids, start=1):
            if pmid in records:
                f.write(json.dumps({"rank": rank, **records[pmid]}, ensure_ascii=False) + "\n")

    meta = {
        "review_pmid": args.review_pmid,
        "query": args.query,
        "query_translation": search.get("querytranslation", ""),
        "date_type": "pdat",
        "mindate": args.mindate,
        "maxdate": args.maxdate,
        "sort": "relevance",
        "retrieved_at": retrieved_at,
        "total_hits": int(search.get("count", 0)),
        "n_requested": args.n,
        "n_returned": len(pmids),
        "n_with_record": len(records),
        "n_with_abstract": sum(1 for r in records.values() if r["abstract"]),
        "missing_pmids": missing,
        "api_key_used": bool(os.environ.get("NCBI_API_KEY")),
        "pmids": pmids,
    }
    (out / "search.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"total_hits={meta['total_hits']} returned={meta['n_returned']} "
        f"with_abstract={meta['n_with_abstract']} -> {out}/"
    )


if __name__ == "__main__":
    main()
