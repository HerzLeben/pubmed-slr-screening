"""Public sample of the report (build_report.py --public): abstracts and verbatim quotes are hidden. No network."""

import json

from build_report import hide_quoted, make_public

ABSTRACT = "We treated 20 patients with relapsed lymphoma using CD19 CAR-T cells. The response rate was 60%."
QUOTE = "We treated 20 patients with relapsed lymphoma"


def payload():
    side = {"crit": {"I1": {"v": 1, "q": QUOTE, "span": [0, 46], "src": "abstract", "note": None},
                     "I2": {"v": -1, "q": "not in the abstract at all", "span": None, "src": None, "note": None},
                     "E1": {"v": 0, "q": None, "span": None, "src": None, "note": None}},
            "overall": "include", "score": 0}
    rec = {"pmid": "1", "title": "CD19 CAR T cells in lymphoma", "abstract": ABSTRACT, "a": side,
           "b": json.loads(json.dumps(side)), "status": "needs_human",
           "summary": f"Aは「{QUOTE}」を引用した", "summary_en": f"A cited '{QUOTE}' and B's verdict was 0"}
    return {"reviews": [{"review_pmid": "9", "records": [rec], "warnings": [["x", {}]]}],
            "extraction": {"items": [{"review": "9", "pmid": "1", "name": "Sample size", "answer": "20",
                                      "value": "20", "quotes": [QUOTE], "ctx": [{"before": "", "match": QUOTE,
                                                                                 "after": ""}], "auto": "correct"}]}}


def test_hides_abstract_and_quotes_but_keeps_the_rest():
    out = make_public(payload())
    text = json.dumps(out, ensure_ascii=False)
    assert QUOTE not in text and "relapsed lymphoma using" not in text and "not in the abstract" not in text
    r = out["reviews"][0]["records"][0]
    assert out["public"] is True and r["has_abstract"] is True and r["abstract"] == ""
    assert r["title"] == "CD19 CAR T cells in lymphoma"
    c = r["a"]["crit"]
    assert (c["I1"]["v"], c["I1"]["qlen"], c["I1"]["nf"]) == (1, len(QUOTE), False)
    assert c["I2"]["nf"] is True and c["E1"]["qlen"] == 0
    assert r["summary"] == f"Aは「引用・{len(QUOTE)}字」を引用した"
    assert r["summary_en"] == f"A cited 「引用・{len(QUOTE)}字」 and B's verdict was 0"
    it = out["extraction"]["items"][0]
    assert (it["value"], it["answer"], it["qcount"], it["quotes"], it["ctx"]) == ("20", "20", 1, [], [])


def test_hide_quoted_leaves_apostrophes_and_short_quotes():
    assert hide_quoted("A's and B's verdicts differ; it's 'short' here") == "A's and B's verdicts differ; it's 'short' here"
    assert hide_quoted(None) is None
