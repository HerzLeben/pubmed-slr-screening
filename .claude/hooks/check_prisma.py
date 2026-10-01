#!/usr/bin/env python3
"""Check the PRISMA counts after Claude writes or edits results/prisma.json (docs/design.md section 4).

Wired in .claude/settings.json as PostToolUse (matcher Write|Edit). The file is already written; exit 2
shows stderr to Claude so it fixes the counts (https://code.claude.com/docs/en/hooks, exit code 2 per
event: "PostToolUse: Shows stderr to Claude; the tool already ran"). The sums are
scripts/prisma_record.py check(): identified - duplicates = after_duplicates = screened + not_screened,
screened = excluded + awaiting_human + to_full_text, and the exclusion reasons add up to excluded.

scripts/prisma_record.py runs the same check before it writes, so this hook matters when Claude or a
person changes the file by hand. Any other file passes (exit 0). Errors inside this hook itself fail open
with a message on stderr.
"""

import json
import sys

from hooklib import project_dir, rel, use_scripts

TARGET = "results/prisma.json"


def main() -> int:
    event = json.load(sys.stdin)
    root = project_dir(event)
    if rel((event.get("tool_input") or {}).get("file_path") or "", root) != TARGET:
        return 0
    path = root / TARGET
    use_scripts(root)
    from prisma_record import check

    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"{TARGET} is not valid JSON: {e}", file=sys.stderr)
        return 2
    errs = check(doc)
    if errs:
        print(f"{TARGET}: the PRISMA counts do not add up. Fix the file:\n" + "\n".join(errs), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 -- fail open; a broken hook must not stop unrelated writes
        print(f"check_prisma.py: hook error, not checked: {e}", file=sys.stderr)
        sys.exit(0)
