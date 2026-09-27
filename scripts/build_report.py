"""Build the static HTML screening report (one file, no server) from results/.

Usage:
    python scripts/build_report.py --reviews reviews --results results --out results/report.html

Reads (see docs/schema.md):
    reviews/<rid>/criteria.json
    results/<rid>/candidates.json
    results/screen/{a,b}/<rid>/batch_*.json
    results/adjudication/<rid>.json      (optional)
    results/human/<rid>.json             (optional)
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from quote_match import locate_quote
from rules import VALID_VERDICTS, adjudicate, disagree_ids, overall, score


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_screener(results: Path, who: str, rid: str, warn: list) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for f in sorted((results / "screen" / who / rid).glob("batch_*.json")):
        data = load(f)
        for rec in data.get("records", []):
            pmid = str(rec.get("pmid"))
            if pmid in out:
                warn.append(["dup_batch", {"who": who, "pmid": pmid, "file": f.name}])
            out[pmid] = rec.get("criteria", [])
    return out


def pack_side(crit: list[dict] | None, ids: list[str], abstract: str, title: str, who: str, pmid: str, warn: list):
    if crit is None:
        return None
    seen = [c.get("id") for c in crit]
    for cid in ids:
        if seen.count(cid) != 1:
            warn.append(["crit_count", {"who": who, "pmid": pmid, "cid": cid, "n": seen.count(cid)}])
    for cid in set(seen) - set(ids):
        warn.append(["crit_unknown", {"who": who, "pmid": pmid, "cid": cid}])
    packed = {}
    for c in crit:
        v = c.get("verdict")
        if v not in VALID_VERDICTS:
            warn.append(["verdict_range", {"who": who, "pmid": pmid, "cid": c.get("id"), "v": v}])
        q = c.get("quote")
        loc = locate_quote(title, abstract, q) if q else None
        span = loc[1] if loc else None
        if v in (1, -1) and not q:
            warn.append(["quote_absent", {"who": who, "pmid": pmid, "cid": c.get("id")}])
        elif v in (1, -1) and span is None:
            warn.append(["quote_notfound", {"who": who, "pmid": pmid, "cid": c.get("id")}])
        packed[c.get("id")] = {"v": v, "q": q, "note": c.get("note"), "span": list(span) if span else None,
                               "src": loc[0] if loc else None}
    return {"crit": packed, "overall": overall(crit), "score": score(crit)}


def build_review(rid: str, reviews: Path, results: Path) -> dict:
    warn: list = []
    crit_doc = load(reviews / rid / "criteria.json")
    criteria = crit_doc["criteria"]
    ids = [c["id"] for c in criteria]
    cands = load(results / rid / "candidates.json")["records"]
    a = load_screener(results, "a", rid, warn)
    b = load_screener(results, "b", rid, warn)
    adj_path = results / "adjudication" / f"{rid}.json"
    adj = {str(r["pmid"]): r for r in load(adj_path)["records"]} if adj_path.exists() else {}
    if not adj_path.exists():
        warn.append(["no_adj", {}])
    hum_path = results / "human" / f"{rid}.json"
    human = {str(r["pmid"]): {"decision": r.get("decision"), "note": r.get("note", "")}
             for r in load(hum_path)["records"]} if hum_path.exists() else {}

    cand_ids = {str(c["pmid"]) for c in cands}
    for who, side in (("a", a), ("b", b)):
        for pmid in sorted(set(side) - cand_ids):
            warn.append(["unknown_pmid", {"who": who, "pmid": pmid}])

    records = []
    for c in sorted(cands, key=lambda r: r.get("rank", 0)):
        pmid = str(c["pmid"])
        abstract = c.get("abstract") or ""
        ca, cb = a.get(pmid), b.get(pmid)
        for who, side in (("a", ca), ("b", cb)):
            if side is None:
                warn.append(["missing_judgment", {"who": who, "pmid": pmid}])
        title = c.get("title", "")
        rule_status, rule_reasons = adjudicate(ca, cb, abstract, title)
        ad = adj.get(pmid)
        status = ad["status"] if ad else rule_status
        mismatch = bool(ad) and ad["status"] != rule_status
        if mismatch:
            warn.append(["adj_mismatch", {"pmid": pmid, "got": ad["status"], "rule": rule_status}])
        if ad and status == "needs_human" and not ad.get("summary"):
            warn.append(["adj_nosummary", {"pmid": pmid}])
        records.append({
            "pmid": pmid, "rank": c.get("rank"), "title": c.get("title", ""),
            "journal": c.get("journal"), "year": c.get("year"), "abstract": abstract,
            "a": pack_side(ca, ids, abstract, title, "a", pmid, warn),
            "b": pack_side(cb, ids, abstract, title, "b", pmid, warn),
            "status": status, "rule_status": rule_status, "mismatch": mismatch,
            "reasons": (ad or {}).get("reasons", rule_reasons),
            "disagree": (ad or {}).get("disagree_criteria", disagree_ids(ca, cb)),
            "summary": (ad or {}).get("summary"),
            "summary_en": (ad or {}).get("summary_en"),
        })
    return {"review_pmid": rid, "title": crit_doc.get("review_title", ""), "title_en": crit_doc.get("review_title_en"), "criteria": criteria,
            "records": records, "human": human, "warnings": warn}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviews", default="reviews")
    ap.add_argument("--results", default="results")
    ap.add_argument("--out", default="results/report.html")
    ap.add_argument("--label", default="", help="text shown next to the title, e.g. DUMMY DATA")
    args = ap.parse_args()
    reviews, results = Path(args.reviews), Path(args.results)
    rids = sorted(p.parent.name for p in reviews.glob("*/criteria.json")
                  if (results / p.parent.name / "candidates.json").exists())
    if not rids:
        sys.exit("criteria.json と candidates.json が揃ったレビューが無い")
    payload = {
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "label": args.label,
        "reviews": [build_review(r, reviews, results) for r in rids],
    }
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("__DATA__", data)
    for key, name in LOGOS.items():
        b64 = base64.b64encode((ASSETS / name).read_bytes()).decode()
        html = html.replace(key, f"data:image/png;base64,{b64}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    n = sum(len(r["records"]) for r in payload["reviews"])
    w = sum(len(r["warnings"]) for r in payload["reviews"])
    print(f"wrote {out} ({len(rids)} reviews, {n} records, {w} warnings)")


TEMPLATE = (Path(__file__).parent / "report_template.html").read_text(encoding="utf-8")
ASSETS = Path(__file__).parent / "assets"
LOGOS = {"__LOGO_NAV__": "hl-logo-yoko-white.png", "__LOGO_MARK__": "herzleben-logo.png",
         "__LOGO_MARK_WHITE__": "herzleben-logo-white.png"}

if __name__ == "__main__":
    main()
