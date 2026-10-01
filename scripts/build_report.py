"""Build the static HTML screening report (one file, no server) from results/.

Usage:
    python scripts/build_report.py --reviews reviews --results results --out results/report.html

Reads (see docs/schema.md):
    reviews/<rid>/criteria.json
    results/<rid>/candidates.json
    results/screen/{a,b}/<rid>/batch_*.json
    results/adjudication/<rid>.json      (optional)
    results/human/<rid>.json             (optional)

eval-3 (--run eval-3, docs/eval/eval-3.md): screener-a only, no adjudication and no human judgment.
    python scripts/build_report.py --run eval-3        # -> results/eval-3/report.html
Uses the <head> (CSS) and header of report_template.html and the body in report_eval3_body.html.
Reads reviews/<rid>/eval-3/{criteria,search}.json, results/eval-3/<rid>/candidates.json,
results/eval-3/screen/a/<rid>/batch_*.json, and the metrics from eval_screening.run_eval3.
The 抽出 section (the human scores the extraction there) uses score_extraction.load_items/load_human and
inlines extraction_metrics.js; it saves results/extraction/human/<review>.json.
The results/report.html of eval-1/eval-2 is not touched.
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


def build_review_eval3(rid: str, included: list[str], title: dict, reviews: Path, results: Path) -> dict:
    from eval_screening import run_eval3

    warn: list = []
    crit_doc = load(reviews / rid / "eval-3" / "criteria.json")
    ids = [c["id"] for c in crit_doc["criteria"]]
    search = load(reviews / rid / "eval-3" / "search.json")
    cands = {str(c["pmid"]): c for c in load(results / rid / "candidates.json")["records"]}
    a = load_screener(results, "a", rid, warn)
    ev = run_eval3(rid, included, reviews, results)
    inc, added = {str(p) for p in included}, set(ev["added_pmids"])
    order = sorted(cands, key=lambda p: (-score(a[p]), cands[p]["rank"]))
    records = []
    for i, pmid in enumerate(order, 1):
        c = cands[pmid]
        abstract, ttl = c.get("abstract") or "", c.get("title", "")
        records.append({"pmid": pmid, "position": i, "rank": c.get("rank"), "title": ttl,
                        "journal": c.get("journal"), "year": c.get("year"), "abstract": abstract,
                        "included": pmid in inc, "added": pmid in added,
                        "a": pack_side(a.get(pmid), ids, abstract, ttl, "a", pmid, warn)})
    return {"review_pmid": rid, "title": title.get("ja", ""), "title_en": title.get("en"),
            "criteria": crit_doc["criteria"], "query": search.get("query", ""), "eval": ev,
            "records": records, "warnings": warn}


def build_extraction(root: Path) -> dict | None:
    """Items to score in the report's 抽出 section (score_extraction.py), or None before the extraction ran."""
    from score_extraction import REFERENCE_EXCLUDE, REVIEWS, load_human, load_items

    if not (root / "results" / "extraction" / "out").exists():
        return None
    items = load_items(root, with_context=True)
    status = load(root / "results" / "fulltext" / "status.json")["studies"]
    breakdown = {}
    for rid in REVIEWS:
        rows = [json.loads(x) for x in (root / "bench" / "extraction" / f"{rid}.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
        st = {str(r["pmid"]): status.get(str(r["pmid"]), {}).get("status", "no_pmc") for r in rows}
        breakdown[rid] = {k: [p for p, v in st.items() if v == k] for k in ("body", "pmc_no_body", "no_pmc")}
    return {"reviews": list(REVIEWS), "items": items, "human": load_human(root, items),
            "reference_exclude": list(REFERENCE_EXCLUDE), "breakdown": breakdown}


def main_eval3(args) -> None:
    reviews = Path(args.reviews)
    results = Path(args.results or "results/eval-3")
    if not results.exists():
        sys.exit(f"{results}/ が無い。results/ は commit されない。CLAUDE.md の「データの流れ」の順に作る")
    out = Path(args.out or "results/eval-3/report.html")
    bench = [json.loads(x) for x in Path("bench/reviews.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    rvs = []
    for row in sorted(bench, key=lambda r: str(r["PMID"])):
        rid = str(row["PMID"])
        old = reviews / rid / "criteria.json"
        doc = load(old) if old.exists() else {}
        rvs.append(build_review_eval3(rid, row["included_pmids"],
                                      {"ja": doc.get("review_title", ""), "en": doc.get("review_title_en")},
                                      reviews, results))
    payload = {"generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "run": "eval-3",
               "reviews": rvs, "extraction": build_extraction(Path("."))}
    head = TEMPLATE[: TEMPLATE.index('<p class="scope"')] + '<p class="scope" data-t="hdr.scope"></p>\n'
    body = (Path(__file__).parent / "report_eval3_body.html").read_text(encoding="utf-8")
    body = body.replace("__EXTRACTION_METRICS_JS__", (Path(__file__).parent / "extraction_metrics.js").read_text(encoding="utf-8"))
    html = head + body.replace("__DATA__", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"))
    for key, name in LOGOS.items():
        html = html.replace(key, "data:image/png;base64," + base64.b64encode((ASSETS / name).read_bytes()).decode())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    n = sum(len(r["records"]) for r in rvs)
    w = sum(len(r["warnings"]) for r in rvs)
    for r in rvs:
        for x in r["warnings"]:
            print("warning", r["review_pmid"], x, file=sys.stderr)
    print(f"wrote {out} ({len(rvs)} reviews, {n} records, {w} warnings)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviews", default="reviews")
    ap.add_argument("--results", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--run", default=None, choices=["eval-3"], help="eval-3: A only, writes results/eval-3/report.html")
    ap.add_argument("--label", default="", help="text shown next to the title, e.g. DUMMY DATA")
    args = ap.parse_args()
    if args.run == "eval-3":
        main_eval3(args)
        return
    args.results = args.results or "results"
    args.out = args.out or "results/report.html"
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
