"""scripts/quote_match.py and scripts/rules.py (docs/schema.md sections 3, 5, 6). No network."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from quote_match import locate_quote, normalize, quote_exists
from rules import adjudicate, disagree_ids, overall, score

ABSTRACT = "We treated 20 patients with relapsed B‑cell lymphoma using CD19 CAR‑T  cells."
TITLE = "A phase 1 trial of CD19 CAR-T cells"


@pytest.mark.parametrize("quote", [
    "relapsed B-cell lymphoma",     # U+2011 in the abstract, plain hyphen in the quote
    "using CD19 CAR-T cells",        # NBSP and a double space in the abstract
    "We treated 20 patients",
])
def test_quote_found_after_normalizing(quote):
    assert locate_quote(TITLE, ABSTRACT, quote)[0] == "abstract"


def test_quote_from_title():
    assert locate_quote(TITLE, ABSTRACT, "A phase 1 trial")[0] == "title"
    assert locate_quote(TITLE, "", "A phase 1 trial")[0] == "title"


@pytest.mark.parametrize("quote", [
    "twenty patients",               # paraphrase
    "we treated 20 patients",        # case differs
    "20 patients ... lymphoma",      # ellipsis
    "CAR-T cells in lymphoma",       # words from two places
    "",
    None,
])
def test_quote_not_found(quote):
    assert not quote_exists(TITLE, ABSTRACT, quote)


def test_span_points_into_the_original_text():
    where, (start, end) = locate_quote(TITLE, ABSTRACT, "B-cell lymphoma")
    assert where == "abstract"
    assert ABSTRACT[start:end] == "B‑cell lymphoma"


def test_normalize_drops_soft_hyphen_and_folds_space():
    assert normalize("CAR­T   cells—x") == "CART cells-x"


def crit(**verdicts):
    return [{"id": k, "verdict": v, "quote": "We treated 20 patients" if v else None} for k, v in verdicts.items()]


def test_overall_and_score():
    assert overall(crit(I1=1, I2=0, E1=1)) == "include"  # 0 falls to include
    assert overall(crit(I1=1, I2=0, E1=-1)) == "exclude"
    assert score(crit(I1=1, I2=0, E1=-1)) == 0


def test_adjudicate_order_of_rules():
    a, b = crit(I1=1, E1=1), crit(I1=1, E1=-1)
    assert adjudicate(a, None, ABSTRACT, TITLE) == ("needs_human", ["missing_record"])
    assert adjudicate(a, b, ABSTRACT, TITLE) == ("needs_human", ["overall_disagree", "criterion_disagree"])
    assert adjudicate(a, crit(I1=0, E1=1), ABSTRACT, TITLE) == ("agreed_include", ["criterion_disagree"])
    assert adjudicate(crit(I1=-1, E1=1), crit(I1=-1, E1=1), ABSTRACT, TITLE) == ("agreed_exclude", [])
    bad = [{"id": "I1", "verdict": 1, "quote": "not in the text"}]
    assert adjudicate(bad, bad, ABSTRACT, TITLE)[1][0] == "quote_missing"
    assert disagree_ids(a, b) == ["E1"]
