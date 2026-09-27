"""Date handling in scripts/fetch_pubmed.py (no network)."""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from fetch_pubmed import date_range, month_end, vs_cap

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
