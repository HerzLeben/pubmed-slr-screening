"""Helpers shared by the hooks in this folder (not a hook itself; settings.json does not run it).

A hook runs as `python3 .claude/hooks/<name>.py`, so this folder is on sys.path and `import hooklib` works.
"""

import json
import os
import sys
from pathlib import Path

MAX_LINES = 40  # problems shown at once; the rest are counted


def project_dir(event: dict) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".").resolve()


def rel(path: str, root: Path) -> str | None:
    """The path relative to the project (posix), or None when it is outside."""
    p = Path(path)
    p = (root / p) if not p.is_absolute() else p
    try:
        return p.resolve().relative_to(root).as_posix()
    except ValueError:
        return None


def use_scripts(root: Path) -> None:
    """Make scripts/ importable (quote_match.py, rules.py, prisma_record.py are the one definition)."""
    path = str(root / "scripts")
    if path not in sys.path:
        sys.path.insert(0, path)


def block(errs: list[str], what: str) -> int:
    """PreToolUse send-back: exit 2 with the problems on stderr, or 0 when there are none."""
    if not errs:
        return 0
    lines = errs[:MAX_LINES] + ([f"…ほか {len(errs) - MAX_LINES} 件"] if len(errs) > MAX_LINES else [])
    print(f"出力が {what} に合わないので書き込みを止めた。直してもう一度 Write する:\n- " + "\n- ".join(lines),
          file=sys.stderr)
    return 2


def report_stop(agent: str, problems: list[str]) -> int:
    """SubagentStop cannot block, so problems go to the main session as a systemMessage. Always 0."""
    if problems:
        msg = f"{agent} の出力に不備（SubagentStop は差し戻せないので、本体が再起動すること）:\n- "
        print(json.dumps({"systemMessage": msg + "\n- ".join(problems[:MAX_LINES])}, ensure_ascii=False))
    return 0


def recheck_mentioned(paths: list[str], root: Path, check) -> list[str]:
    """SubagentStop: re-run `check(content, relpath, root)` on the output files named in the last message."""
    if not paths:
        return ["最後のメッセージに出力ファイルのパスが無い（書かずに終わった可能性）"]
    problems = []
    for relpath in paths:
        f = root / relpath
        if not f.exists():
            problems.append(f"{relpath}: ファイルが無い")
            continue
        problems += [f"{relpath}: {e}" for e in check(f.read_text(encoding="utf-8"), relpath, root)]
    return problems
