"""PMC XML -> text for the extractor (scripts/fulltext_to_text.py, no network)."""



from fulltext_to_text import convert

XML = """<?xml version="1.0"?>
<pmc-articleset><article>
<front><article-meta><title-group><article-title>A CAR-T trial</article-title></title-group>
<abstract><sec><title>Methods</title><p>We enrolled patients.</p></sec></abstract></article-meta></front>
<body>
<p>Opening paragraph <xref ref-type="bibr">1</xref>.</p>
<sec><title>Patients</title><p>Doses were 50&#215;10<sup>6</sup> cells.<table-wrap id="t1"><label>Table 1</label>
<caption><p>Inside body</p></caption><table><tr><td>Age</td><td>60</td></tr></table></table-wrap></p>
<sec><title>Subgroup</title><p>Nested text.</p></sec></sec>
<sec><title>Supplementary Material</title><supplementary-material><caption><p>Supp table</p></caption>
</supplementary-material></sec>
</body>
<back><ack><p>We thank everyone.</p></ack>
<ref-list><ref><mixed-citation>Smith J. A cited paper. 2010.</mixed-citation></ref></ref-list></back>
<floats-group><table-wrap id="t2"><label>Table 2</label><caption><p>Baseline characteristics</p></caption>
<table><thead><tr><th>Characteristic</th><th>Total (N = 33)</th></tr></thead>
<tbody><tr><td>Median age (range)</td><td>60 (37&#8211;75)</td></tr></tbody></table>
<table-wrap-foot><fn><p>BCMA denotes B-cell maturation antigen.</p></fn></table-wrap-foot></table-wrap>
<fig id="f1"><label>Figure 1</label><caption><p>Study flow</p></caption></fig></floats-group>
</article></pmc-articleset>"""


def test_floats_group_table_is_included():
    text, summary = convert(XML)
    assert "Table 2 Baseline characteristics" in text
    assert "Characteristic\tTotal (N = 33)" in text
    assert "Median age (range)\t60 (37–75)" in text
    assert "BCMA denotes B-cell maturation antigen." in text
    assert summary["tables"] == 2
    assert summary["tables_in_body"] == 1


def test_body_table_written_once_after_body():
    text, _ = convert(XML)
    assert text.count("Inside body") == 1
    assert text.index("Nested text.") < text.index("## Tables") < text.index("Table 1 Inside body")


def test_references_and_back_matter_are_left_out():
    text, summary = convert(XML)
    assert "A cited paper" not in text
    assert "We thank everyone" not in text
    assert "Supp table" not in text
    assert summary["supplementary"] == 1


def test_headings_are_one_line_with_hashes():
    text, _ = convert(XML)
    lines = text.splitlines()
    assert lines[0] == "# A CAR-T trial"
    for h in ("## Abstract", "## Methods", "## Patients", "## Subgroup", "## Tables", "## Figures"):
        assert h in lines
    assert "## Supplementary Material" not in lines  # section with nothing but supplementary material


def test_figure_caption_and_powers():
    text, summary = convert(XML)
    assert "Figure 1 Study flow" in text
    assert "50×10^6 cells" in text
    assert "Opening paragraph 1." in text  # a citation number after a word is not a power
    assert summary["figures"] == 1


def test_long_paragraph_wrapped_at_sentence_ends():
    from fulltext_to_text import wrap
    from quote_match import find_quote

    para = " ".join(f"Sentence number {i} says something about CAR-T cells." for i in range(60))
    out = wrap(para, width=200)
    assert all(len(line) <= 200 for line in out.splitlines())
    assert all(line.endswith(".") for line in out.splitlines())
    # a quote that crosses a line break still matches (quote_match folds whitespace)
    assert find_quote(out, "about CAR-T cells. Sentence number 4 says")
