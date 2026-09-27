#!/usr/bin/env python3
"""UserPromptSubmit hook: append the submitted prompt to docs/prompts/log.md with a timestamp.

Prints nothing and always exits 0. On UserPromptSubmit, plain-text stdout is added to
Claude's context and exit 2 rejects the prompt, so this hook must stay silent and never block.
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
    log_path.parent.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    entry = f"\n---\n\n## {stamp}\n\n{prompt.rstrip()}\n"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(entry)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
