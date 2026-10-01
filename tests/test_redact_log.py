"""Redaction of docs/prompts/log.md (scripts/redact_log.py) and the log_prompt hook that uses it. No network."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from redact_log import redact

HOOK = REPO / ".claude" / "hooks" / "log_prompt.py"

SAMPLE = """前の行
<ide_selection>The user selected the lines 8 to 8 from /Users/someone/dev/pubmed-slr-screening/CLAUDE.md:
**迷ったらここが正**

This may or may not be related to the current task.</ide_selection>
人が書いた指示はそのまま残す。
<ide_opened_file>The user opened the file /Users/someone/dev/pubmed-slr-screening/.env in the IDE.</ide_opened_file>
資料は ~/Library/CloudStorage/GoogleDrive-someone@example.co.jp/My Drive/Blog/a.md にある。
出力 /private/tmp/claude-501/-Users-someone-dev-pubmed-slr-screening/abc/tasks/x.output を見た。
file:///Users/someone/dev/pubmed-slr-screening/results/report.html と /Users/someone/.claude.json
連絡は someone@example.co.jp まで
"""


def test_redact_rules():
    out, c = redact(SAMPLE)
    assert c == {"ide": 2, "drive": 1, "tmp": 1, "repo": 1, "home": 1, "email": 1}
    assert "someone" not in out and "ide_" not in out and ".env" not in out
    assert "前の行\n人が書いた指示はそのまま残す。\n資料は <Cowork のフォルダ>/Blog/a.md にある。" in out
    assert "出力 <tmp>/abc/tasks/x.output を見た。" in out
    assert "file://<repo>/results/report.html と ~/.claude.json" in out
    assert "連絡は <email> まで" in out


def test_redact_is_idempotent_and_keeps_plain_text():
    once = redact(SAMPLE)[0]
    assert redact(once) == (once, redact(once)[1]) and sum(redact(once)[1].values()) == 0
    text = "~/dev/pubmed-slr-screening で `python3 -m pytest -q` を打つ。results/ は gitignore"
    assert redact(text)[0] == text


def test_hook_writes_redacted_entry(tmp_path):
    (tmp_path / "scripts").mkdir()
    shutil.copy(REPO / "scripts" / "redact_log.py", tmp_path / "scripts" / "redact_log.py")
    event = {"prompt": SAMPLE, "cwd": str(tmp_path)}
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event), capture_output=True, text=True,
                       env={**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)}, check=False)
    assert r.returncode == 0 and r.stdout == ""
    log = (tmp_path / "docs" / "prompts" / "log.md").read_text(encoding="utf-8")
    assert "人が書いた指示はそのまま残す。" in log and "someone" not in log and "ide_" not in log


def test_hook_writes_nothing_without_redactor(tmp_path):
    event = {"prompt": SAMPLE, "cwd": str(tmp_path)}
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event), capture_output=True, text=True,
                       env={**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)}, check=False)
    assert r.returncode == 0 and r.stdout == ""
    log = tmp_path / "docs" / "prompts" / "log.md"
    assert not log.exists() or "someone" not in log.read_text(encoding="utf-8")
