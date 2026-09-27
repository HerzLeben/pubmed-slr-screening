"""Quote matching shared by the SubagentStop hook, adjudicate.py and build_report.py.

Rule (one definition for all): a quote "exists" when, after normalizing both
sides, it appears as one contiguous, case-sensitive substring of the TITLE or
the ABSTRACT of the candidate. No ellipsis, no paraphrase, no shortening.

Normalization (applied to quote, title and abstract alike):
  1. Unicode NFKC, character by character
  2. hyphen / dash variants (U+2010-2015, U+2212, U+FE58, U+FE63, U+FF0D, U+00AD removed) -> "-"
  3. every run of whitespace (incl. NBSP, thin space) -> one space; trimmed
Decided 2026-09-27 after the no-subagent trial (5 of 9 misses were hyphen/space only).
"""

from __future__ import annotations

import unicodedata

_DASHES = {c: "-" for c in "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d"}
_DROP = {"\u00ad", "\u200b", "\u200c", "\u200d", "\ufeff"}  # soft hyphen, zero-width chars, BOM


def _norm_char(ch: str) -> str:
    if ch in _DROP:
        return ""
    ch = unicodedata.normalize("NFKC", ch)
    return "".join(_DASHES.get(c, c) for c in ch)


def _normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Normalized text and, for each output char, its index in the original text."""
    out: list[str] = []
    idx: list[int] = []
    prev_space = True  # drop leading whitespace
    for i, raw in enumerate(text):
        for ch in _norm_char(raw):
            if ch.isspace():
                if prev_space:
                    continue
                out.append(" ")
                idx.append(i)
                prev_space = True
            else:
                out.append(ch)
                idx.append(i)
                prev_space = False
    if out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


def normalize(text: str) -> str:
    return _normalize_with_map(text or "")[0]


def find_quote(text: str, quote: str | None) -> tuple[int, int] | None:
    """(start, end) of the quote in the ORIGINAL text, or None."""
    if not text or not quote:
        return None
    q = normalize(quote)
    if not q:
        return None
    norm, idx = _normalize_with_map(text)
    pos = norm.find(q)
    if pos < 0:
        return None
    return idx[pos], idx[pos + len(q) - 1] + 1


def locate_quote(title: str, abstract: str, quote: str | None) -> tuple[str, tuple[int, int]] | None:
    """Where the quote is: ("abstract", span) first, else ("title", span), else None."""
    span = find_quote(abstract, quote)
    if span:
        return "abstract", span
    span = find_quote(title, quote)
    if span:
        return "title", span
    return None


def quote_exists(title: str, abstract: str, quote: str | None) -> bool:
    return locate_quote(title, abstract, quote) is not None
