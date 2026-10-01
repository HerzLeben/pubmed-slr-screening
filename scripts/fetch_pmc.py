"""Fetch PMC full text (JATS XML) for PMIDs and record whether a body is available.

PMID -> PMCID (elink, linkname=pubmed_pmc) -> efetch (db=pmc, rettype=xml) -> results/fulltext/<PMID>.xml.
results/fulltext/status.json gets one entry per PMID:
  no_pmc       no PMC record is linked to the PMID
  pmc_no_body  a PMC record exists but its XML has no <body> (e.g. author manuscript withheld by the publisher)
  body         the XML has a <body>; this is the full text the extractor may read

Only PMC is used, as in the original TrialMind ("restricted to publicly available sources from PubMed Central").
The request interval and the handling of NCBI_API_KEY / NCBI_EMAIL are those of fetch_pubmed.py (POST only,
the key is never printed or written).

Example:
  python3 scripts/fetch_pmc.py --from-extraction 33746596 37168849
  python3 scripts/fetch_pmc.py --pmids 29669947
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_pubmed import post
from make_extraction_jobs import read_pmids

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "fulltext"
EXTRACTION = ROOT / "bench" / "extraction"


def elink_pmc(pmid: str) -> list[str]:
    """PMC ids (numbers, without the "PMC" prefix) linked to a PMID."""
    body = post("elink.fcgi", {"dbfrom": "pubmed", "db": "pmc", "linkname": "pubmed_pmc",
                               "id": pmid, "retmode": "json"})
    ids = []
    for ls in json.loads(body).get("linksets", []):
        for db in ls.get("linksetdbs", []):
            if db.get("linkname") == "pubmed_pmc":
                ids.extend(str(i) for i in db.get("links", []))
    return ids


def efetch_pmc(pmcid: str) -> bytes:
    return post("efetch.fcgi", {"db": "pmc", "id": pmcid, "rettype": "xml"})


def classify(xml: bytes | None) -> str:
    """Status for one PMID from the efetch XML (None when no PMC record is linked)."""
    if xml is None:
        return "no_pmc"
    root = ET.fromstring(xml)
    body = root.find(".//article/body") if root.tag != "article" else root.find("body")
    if body is None or not "".join(body.itertext()).strip():
        return "pmc_no_body"
    return "body"


def fetch_one(pmid: str, out: Path) -> dict:
    pmcids = elink_pmc(pmid)
    if not pmcids:
        return {"pmid": pmid, "pmcid": None, "status": classify(None)}
    pmcid = pmcids[0]
    xml = efetch_pmc(pmcid)
    (out / f"{pmid}.xml").write_bytes(xml)
    return {"pmid": pmid, "pmcid": f"PMC{pmcid}", "status": classify(xml), "n_pmc_links": len(pmcids)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-extraction", nargs="*", default=[], metavar="REVIEW",
                    help="review PMIDs; fetch every study PMID of bench/extraction/<REVIEW>.jsonl")
    ap.add_argument("--pmids", nargs="*", default=[], help="extra study PMIDs to check")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env", override=False)
    OUT.mkdir(parents=True, exist_ok=True)
    status_path = OUT / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {"studies": {}}

    wanted: dict[str, list[str]] = {}
    for review in args.from_extraction:
        for p in read_pmids(EXTRACTION / f"{review}.jsonl"):
            wanted.setdefault(p, []).append(review)
    for p in args.pmids:
        wanted.setdefault(p, [])

    for pmid, reviews in wanted.items():
        rec = fetch_one(pmid, OUT)
        prev = status["studies"].get(pmid, {})
        rec["reviews"] = sorted(set(prev.get("reviews", [])) | set(reviews))
        status["studies"][pmid] = rec
        print(f"{pmid}\t{rec['pmcid'] or '-'}\t{rec['status']}")

    status["fetched_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
