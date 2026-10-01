#!/usr/bin/env python3
"""Check extractor output against docs/schema.md section 10 (a separate file from check_screen_output.py).

Wired in .claude/settings.json for two events:

PreToolUse (matcher Write) -- the send-back. Exit 2 blocks the Write and the subagent receives stderr and keeps
  working (https://code.claude.com/docs/en/hooks, "PreToolUse: Blocks the tool call"). For a Write to
  results/extraction/out/<review>/<pmid>.json (by anyone), checked against the job
  results/extraction/jobs/<review>/<pmid>.json:
    1. valid JSON {review_pmid, pmid, items: [{name, value, quotes}]}; review_pmid and pmid match the path
    2. item names are exactly the job's items, same order, none missing or extra
    3. value is a non-empty string; "記載なし" has quotes []; any other value has at least one quote
    4. every quote is found verbatim in the job's full text (scripts/quote_match.py: NFKC, hyphen variants,
       whitespace incl. line breaks and tabs folded to one space)
  The extractor may write only the `output` of an existing job.
SubagentStop (matcher extractor) -- observation only (SubagentStop cannot block). Re-checks the output files named
  in the last message and tells the main session with a systemMessage, e.g. an extractor that ended without writing.

Any other Write passes (exit 0). Errors inside this hook fail open with a message on stderr.
"""

import json
import re
import sys
from pathlib import Path

from hooklib import block, project_dir, recheck_mentioned, rel, report_stop, use_scripts

OUT = re.compile(r"^results/extraction/out/(\d+)/(\d+)\.json$")
MENTION = re.compile(r"results/extraction/out/\d+/\d+\.json")
NOT_FOUND = "記載なし"
SCHEMA = "docs/schema.md 10章"


def check_extract(content: str, relpath: str, root: Path) -> list[str]:
    rid, pmid = OUT.match(relpath).groups()
    job_path = root / "results" / "extraction" / "jobs" / rid / f"{pmid}.json"
    if not job_path.exists():
        return [f"job が無い: {job_path.relative_to(root)}"]
    job = json.loads(job_path.read_text(encoding="utf-8"))
    txt_path = root / job["fulltext"]
    if not txt_path.exists():
        return [f"全文が無い: {job['fulltext']}"]
    try:
        doc = json.loads(content)
    except json.JSONDecodeError as e:
        return [f"JSON として読めない: {e}"]
    if not isinstance(doc, dict) or not isinstance(doc.get("items"), list):
        return ["形が違う: トップは {review_pmid, pmid, items: [{name, value, quotes}]}"]
    errs: list[str] = []
    if str(doc.get("review_pmid")) != rid:
        errs.append(f"review_pmid が {doc.get('review_pmid')!r}（このパスは {rid}）")
    if str(doc.get("pmid")) != pmid:
        errs.append(f"pmid が {doc.get('pmid')!r}（このパスは {pmid}）")

    expected = job["items"]
    got = [it.get("name") if isinstance(it, dict) else None for it in doc["items"]]
    for name in expected:
        if got.count(name) == 0:
            errs.append(f"項目 {name!r}: 無い（job の項目名をそのまま、全部書く）")
        elif got.count(name) > 1:
            errs.append(f"項目 {name!r}: 重複")
    for name in [g for g in got if g not in expected]:
        errs.append(f"項目 {name!r}: job に無い項目名（言い換えない）")
    if not errs and got != expected:
        errs.append("items を job の順に並べる")

    use_scripts(root)
    from quote_match import find_quote

    text = txt_path.read_text(encoding="utf-8")
    for it in doc["items"]:
        if not isinstance(it, dict):
            errs.append("items の要素がオブジェクトでない")
            continue
        name, value, quotes = it.get("name"), it.get("value"), it.get("quotes")
        if not isinstance(value, str) or not value.strip():
            errs.append(f"項目 {name!r}: value が空（見つからなければ {NOT_FOUND!r}）")
            continue
        if not isinstance(quotes, list):
            errs.append(f"項目 {name!r}: quotes は配列にする")
            continue
        if value.strip() == NOT_FOUND:
            if quotes:
                errs.append(f"項目 {name!r}: {NOT_FOUND} のときは quotes を [] にする")
            continue
        if not quotes:
            errs.append(f"項目 {name!r}: 値があるのに quotes が無い（全文からの逐語引用を1つ以上）")
        for q in quotes:
            if not isinstance(q, str) or not q.strip():
                errs.append(f"項目 {name!r}: 空の引用")
            elif not find_quote(text, q):
                errs.append(f"項目 {name!r}: 引用が全文に逐語で無い（言い換え・縮約・つなぎ合わせ不可。"
                            f"表はセルの文字列をそのまま）: {q[:80]!r}")
    return errs


def pre_tool_use(event: dict, root: Path) -> int:
    tool_input = event.get("tool_input") or {}
    relpath = rel(tool_input.get("file_path", ""), root)
    agent = event.get("agent_type") or ""
    m = OUT.match(relpath or "")
    if agent == "extractor":
        job = root / "results" / "extraction" / "jobs" / m.group(1) / f"{m.group(2)}.json" if m else None
        if not job or not job.exists() or json.loads(job.read_text(encoding="utf-8")).get("output") != relpath:
            return block([(f"extractor が書けるのは job の output（results/extraction/out/<review>/<pmid>.json）だけ"
                           f"（{tool_input.get('file_path')}）")], SCHEMA)
    if m:
        return block(check_extract(tool_input.get("content", ""), relpath, root), SCHEMA)
    return 0


def subagent_stop(event: dict, root: Path) -> int:
    paths = sorted(set(MENTION.findall(event.get("last_assistant_message") or "")))
    return report_stop("extractor", recheck_mentioned(paths, root, check_extract))


def main() -> int:
    try:
        event = json.load(sys.stdin)
        root = project_dir(event)
        name = event.get("hook_event_name")
        if name == "PreToolUse":
            return pre_tool_use(event, root)
        if name == "SubagentStop":
            return subagent_stop(event, root)
        return 0
    except Exception as e:  # noqa: BLE001 -- a broken hook must not block unrelated work; report and let it pass
        print(f"check_extract_output.py: hook error, not checked: {e!r}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
