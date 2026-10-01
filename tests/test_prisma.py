"""scripts/prisma_record.py and .claude/hooks/check_prisma.py on a small made-up review. No network."""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

from prisma_record import check, reason, record

HOOK = REPO / ".claude" / "hooks" / "check_prisma.py"
ORDER = ["I1", "I2", "E1"]


def crit(*verdicts):
    return [{"id": i, "verdict": v} for i, v in zip(ORDER, verdicts, strict=True)]


def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


@pytest.fixture
def project(tmp_path):
    # pmid: (A, B, status, human decision); 6 hits, 5 screened (one outside the screened pool)
    rows = {
        "1": (crit(1, 1, 1), crit(1, 1, 1), "agreed_include", None),
        "2": (crit(-1, 1, -1), crit(1, 1, -1), "agreed_exclude", None),   # I1 comes before E1
        "3": (crit(1, 1, 1), crit(1, 1, -1), "needs_human", "exclude"),
        "4": (crit(1, 0, 1), crit(1, -1, 1), "needs_human", "include"),
        "5": (crit(1, 1, 1), crit(1, -1, 1), "needs_human", None),
    }
    write(tmp_path / "reviews" / "r" / "search.json",
          {"total_hits": 7, "all_pmids": ["1", "2", "3", "4", "5", "6", "6"], "retrieved_at": "t", "maxdate": "m"})
    write(tmp_path / "reviews" / "r" / "criteria.json", {"criteria": [{"id": i} for i in ORDER]})
    res = tmp_path / "results"
    write(res / "r" / "candidates.json", {"records": [{"pmid": p} for p in rows]})
    for who, k in (("a", 0), ("b", 1)):
        write(res / "screen" / who / "r" / "batch_01.json",
              {"records": [{"pmid": p, "criteria": r[k]} for p, r in rows.items()]})
    write(res / "adjudication" / "r.json", {"records": [{"pmid": p, "status": r[2]} for p, r in rows.items()]})
    write(res / "human" / "r.json", {"records": [{"pmid": p, "decision": r[3]} for p, r in rows.items() if r[3]]})
    (tmp_path / "scripts").symlink_to(REPO / "scripts")
    return tmp_path


def test_record_counts(project):
    r = record("r", project / "reviews", project / "results")
    assert {k: r[k] for k in ("identified", "duplicates_removed", "after_duplicates", "not_screened", "screened",
                              "excluded", "awaiting_human", "to_full_text")} == {
        "identified": 7, "duplicates_removed": 1, "after_duplicates": 6, "not_screened": 1, "screened": 5,
        "excluded": 2, "awaiting_human": 1, "to_full_text": 2}
    assert r["excluded_by_reason"] == {"I1": 1, "I2": 0, "E1": 0, "human": 1}
    assert r["detail"] == {"agreed_include": 1, "agreed_exclude": 1, "needs_human": 3, "human_include": 1,
                           "human_exclude": 1, "undecided": 1}
    assert check({"reviews": [r]}) == []


def test_reason_is_first_minus1_in_criteria_order():
    assert reason(ORDER, crit(1, 1, -1), crit(1, -1, 1)) == "I2"
    assert reason(["E1", "I1", "I2"], crit(-1, 1, -1), crit(1, 1, 1)) == "E1"


@pytest.mark.parametrize("mutate, expect", [
    (lambda r: r.update(after_duplicates=5), "identified - duplicates_removed"),
    (lambda r: r.update(not_screened=0), "screened + not_screened"),
    (lambda r: r.update(to_full_text=3), "excluded + awaiting_human + to_full_text"),
    (lambda r: r["excluded_by_reason"].update(I2=1), "sum of excluded_by_reason"),
    (lambda r: r["detail"].update(human_include=2, human_exclude=0), "detail"),
    (lambda r: r.update(screened="5"), "integers"),
])
def test_check_finds_broken_sums(project, mutate, expect):
    r = copy.deepcopy(record("r", project / "reviews", project / "results"))
    mutate(r)
    errs = check({"reviews": [r]})
    assert errs and any(expect in e for e in errs)


def test_check_needs_reviews():
    assert check({}) and check({"reviews": []}) and check([])


def run_hook(root: Path, path: str, tool="Write"):
    event = {"hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": {"file_path": path},
             "cwd": str(root)}
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event), capture_output=True, text=True,
                          env=env, check=False)


def test_hook_passes_good_file_and_sends_back_broken_one(project):
    r = record("r", project / "reviews", project / "results")
    target = project / "results" / "prisma.json"
    write(target, {"reviews": [r]})
    assert run_hook(project, str(target)).returncode == 0
    r["excluded"] += 1
    write(target, {"reviews": [r]})
    p = run_hook(project, "results/prisma.json", tool="Edit")
    assert p.returncode == 2 and "do not add up" in p.stderr


def test_hook_invalid_json_and_other_files(project):
    target = project / "results" / "prisma.json"
    target.write_text("{not json", encoding="utf-8")
    assert run_hook(project, str(target)).returncode == 2
    assert run_hook(project, str(project / "results" / "other.json")).returncode == 0
    assert run_hook(project, "/elsewhere/results/prisma.json").returncode == 0
