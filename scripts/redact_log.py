"""Keep docs/prompts/log.md a record of what the human wrote, without personal and local information (指示書21 2章).

Usage:
    python3 scripts/redact_log.py                     # rewrite docs/prompts/log.md in place, print the counts
    python3 scripts/redact_log.py --dry-run [path]    # only print the counts and examples

The UserPromptSubmit hook (.claude/hooks/log_prompt.py) uses from_harness() and redact() for new entries;
redact() was also used by `git filter-repo --file-info-callback` to rewrite docs/prompts/log.md in the history.

Entries that Claude Code itself submits as a prompt -- a background task's <task-notification> and a
subagent's <agent-message> hand-back -- are not instructions from the human and are dropped (2026-10-01).
Rules for the rest (the text the human wrote is not changed otherwise):
    <ide_selection>…</ide_selection>, <ide_opened_file>…</ide_opened_file>  -> removed
    ~/ or /Users/<name>/Library/CloudStorage/GoogleDrive-<account>/My Drive/  -> <Cowork のフォルダ>/
    /private/tmp/claude-<uid>/<project>/                                      -> <tmp>/
    /Users/<name>/dev/pubmed-slr-screening                                    -> <repo>
    /Users/<name>                                                             -> ~
    e-mail addresses                                                          -> <email>
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

RULES: list[tuple[str, re.Pattern, str]] = [
    ("ide", re.compile(r"<(ide_selection|ide_opened_file)>.*?</\1>\n?", re.DOTALL), ""),
    ("drive", re.compile(r"(?:~|/Users/[^/\s]+)/Library/CloudStorage/GoogleDrive-[^/\s]+/(?:My Drive/)?"),
     "<Cowork のフォルダ>/"),
    ("tmp", re.compile(r"(?:/private)?/tmp/claude-\d+/[^/\s]+/"), "<tmp>/"),
    ("repo", re.compile(r"/Users/[^/\s]+/dev/pubmed-slr-screening"), "<repo>"),
    ("home", re.compile(r"/Users/[^/\s]+"), "~"),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"), "<email>"),
]


HARNESS = re.compile(r"^\s*<(task-notification|agent-message)\b")
ENTRY = re.compile(r"\n---\n\n(?=## \d{4}-\d{2}-\d{2}T)")  # the separator log_prompt.py writes before each entry


def from_harness(prompt: str) -> bool:
    """True for a prompt that Claude Code submitted (task notification, subagent hand-back), not the human."""
    return bool(HARNESS.match(prompt))


def drop_harness_entries(text: str) -> tuple[str, int]:
    """The log without the entries whose prompt is from_harness(), and how many were dropped."""
    head, *entries = ENTRY.split(text)
    kept = [e for e in entries if not from_harness(e.split("\n", 2)[2] if e.count("\n") >= 2 else "")]
    return "\n---\n\n".join([head, *kept]), len(entries) - len(kept)


def redact(text: str) -> tuple[str, Counter]:
    counts: Counter = Counter()
    for name, pat, repl in RULES:
        text, n = pat.subn(repl, text)
        counts[name] += n
    return text, counts


def examples(text: str, k: int = 3) -> list[tuple[str, str]]:
    """Up to k (before, after) line pairs that change, one per rule where possible."""
    out, seen = [], set()
    for line in text.splitlines():
        new, c = redact(line)
        kinds = {n for n, v in c.items() if v}
        if new != line and not kinds <= seen:
            seen |= kinds
            out.append((line, new))
            if len(out) == k:
                break
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="docs/prompts/log.md")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    path = Path(args.path)
    text = path.read_text(encoding="utf-8")
    new, dropped = drop_harness_entries(text)
    new, counts = redact(new)
    print(f"harness\t{dropped}")
    for name, _, _ in RULES:
        print(f"{name}\t{counts[name]}")
    if args.dry_run:
        for before, after in examples(text):
            print("-", before[:200])
            print("+", after[:200])
        return
    if new != text:
        path.write_text(new, encoding="utf-8")
    print(f"wrote {path}" if new != text else "no change", file=sys.stderr)


if __name__ == "__main__":
    main()
