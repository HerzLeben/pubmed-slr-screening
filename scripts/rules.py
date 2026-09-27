"""Screening rules shared by build_report.py, the adjudicator check and eval.

See docs/schema.md. Verdicts: 1 = toward inclusion, -1 = toward exclusion,
0 = unclear (treated as toward inclusion). This holds for exclusion criteria too.
"""

from __future__ import annotations

from quote_match import quote_exists

VALID_VERDICTS = (-1, 0, 1)


def score(criteria: list[dict]) -> int:
    """Sum of verdicts. Used for ranking (Recall@k)."""
    return sum(int(c.get("verdict", 0)) for c in criteria)


def overall(criteria: list[dict]) -> str:
    """exclude if any criterion is -1, else include (0 falls to include)."""
    return "exclude" if any(c.get("verdict") == -1 for c in criteria) else "include"


def quotes_ok(criteria: list[dict], abstract: str, title: str = "") -> bool:
    """Every +/-1 verdict has a quote that exists verbatim in the title or abstract."""
    for c in criteria:
        if c.get("verdict") in (1, -1) and not quote_exists(title, abstract, c.get("quote")):
            return False
    return True


def disagree_ids(a: list[dict] | None, b: list[dict] | None) -> list[str]:
    if a is None or b is None:
        return []
    va = {c["id"]: c.get("verdict") for c in a}
    vb = {c["id"]: c.get("verdict") for c in b}
    return sorted(k for k in set(va) | set(vb) if va.get(k) != vb.get(k))


def adjudicate(a: list[dict] | None, b: list[dict] | None, abstract: str, title: str = "") -> tuple[str, list[str]]:
    """Return (status, reasons) by the ordered rules in docs/schema.md section 6."""
    if a is None or b is None:
        return "needs_human", ["missing_record"]
    reasons: list[str] = []
    if not (quotes_ok(a, abstract, title) and quotes_ok(b, abstract, title)):
        return "needs_human", ["quote_missing"] + (["overall_disagree"] if overall(a) != overall(b) else [])
    if overall(a) != overall(b):
        reasons.append("overall_disagree")
        if disagree_ids(a, b):
            reasons.append("criterion_disagree")
        return "needs_human", reasons
    if disagree_ids(a, b):
        reasons.append("criterion_disagree")
    return f"agreed_{overall(a)}", reasons
