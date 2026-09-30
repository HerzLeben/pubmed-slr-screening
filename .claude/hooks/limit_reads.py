#!/usr/bin/env python3
"""Let the adjudicator and the extractor Read only their input files (agent definitions, "入力").

PreToolUse (matcher Read). A subagent's `tools` field takes tool names only, not paths
(https://code.claude.com/docs/en/sub-agents), so the path check is done here. The event carries
`agent_type` when the tool call comes from a subagent (https://code.claude.com/docs/en/hooks, common
input fields); exit 2 "Blocks the tool call" and the subagent receives stderr.

Allowed for agent_type "adjudicator":
  results/adjudication/<review>.json
  results/screen/<a|b>/<review>/batch_<nn>.json
  reviews/<review>/criteria.json
  results/<review>/candidates.json
Allowed for agent_type "extractor" (指示書20):
  its own job results/extraction/jobs/<review>/<pmid>.json, and the job's `fulltext` (results/fulltext/<pmid>.txt).
  The hook cannot see which job a subagent was given, so the first job an extractor reads is pinned to its
  agent_id (.claude/state/extract_reads/<agent_id>.json); another job, or a text that is not the pinned job's
  `fulltext`, is refused. bench/, other outputs and docs/ are refused.
Any other agent, and the main session, passes (exit 0). Errors inside this hook fail open with a message.
"""

import json
import os
import re
import sys
from pathlib import Path

ALLOWED = {
    "adjudicator": [
        re.compile(r"^results/adjudication/\d+\.json$"),
        re.compile(r"^results/screen/[ab]/\d+/batch_\d{2}\.json$"),
        re.compile(r"^reviews/\d+/criteria\.json$"),
        re.compile(r"^results/\d+/candidates\.json$"),
    ],
}
JOB = re.compile(r"^results/extraction/jobs/\d+/\d+\.json$")
MESSAGES = {
    "adjudicator": "results/adjudication/<review>.json、results/screen/<a|b>/<review>/batch_<nn>.json、"
                   "reviews/<review>/criteria.json、results/<review>/candidates.json",
}


def extractor_read(relpath: str | None, event: dict, root: Path) -> str | None:
    """None when allowed, else the reason."""
    state = root / ".claude" / "state" / "extract_reads"
    agent_id = re.sub(r"[^\w-]", "_", str(event.get("agent_id") or "unknown"))
    pin = state / f"{agent_id}.json"
    pinned = json.loads(pin.read_text(encoding="utf-8"))["job"] if pin.exists() else None
    if relpath and JOB.match(relpath):
        if pinned is None:
            state.mkdir(parents=True, exist_ok=True)
            pin.write_text(json.dumps({"job": relpath}), encoding="utf-8")
            return None
        return None if relpath == pinned else f"読める job は最初に読んだ {pinned} だけ"
    if pinned is None:
        return "先に委任された job ファイル（results/extraction/jobs/<review>/<pmid>.json）を読む"
    fulltext = json.loads((root / pinned).read_text(encoding="utf-8")).get("fulltext")
    if relpath == fulltext:
        return None
    return f"読めるのは job（{pinned}）と、その fulltext（{fulltext}）だけ"


def rel(path: str, root: Path) -> str | None:
    p = Path(path)
    p = (root / p) if not p.is_absolute() else p
    try:
        return p.resolve().relative_to(root).as_posix()
    except ValueError:
        return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
        if event.get("hook_event_name") != "PreToolUse" or event.get("tool_name") != "Read":
            return 0
        agent = event.get("agent_type") or ""
        root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".").resolve()
        path = (event.get("tool_input") or {}).get("file_path", "")
        relpath = rel(path, root)
        if agent == "extractor":
            reason = extractor_read(relpath, event, root)
            if reason is None:
                return 0
            print(f"extractor は入力ファイルだけを読む（{reason}）。{path} は読まない", file=sys.stderr)
            return 2
        patterns = ALLOWED.get(agent)
        if patterns is None:
            return 0
        if relpath and any(p.match(relpath) for p in patterns):
            return 0
        print(f"{agent} が読めるのは入力ファイルだけ（{MESSAGES[agent]}）。{path} は読まない", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001 -- a broken hook must not block unrelated work; report and let it pass
        print(f"limit_reads.py: hook error, not checked: {e!r}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
