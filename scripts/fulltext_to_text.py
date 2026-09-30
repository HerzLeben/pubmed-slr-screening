"""Turn PMC full text (JATS XML) into the plain text the extractor reads.

results/fulltext/<PMID>.xml -> results/fulltext/<PMID>.txt (gitignored, like the XML), for every PMID whose
status.json entry is "body". Also writes results/fulltext/text_summary.json (counts per PMID).

What goes in (DECISIONS 2026-10-01 指示書20):
  - title, abstract, and every <sec> of <body>; each section title becomes one line starting with "## "
  - EVERY <table-wrap> in the article, wherever it sits (<body>, <floats-group>, <back>): label, caption,
    one line per row with cells separated by tabs, and <table-wrap-foot>
  - the label and caption of every <fig>
What stays out: the reference list (<ref-list>), back matter (acknowledgements, notes), and supplementary
material (<supplementary-material> is not fetched; only its count is recorded).
Why: the original feeds "the full content of the study documents in PDF or XML formats"; in PMC XML most
tables sit outside <body> (4 of the 10 tables of the 6 full texts are inside), so <body> alone drops the
patient characteristics tables.

Tables and figures are written after the body, in document order, so a table inside <body> is not
written twice.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FULLTEXT = ROOT / "results" / "fulltext"

# Elements whose text is never part of a paragraph: written elsewhere (tables, figures) or left out.
SKIP = {"table-wrap", "fig", "supplementary-material", "ref-list", "table-wrap-group", "fig-group"}
BLOCKS = {"p", "list", "disp-quote", "boxed-text", "def-list", "statement", "disp-formula"}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def is_power(before: str, sup: str) -> bool:
    """10<sup>6</sup> -> "10^6", so a dose is not read as "106". Footnote marks and citation numbers after
    a word stay as they were."""
    return bool(re.search(r"\d$", before)) and bool(re.match(r"\s*[-\u2212\u2013]?\d", sup))


def inline_text(el: ET.Element) -> str:
    """Text of an element and its children, without tables, figures and supplementary material."""
    parts: list[str] = []

    def walk(e: ET.Element) -> None:
        if e.tag in SKIP:
            if e.tail:
                parts.append(e.tail)
            return
        if e.tag == "sup" and is_power("".join(parts), "".join(e.itertext())):
            parts.append("^")
        if e.text:
            parts.append(e.text)
        for c in e:
            walk(c)
        if e.tail:
            parts.append(e.tail)

    if el.text:
        parts.append(el.text)
    for c in el:
        walk(c)
    return clean("".join(parts))


def section_lines(el: ET.Element) -> list[str]:
    """Paragraph blocks of a <body>, <abstract> or <sec>; <title> of a <sec> becomes '## <title>'."""
    out: list[str] = []
    for c in el:
        if c.tag in SKIP:
            continue
        if c.tag == "sec":
            inner = section_lines(c)
            if not inner:
                continue  # e.g. a section holding only supplementary material
            title = c.find("title")
            if title is not None and inline_text(title):
                out.append("## " + inline_text(title))
            out += inner
        elif c.tag == "title":
            continue  # the <sec> branch above writes it
        elif c.tag in BLOCKS:
            text = inline_text(c)
            if text:
                out.append(text)
        else:
            # anything else with text (e.g. a bare <label>) is kept as a line; containers are walked
            if len(c):
                out += section_lines(c)
            else:
                text = inline_text(c)
                if text:
                    out.append(text)
    return out


def table_lines(tw: ET.Element) -> list[str]:
    label = inline_text(tw.find("label")) if tw.find("label") is not None else ""
    caption = inline_text(tw.find("caption")) if tw.find("caption") is not None else ""
    out = [" ".join(x for x in (label, caption) if x) or "Table"]
    for tr in tw.iter("tr"):
        cells = [inline_text(c) for c in tr if c.tag in ("th", "td")]
        if any(cells):
            out.append("\t".join(cells))
    foot = tw.find("table-wrap-foot")
    if foot is not None:
        out += section_lines(foot) or ([inline_text(foot)] if inline_text(foot) else [])
    return out


def fig_lines(fig: ET.Element) -> list[str]:
    label = inline_text(fig.find("label")) if fig.find("label") is not None else ""
    caption = inline_text(fig.find("caption")) if fig.find("caption") is not None else ""
    text = " ".join(x for x in (label, caption) if x)
    return [text] if text else []


def outside_refs(root: ET.Element, tag: str) -> list[ET.Element]:
    """All <tag> elements in document order, except those inside a reference list or supplementary material."""
    found: list[ET.Element] = []

    def walk(e: ET.Element) -> None:
        if e.tag in ("ref-list", "supplementary-material"):
            return
        if e.tag == tag:
            found.append(e)
        for c in e:
            walk(c)

    walk(root)
    return found


def convert(xml_text: str) -> tuple[str, dict]:
    root = ET.fromstring(xml_text)
    article = root if root.tag == "article" else root.find(".//article")
    if article is None:
        raise ValueError("no <article>")
    meta = article.find("front/article-meta")
    body = article.find("body")
    blocks: list[str] = []

    title = meta.find("title-group/article-title") if meta is not None else None
    if title is not None:
        blocks.append("# " + inline_text(title))
    for ab in (meta.findall("abstract") if meta is not None else []):
        if ab.get("abstract-type") in ("graphical", "teaser"):
            continue
        blocks.append("## Abstract")
        blocks += section_lines(ab)
    if body is not None:
        blocks += section_lines(body)

    tables = outside_refs(article, "table-wrap")
    figs = outside_refs(article, "fig")
    if tables:
        blocks.append("## Tables")
        for tw in tables:
            blocks.append("\n".join(table_lines(tw)))
    if figs:
        blocks.append("## Figures")
        for f in figs:
            blocks += fig_lines(f)

    in_body = len(body.findall(".//table-wrap")) if body is not None else 0
    summary = {
        "chars": 0,
        "tables": len(tables),
        "tables_in_body": in_body,
        "figures": len(figs),
        "supplementary": len(article.findall(".//supplementary-material")),
    }
    text = "\n\n".join(blocks) + "\n"
    summary["chars"] = len(text)
    return text, summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", type=Path, default=FULLTEXT)
    args = ap.parse_args(argv)
    status = json.loads((args.dir / "status.json").read_text(encoding="utf-8"))["studies"]
    pmids = sorted(p for p, v in status.items() if v.get("status") == "body")
    summary = {}
    for pmid in pmids:
        text, s = convert((args.dir / f"{pmid}.xml").read_text(encoding="utf-8"))
        (args.dir / f"{pmid}.txt").write_text(text, encoding="utf-8")
        summary[pmid] = s
        print(f"{pmid}: {s['chars']:,} chars, tables {s['tables']} (in body {s['tables_in_body']}), "
              f"figures {s['figures']}, supplementary {s['supplementary']} (not fetched)")
    (args.dir / "text_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
