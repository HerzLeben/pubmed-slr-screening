"""Score the extraction (指示書20 6章): compare the extractor's output with the benchmark answers.

Usage:
    python3 scripts/score_extraction.py                 # prints the counts and Accuracy, writes results/extraction/score.json

Reads (docs/schema.md 10章):
    results/extraction/jobs/<review>/<pmid>.json        the pairs to score (only those with a body text)
    results/extraction/out/<review>/<pmid>.json         the extractor's values
    bench/extraction/<review>.jsonl                     the answers
    results/extraction/human/<review>.json              the human's scores (optional; saved from the eval-3 report)

Rule (指示書20 6.1, changed by the human on 2026-10-01):
    exact match after trimming and lower-casing  -> correct (by rule)
    anything else, "記載なし" included             -> scored by the human in the report
The Accuracy without the pairs in REFERENCE_EXCLUDE is also given, as a reference only.
The Accuracy and its 95% CI (Wilson) are the same calculation as scripts/extraction_metrics.js.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from quote_match import find_quote

NOT_FOUND = "記載なし"
REVIEWS = ("33746596", "37168849")
EXPECTED_TOTAL = 102
# the answer looks wrong (in vitro study, no patients; 2026-10-01 human). Main values keep all 102 items
REFERENCE_EXCLUDE = ("37168849/33495835",)
Z = 1.959963984540054
CONTEXT = 160


def norm(s) -> str:
    return str(s if s is not None else "").strip().lower()


def auto_score(answer: str, value: str) -> str | None:
    """"correct" for an exact match, else None (the human scores it; "記載なし" too)."""
    return "correct" if norm(value) == norm(answer) else None


def quote_contexts(text: str, quotes: list[str], width: int = CONTEXT) -> list[dict]:
    """Each quote with the text around it, so the human can see where in the full text it is."""
    out = []
    for q in quotes:
        span = find_quote(text, q)
        if not span:
            out.append({"q": q, "nf": True})
            continue
        s, e = span
        out.append({"before": ("…" if s > width else "") + text[max(0, s - width):s], "match": text[s:e],
                    "after": text[e:e + width] + ("…" if e + width < len(text) else "")})
    return out


def load_items(root: Path, reviews=REVIEWS, with_context: bool = False) -> list[dict]:
    items = []
    for rid in reviews:
        answers = {}
        for line in (root / "bench" / "extraction" / f"{rid}.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                answers[str(row["pmid"])] = row
        for job_path in sorted((root / "results" / "extraction" / "jobs" / rid).glob("*.json")):
            job = json.loads(job_path.read_text(encoding="utf-8"))
            pmid = str(job["pmid"])
            out_path = root / job["output"]
            if not out_path.exists():
                sys.exit(f"出力が無い: {job['output']}")
            out = {it["name"]: it for it in json.loads(out_path.read_text(encoding="utf-8"))["items"]}
            if pmid not in answers:
                sys.exit(f"答えに PMID {pmid} が無い: bench/extraction/{rid}.jsonl")
            text = (root / job["fulltext"]).read_text(encoding="utf-8") if with_context else ""
            for name in job["items"]:
                if name not in answers[pmid] or name not in out:
                    sys.exit(f"{rid}/{pmid}: 項目 {name!r} が答えか出力に無い")
                answer, value = answers[pmid][name], out[name]["value"]
                quotes = out[name].get("quotes") or []
                it = {"review": rid, "pmid": pmid, "name": name, "answer": answer, "value": value,
                      "quotes": quotes, "auto": auto_score(answer, value)}
                if with_context:
                    it["ctx"] = quote_contexts(text, quotes)
                items.append(it)
    return items


def load_human(root: Path, items: list[dict], reviews=REVIEWS) -> dict[str, dict[str, bool]]:
    """{review: {"<pmid>\\t<item>": True/False}} from results/extraction/human/<review>.json."""
    open_keys = {(it["review"], f"{it['pmid']}\t{it['name']}") for it in items if it["auto"] is None}
    human: dict[str, dict[str, bool]] = {}
    for rid in reviews:
        path = root / "results" / "extraction" / "human" / f"{rid}.json"
        if not path.exists():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        if str(doc.get("review_pmid")) != rid:
            sys.exit(f"{path}: review_pmid が {doc.get('review_pmid')!r}")
        got = {}
        for r in doc.get("records", []):
            key = f"{r['pmid']}\t{r['item']}"
            if (rid, key) not in open_keys:
                sys.exit(f"{path}: 人が採点する項目ではない: {r['pmid']} / {r['item']}")
            if not isinstance(r.get("correct"), bool):
                sys.exit(f"{path}: correct は true か false: {r['pmid']} / {r['item']}")
            got[key] = r["correct"]
        human[rid] = got
    return human


def wilson(k: int, n: int) -> tuple[float | None, float | None]:
    if not n:
        return None, None
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return c - h, c + h


def metrics(items: list[dict], human: dict) -> dict:
    """Same as extractionMetrics() in extraction_metrics.js."""
    def blank():
        return {"total": 0, "scored": 0, "correct": 0, "pending": 0, "rule_correct": 0,
                "human_correct": 0, "human_wrong": 0}

    out = {"overall": blank(), "by_review": {}, "by_pair": {}}
    for it in items:
        h = human.get(it["review"], {}).get(f"{it['pmid']}\t{it['name']}")
        pair = f"{it['review']}/{it['pmid']}"
        rv = out["by_review"].setdefault(it["review"], blank())
        pr = out["by_pair"].setdefault(pair, blank())
        for m in (out["overall"], rv, pr):
            m["total"] += 1
            if it["auto"] == "correct":
                m["scored"] += 1
                m["correct"] += 1
                m["rule_correct"] += 1
            elif h is True:
                m["scored"] += 1
                m["correct"] += 1
                m["human_correct"] += 1
            elif h is False:
                m["scored"] += 1
                m["human_wrong"] += 1
            else:
                m["pending"] += 1
    for m in [out["overall"], *out["by_review"].values(), *out["by_pair"].values()]:
        m["accuracy"] = m["correct"] / m["scored"] if m["scored"] else None
        m["ci_low"], m["ci_high"] = wilson(m["correct"], m["scored"])
    return out


def fmt(m: dict) -> str:
    acc = "—" if m["accuracy"] is None else f"{m['accuracy']:.3f} (95% CI {m['ci_low']:.3f}–{m['ci_high']:.3f})"
    return (f"{acc}  correct {m['correct']}/{m['scored']}, pending {m['pending']} "
            f"[rule ✓{m['rule_correct']}, human ✓{m['human_correct']} ✗{m['human_wrong']}]")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="results/extraction/score.json")
    args = ap.parse_args()
    root = Path(args.root)
    if not (root / "results" / "extraction" / "jobs").exists():
        sys.exit("results/extraction/jobs/ が無い。results/ は commit されない。CLAUDE.md の「データの流れ」の順に作る（抽出は docs/schema.md 10章）")
    items = load_items(root)
    if len(items) != EXPECTED_TOTAL:
        sys.exit(f"分母が {len(items)}（{EXPECTED_TOTAL} のはず）")
    human = load_human(root, items)
    m = metrics(items, human)
    ref = metrics([it for it in items if f"{it['review']}/{it['pmid']}" not in REFERENCE_EXCLUDE], human)
    m["reference_without"] = {"pairs": list(REFERENCE_EXCLUDE), "overall": ref["overall"], "by_review": ref["by_review"]}
    print("overall  ", fmt(m["overall"]))
    for k, v in m["by_review"].items():
        print("review   ", k, fmt(v))
    for k, v in m["by_pair"].items():
        print("pair     ", k, fmt(v))
    print("reference without", ", ".join(REFERENCE_EXCLUDE), fmt(ref["overall"]))
    for k, v in ref["by_review"].items():
        print("reference review ", k, fmt(v))
    out = root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
