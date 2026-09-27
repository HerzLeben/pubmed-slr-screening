#!/usr/bin/env python3
"""Keep at most N subagents running at once in a session (CLAUDE.md: the limit is 6).

SubagentStart: exit 2 blocks the subagent from starting (https://code.claude.com/docs/en/hooks, exit code 2
  per event: "SubagentStart: Blocks the subagent from starting"). A marker file per running subagent is
  kept under .claude/state/running/<session_id>/; if N are already there, the start is refused.
SubagentStop: removes the marker.

N comes from SLR_MAX_PARALLEL (default 6). Markers older than SLR_STALE_SECONDS (default 3 h) are treated
as left over from a subagent whose SubagentStop never ran, and are removed. The settings.json env
CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=6 is Claude Code's own limit; this hook is the project's check with a
message that names the rule, and it also covers subagents the built-in limit lets through (resumes).
"""

import fcntl
import json
import os
import re
import sys
import time
from pathlib import Path

SAFE = re.compile(r"[^A-Za-z0-9_.-]")


def state_dir(event: dict) -> Path:
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".")
    session = SAFE.sub("_", str(event.get("session_id") or "nosession"))
    return root / ".claude" / "state" / "running" / session


def main() -> int:
    try:
        event = json.load(sys.stdin)
        name = event.get("hook_event_name")
        agent_id = SAFE.sub("_", str(event.get("agent_id") or ""))
        if name not in ("SubagentStart", "SubagentStop") or not agent_id:
            return 0
        d = state_dir(event)
        d.mkdir(parents=True, exist_ok=True)
        limit = int(os.environ.get("SLR_MAX_PARALLEL", "6"))
        stale = float(os.environ.get("SLR_STALE_SECONDS", str(3 * 3600)))
        with (d / ".lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)  # parallel starts in one message must not all see a free slot
            if name == "SubagentStop":
                (d / agent_id).unlink(missing_ok=True)
                return 0
            now = time.time()
            running = []
            for m in d.iterdir():
                if m.name.startswith("."):
                    continue
                if now - m.stat().st_mtime > stale:
                    m.unlink(missing_ok=True)
                else:
                    running.append(m.name)
            if len(running) >= limit:
                print(f"subagent の同時起動は {limit} まで（CLAUDE.md）。いま {len(running)} 体が動いている。"
                      f"終わるのを待ってから {event.get('agent_type')} を起動する", file=sys.stderr)
                return 2
            (d / agent_id).write_text(json.dumps({"agent_type": event.get("agent_type"), "started": now}))
            return 0
    except Exception as e:  # noqa: BLE001 -- a broken gate must not stop all subagents; report and let it pass
        print(f"agent_gate.py: hook error, not checked: {e!r}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
