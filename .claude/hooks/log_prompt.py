#!/usr/bin/env python3
"""UserPromptSubmit hook: append the submitted prompt to docs/prompts/log.md with a timestamp.

Prints nothing and always exits 0. On UserPromptSubmit, plain-text stdout is added to
Claude's context and exit 2 rejects the prompt, so this hook must stay silent and never block.
Personal and local information (paths, e-mail, IDE selections) is removed with scripts/redact_log.py
before writing (指示書21). If that import fails, nothing is written rather than an unredacted entry.
Prompts that Claude Code submits itself (task notifications, subagent hand-backs) are not the human's
instructions and are not written (redact_log.from_harness, 2026-10-01).
Spec: https://code.claude.com/docs/en/hooks (checked 2026-09-27)
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def main() -> None:
    data = json.load(sys.stdin)
    prompt = data.get("prompt", "")
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or "."
    log_path = Path(project_dir) / "docs" / "prompts" / "log.md"
    sys.path.insert(0, str(Path(project_dir) / "scripts"))
    from redact_log import from_harness, redact

    if from_harness(prompt):
        return
    prompt = redact(prompt)[0]
    log_path.parent.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    entry = f"\n---\n\n## {stamp}\n\n{prompt.rstrip()}\n"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(entry)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001, S110 -- must stay silent and never block (see docstring)
        pass
    sys.exit(0)
