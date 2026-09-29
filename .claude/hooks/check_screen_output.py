#!/usr/bin/env python3
"""Check screener and adjudicator output against docs/schema.md sections 5 and 6.

Wired in .claude/settings.json for two events:

PreToolUse (matcher Write) -- the send-back. Runs before the file is written. Exit 2 blocks the Write
  and the subagent receives stderr and keeps working (https://code.claude.com/docs/en/hooks, exit code 2
  per event: "PreToolUse: Blocks the tool call"). Checked:
  - results/screen/<a|b>/<review>/batch_<nn>.json (schema 5):
      1. valid JSON of the right shape; screener, review_pmid and batch match the path; records are exactly
         the PMIDs of results/batches/<review>/<a|b>/batch_<nn>.json
      2. every record has each criterion of reviews/<review>/criteria.json exactly once, in ID order, with
         verdict -1/0/1; no overall/score
      3. every +/-1 has a quote found in the title or abstract of results/<review>/candidates.json
         (scripts/quote_match.py: NFKC, hyphen variants, whitespace); 0 has quote null
    The same checks apply to results/eval-3/screen/<a|b>/<review>/batch_<nn>.json, matched against the
    eval-3 inputs instead (run_files): results/eval-3/batches/..., reviews/<review>/eval-3/criteria.json
    (the unapproved draft criteria, DECISIONS 指示書19 2章) and results/eval-3/<review>/candidates.json.
  - results/adjudication/<review>.json written by the adjudicator (schema 6): records, status, reasons and
    disagree_criteria unchanged; every needs_human record has a summary
  - a screener may write only under results/[eval-3/]screen/<its letter>/, the adjudicator only
    results/adjudication/<review>.json
SubagentStop (matcher screener-a|screener-b) -- observation only. SubagentStop cannot block ("Exit code 2
  isn't honored; the subagent has already finished"), so this re-checks the files named in the subagent's
  last message and reports problems as a systemMessage for the main session.

Any other Write passes (exit 0). Errors inside this hook itself fail open with a message on stderr.
"""

import json
import os
import re
import sys
from pathlib import Path

SCREEN = re.compile(r"^results/(?:(eval-3)/)?screen/([ab])/(\d+)/batch_(\d{2})\.json$")
ADJ = re.compile(r"^results/adjudication/(\d+)\.json$")
MENTION = re.compile(r"results/(?:eval-3/)?screen/[ab]/\d+/batch_\d{2}\.json")
MAX_LINES = 40


def project_dir(event: dict) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".").resolve()


def rel(path: str, root: Path) -> str | None:
    p = Path(path)
    p = (root / p) if not p.is_absolute() else p
    try:
        return p.resolve().relative_to(root).as_posix()
    except ValueError:
        return None


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def id_key(cid: str) -> tuple[int, int]:
    return (0 if cid.startswith("I") else 1, int(cid[1:]))


def run_files(run: str | None, who: str, rid: str, nn: str, root: Path) -> tuple[Path, Path, Path]:
    """(batch input, criteria, candidates) for a screener output of this run. None is eval-1/eval-2."""
    if run == "eval-3":
        res = root / "results" / "eval-3"
        return (res / "batches" / rid / who / f"batch_{nn}.json",
                root / "reviews" / rid / "eval-3" / "criteria.json",
                res / rid / "candidates.json")
    return (root / "results" / "batches" / rid / who / f"batch_{nn}.json",
            root / "reviews" / rid / "criteria.json",
            root / "results" / rid / "candidates.json")


def check_screen(content: str, relpath: str, root: Path) -> list[str]:
    run, who, rid, nn = SCREEN.match(relpath).groups()
    errs: list[str] = []
    try:
        doc = json.loads(content)
    except json.JSONDecodeError as e:
        return [f"JSON として読めない: {e}"]
    if not isinstance(doc, dict) or not isinstance(doc.get("records"), list):
        return ["形が違う: トップは {review_pmid, screener, batch, records: [...]}"]
    if doc.get("screener") != who:
        errs.append(f"screener が {doc.get('screener')!r}（このパスは {who!r}）")
    if str(doc.get("review_pmid")) != rid:
        errs.append(f"review_pmid が {doc.get('review_pmid')!r}（このパスは {rid}）")
    if doc.get("batch") != int(nn):
        errs.append(f"batch が {doc.get('batch')!r}（このパスは {int(nn)}）")

    sys.path.insert(0, str(root / "scripts"))
    from quote_match import quote_exists

    batch_in, crit_path, cand_path = run_files(run, who, rid, nn, root)
    for p in (batch_in, crit_path, cand_path):
        if not p.exists():
            return errs + [f"照合に使うファイルが無い: {p.relative_to(root)}"]
    expected = [str(r["pmid"]) for r in load(batch_in)["records"]]
    ids = sorted((c["id"] for c in load(crit_path)["criteria"]), key=id_key)
    cands = {str(c["pmid"]): c for c in load(cand_path)["records"]}

    got = [str(r.get("pmid")) for r in doc["records"] if isinstance(r, dict)]
    for pmid in sorted(set(expected) - set(got)):
        errs.append(f"PMID {pmid}: レコードが無い（バッチの全件を書く）")
    for pmid in sorted(set(got) - set(expected)):
        errs.append(f"PMID {pmid}: このバッチに無い PMID")
    for pmid in sorted({p for p in got if got.count(p) > 1}):
        errs.append(f"PMID {pmid}: レコードが重複")

    for rec in doc["records"]:
        if not isinstance(rec, dict):
            errs.append("records の要素がオブジェクトでない")
            continue
        pmid = str(rec.get("pmid"))
        for key in ("overall", "score"):
            if key in rec:
                errs.append(f"PMID {pmid}: {key} は書かない（規則で導く）")
        crit = rec.get("criteria")
        if not isinstance(crit, list):
            errs.append(f"PMID {pmid}: criteria が無い")
            continue
        seen = [c.get("id") if isinstance(c, dict) else None for c in crit]
        for cid in ids:
            if seen.count(cid) != 1:
                errs.append(f"PMID {pmid} 基準 {cid}: {'無い' if seen.count(cid) == 0 else '重複'}")
        for cid in sorted({str(s) for s in seen} - set(ids)):
            errs.append(f"PMID {pmid} 基準 {cid}: 知らない基準 ID")
        if all(s in ids for s in seen) and len(seen) == len(ids) and seen != ids:
            errs.append(f"PMID {pmid}: criteria を ID 順（{', '.join(ids)}）に並べる")
        cand = cands.get(pmid, {})
        for c in crit:
            if not isinstance(c, dict):
                continue
            cid, v, q = c.get("id"), c.get("verdict"), c.get("quote")
            if isinstance(v, bool) or v not in (-1, 0, 1):
                errs.append(f"PMID {pmid} 基準 {cid}: verdict {v!r} は範囲外（-1/0/1 の整数）")
                continue
            if v == 0:
                if q is not None:
                    errs.append(f"PMID {pmid} 基準 {cid}: verdict 0 の quote は null にする")
                continue
            if not isinstance(q, str) or not q.strip():
                errs.append(f"PMID {pmid} 基準 {cid}: verdict {v} なのに quote が無い")
            elif not quote_exists(cand.get("title", ""), cand.get("abstract") or "", q):
                errs.append(f"PMID {pmid} 基準 {cid}: quote がタイトルにも抄録にも逐語で無い"
                            f"（言い換え・縮約・つなぎ合わせ不可）: {q[:80]!r}")
    return errs


def check_adjudication(content: str, relpath: str, root: Path) -> list[str]:
    (rid,) = ADJ.match(relpath).groups()
    path = root / relpath
    if not path.exists():
        return [f"{relpath} が無い。先に scripts/adjudicate.py で作る（adjudicator は summary だけを足す）"]
    try:
        new = json.loads(content)
    except json.JSONDecodeError as e:
        return [f"JSON として読めない: {e}"]
    old = load(path)
    errs: list[str] = []
    if str(new.get("review_pmid")) != rid:
        errs.append(f"review_pmid が {new.get('review_pmid')!r}（このパスは {rid}）")
    old_recs, new_recs = old.get("records", []), new.get("records", [])
    if [str(r.get("pmid")) for r in new_recs] != [str(r.get("pmid")) for r in old_recs]:
        return errs + ["records の PMID・数・順番を変えない"]
    for o, n in zip(old_recs, new_recs, strict=True):
        for key in ("status", "reasons", "disagree_criteria"):
            if n.get(key) != o.get(key):
                errs.append(f"PMID {o['pmid']}: {key} を変えない（{o.get(key)!r} → {n.get(key)!r}）")
        if o.get("status") == "needs_human" and not str(n.get("summary") or "").strip():
            errs.append(f"PMID {o['pmid']}: needs_human に summary が無い")
    return errs


def pre_tool_use(event: dict, root: Path) -> int:
    tool_input = event.get("tool_input") or {}
    relpath = rel(tool_input.get("file_path", ""), root)
    agent = event.get("agent_type") or ""
    if agent.startswith("screener-"):
        letter = agent.removeprefix("screener-")
        m = SCREEN.match(relpath or "")
        if not m or m.group(2) != letter:
            return block([(f"{agent} が書けるのは results/screen/{letter}/<review>/batch_<nn>.json"
                           f"（eval-3 は results/eval-3/screen/{letter}/<review>/batch_<nn>.json）だけ"
                           f"（{tool_input.get('file_path')}）")])
    if agent == "adjudicator" and not ADJ.match(relpath or ""):
        return block([f"adjudicator が書けるのは results/adjudication/<review>.json だけ（{tool_input.get('file_path')}）"])
    if relpath and SCREEN.match(relpath):
        return block(check_screen(tool_input.get("content", ""), relpath, root))
    if relpath and ADJ.match(relpath) and agent == "adjudicator":
        return block(check_adjudication(tool_input.get("content", ""), relpath, root))
    return 0


def block(errs: list[str]) -> int:
    if not errs:
        return 0
    lines = errs[:MAX_LINES] + ([f"…ほか {len(errs) - MAX_LINES} 件"] if len(errs) > MAX_LINES else [])
    print("出力が docs/schema.md に合わないので書き込みを止めた。直してもう一度 Write する:\n- "
          + "\n- ".join(lines), file=sys.stderr)
    return 2


def subagent_stop(event: dict, root: Path) -> int:
    paths = sorted(set(MENTION.findall(event.get("last_assistant_message") or "")))
    problems = []
    if not paths:
        problems.append("最後のメッセージに出力ファイルのパスが無い（書かずに終わった可能性）")
    for relpath in paths:
        f = root / relpath
        if not f.exists():
            problems.append(f"{relpath}: ファイルが無い")
            continue
        problems += [f"{relpath}: {e}" for e in check_screen(f.read_text(encoding="utf-8"), relpath, root)]
    if problems:
        msg = f"{event.get('agent_type')} の出力に不備（SubagentStop は差し戻せないので、本体が再起動すること）:\n- "
        print(json.dumps({"systemMessage": msg + "\n- ".join(problems[:MAX_LINES])}, ensure_ascii=False))
    return 0


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
        print(f"check_screen_output.py: hook error, not checked: {e!r}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
