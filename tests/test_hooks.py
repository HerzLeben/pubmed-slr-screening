"""The hooks in .claude/hooks/ get deliberately broken output and must send it back (exit 2).

Each test builds a small project in tmp_path (criteria, candidates, a batch input) and runs the hook as
Claude Code would: JSON on stdin, CLAUDE_PROJECT_DIR set, exit code and stderr/stdout read back.
"""

import copy
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CHECK = REPO / ".claude" / "hooks" / "check_screen_output.py"
GATE = REPO / ".claude" / "hooks" / "agent_gate.py"
READS = REPO / ".claude" / "hooks" / "limit_reads.py"

RID = "999"
CRITERIA = [
    {"id": "I1", "type": "inclusion", "text": "blood cancer patients"},
    {"id": "I2", "type": "inclusion", "text": "CD19 CAR-T"},
    {"id": "E1", "type": "exclusion", "text": "secondary literature"},
]
# PMID 1: abstract uses a non-breaking hyphen (U+2011) and a no-break space; PMID 2 has no abstract.
CANDS = [
    {"pmid": "1", "rank": 1, "title": "CD19 CAR T cells in lymphoma",
     "abstract": "We treated 20 patients with relapsed B‑cell lymphoma using CD19 CAR‑T cells. "
                 "The overall response rate was 60%."},
    {"pmid": "2", "rank": 2, "title": "A review of CAR-T therapy for leukemia", "abstract": ""},
]
OUT_A = f"results/screen/a/{RID}/batch_01.json"


def good_output(who="a"):
    return {
        "review_pmid": RID, "screener": who, "batch": 1,
        "records": [
            {"pmid": "1", "criteria": [
                {"id": "I1", "verdict": 1, "quote": "20 patients with relapsed B-cell lymphoma"},  # plain hyphen
                {"id": "I2", "verdict": 1, "quote": "CD19 CAR-T cells"},
                {"id": "E1", "verdict": 1, "quote": "We treated 20 patients"},
            ]},
            {"pmid": "2", "criteria": [
                {"id": "I1", "verdict": 0, "quote": None, "note": "no abstract"},
                {"id": "I2", "verdict": 0, "quote": None},
                {"id": "E1", "verdict": -1, "quote": "A review of CAR-T therapy"},  # from the title
            ]},
        ],
    }


@pytest.fixture
def project(tmp_path):
    (tmp_path / "scripts").mkdir()
    shutil.copy(REPO / "scripts" / "quote_match.py", tmp_path / "scripts")
    (tmp_path / "reviews" / RID).mkdir(parents=True)
    (tmp_path / "reviews" / RID / "criteria.json").write_text(json.dumps({"review_pmid": RID, "criteria": CRITERIA}))
    (tmp_path / "results" / RID).mkdir(parents=True)
    (tmp_path / "results" / RID / "candidates.json").write_text(json.dumps({"review_pmid": RID, "records": CANDS}))
    for who in ("a", "b"):
        d = tmp_path / "results" / "batches" / RID / who
        d.mkdir(parents=True)
        recs = [{"pmid": c["pmid"], "title": c["title"], "abstract": c["abstract"]} for c in CANDS]
        (d / "batch_01.json").write_text(json.dumps({"review_pmid": RID, "screener": who, "batch": 1, "records": recs}))
    return tmp_path


def run(script, event, root):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
    p = subprocess.run([sys.executable, str(script)], input=json.dumps(event), capture_output=True, text=True,
                       env=env, timeout=30, check=False)
    return p.returncode, p.stdout, p.stderr


def write_event(root, path, content, agent="screener-a"):
    ev = {"hook_event_name": "PreToolUse", "tool_name": "Write", "session_id": "s1", "cwd": str(root),
          "tool_input": {"file_path": str(root / path), "content": content if isinstance(content, str)
                         else json.dumps(content, ensure_ascii=False)}}
    if agent:
        ev["agent_type"] = agent
        ev["agent_id"] = "agent-1"
    return ev


# ---- screener output: passes -------------------------------------------------------------------

def test_good_output_passes(project):
    code, _, err = run(CHECK, write_event(project, OUT_A, good_output()), project)
    assert code == 0, err


def test_screener_b_good_output_passes(project):
    code, _, err = run(CHECK, write_event(project, f"results/screen/b/{RID}/batch_01.json", good_output("b"),
                                          agent="screener-b"), project)
    assert code == 0, err


def test_unrelated_write_by_main_session_passes(project):
    code, _, _ = run(CHECK, write_event(project, "docs/notes.md", "hello", agent=None), project)
    assert code == 0


# ---- eval-3: the run picks the criteria file (reviews/<rid>/eval-3/criteria.json) -------------------------
E3_RID = "31190844"  # the real draft criteria of eval-3 have I5 (comparator); eval-2's criteria.json does not
E3_CAND = {"pmid": "5", "rank": 1, "title": "CD19 CAR-T cells versus chemotherapy in B-ALL",
           "abstract": "Adults with relapsed B-ALL received autologous CD19 CAR-T cells."}


def e3_output(ids, who="a"):
    crit = [{"id": i, "verdict": 1, "quote": "CD19 CAR-T cells"} if i == "I2" else {"id": i, "verdict": 0, "quote": None}
            for i in ids]
    return {"review_pmid": E3_RID, "screener": who, "batch": 1, "records": [{"pmid": "5", "criteria": crit}]}


def ids_of(path):
    return [c["id"] for c in json.loads(path.read_text(encoding="utf-8"))["criteria"]]


@pytest.fixture
def e3_project(tmp_path):
    (tmp_path / "scripts").mkdir()
    shutil.copy(REPO / "scripts" / "quote_match.py", tmp_path / "scripts")
    for sub in ("", "eval-3"):
        d = tmp_path / "reviews" / E3_RID / sub
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / "reviews" / E3_RID / sub / "criteria.json", d / "criteria.json")
    rec = {k: E3_CAND[k] for k in ("pmid", "title", "abstract")}
    for res in (tmp_path / "results", tmp_path / "results" / "eval-3"):
        (res / E3_RID).mkdir(parents=True)
        (res / E3_RID / "candidates.json").write_text(json.dumps({"review_pmid": E3_RID, "records": [E3_CAND]}))
        for who in ("a", "b"):
            d = res / "batches" / E3_RID / who
            d.mkdir(parents=True)
            (d / "batch_01.json").write_text(json.dumps({"review_pmid": E3_RID, "screener": who, "batch": 1,
                                                         "records": [rec]}))
    return tmp_path


def test_eval3_criteria_have_i5_and_eval2_do_not():
    assert "I5" in ids_of(REPO / "reviews" / E3_RID / "eval-3" / "criteria.json")
    assert "I5" not in ids_of(REPO / "reviews" / E3_RID / "criteria.json")


def test_eval3_output_with_i5_passes(e3_project):
    ids = ids_of(e3_project / "reviews" / E3_RID / "eval-3" / "criteria.json")
    path = f"results/eval-3/screen/a/{E3_RID}/batch_01.json"
    code, _, err = run(CHECK, write_event(e3_project, path, e3_output(ids)), e3_project)
    assert code == 0, err


def test_eval3_output_without_i5_is_sent_back(e3_project):
    ids = ids_of(e3_project / "reviews" / E3_RID / "criteria.json")
    path = f"results/eval-3/screen/a/{E3_RID}/batch_01.json"
    code, _, err = run(CHECK, write_event(e3_project, path, e3_output(ids)), e3_project)
    assert code == 2
    assert "基準 I5: 無い" in err


def test_eval2_still_checks_against_eval2_criteria(e3_project):
    eval2 = ids_of(e3_project / "reviews" / E3_RID / "criteria.json")
    path = f"results/screen/a/{E3_RID}/batch_01.json"
    code, _, err = run(CHECK, write_event(e3_project, path, e3_output(eval2)), e3_project)
    assert code == 0, err
    eval3 = ids_of(e3_project / "reviews" / E3_RID / "eval-3" / "criteria.json")
    code, _, err = run(CHECK, write_event(e3_project, path, e3_output(eval3)), e3_project)
    assert code == 2
    assert "基準 I5: 知らない基準 ID" in err


def test_eval3_quote_checked_against_eval3_candidates(e3_project):
    (e3_project / "results" / "eval-3" / E3_RID / "candidates.json").write_text(json.dumps(
        {"review_pmid": E3_RID, "records": [{**E3_CAND, "title": "Other title", "abstract": "Other text."}]}))
    ids = ids_of(e3_project / "reviews" / E3_RID / "eval-3" / "criteria.json")
    path = f"results/eval-3/screen/a/{E3_RID}/batch_01.json"
    code, _, err = run(CHECK, write_event(e3_project, path, e3_output(ids)), e3_project)
    assert code == 2
    assert "逐語で無い" in err


def test_eval3_missing_input_is_reported(e3_project):
    (e3_project / "reviews" / E3_RID / "eval-3" / "criteria.json").unlink()
    ids = ids_of(e3_project / "reviews" / E3_RID / "criteria.json")
    path = f"results/eval-3/screen/a/{E3_RID}/batch_01.json"
    code, _, err = run(CHECK, write_event(e3_project, path, e3_output(ids)), e3_project)
    assert code == 2
    assert f"reviews/{E3_RID}/eval-3/criteria.json" in err


def test_screener_a_cannot_write_eval3_b_folder(e3_project):
    ids = ids_of(e3_project / "reviews" / E3_RID / "eval-3" / "criteria.json")
    path = f"results/eval-3/screen/b/{E3_RID}/batch_01.json"
    code, _, err = run(CHECK, write_event(e3_project, path, e3_output(ids, "b")), e3_project)
    assert code == 2
    assert "results/eval-3/screen/a/" in err


def test_subagent_stop_rechecks_eval3_output(e3_project):
    ids = ids_of(e3_project / "reviews" / E3_RID / "criteria.json")  # no I5: wrong for eval-3
    rel = f"results/eval-3/screen/a/{E3_RID}/batch_01.json"
    (e3_project / rel).parent.mkdir(parents=True)
    (e3_project / rel).write_text(json.dumps(e3_output(ids)))
    ev = {"hook_event_name": "SubagentStop", "agent_type": "screener-a", "cwd": str(e3_project),
          "last_assistant_message": f"書きました: {rel}"}
    code, out, _ = run(CHECK, ev, e3_project)
    assert code == 0
    assert "I5" in json.loads(out)["systemMessage"]


# ---- screener output: sent back ----------------------------------------------------------------

def broken(mutate):
    doc = good_output()
    mutate(doc)
    return doc


BROKEN = {
    "paraphrased_quote": (lambda d: d["records"][0]["criteria"][0].update(quote="twenty relapsed lymphoma patients"),
                          "PMID 1 基準 I1"),
    "shortened_quote": (lambda d: d["records"][0]["criteria"][1].update(quote="CD19 CAR-T ... cells"), "PMID 1 基準 I2"),
    "stitched_quote": (lambda d: d["records"][0]["criteria"][2].update(quote="We treated 20 patients. The overall"),
                       "PMID 1 基準 E1"),
    "missing_criterion": (lambda d: d["records"][0]["criteria"].pop(1), "PMID 1 基準 I2: 無い"),
    "duplicated_criterion": (lambda d: d["records"][1]["criteria"].append(
        {"id": "I1", "verdict": 0, "quote": None}), "PMID 2 基準 I1: 重複"),
    "unknown_criterion": (lambda d: d["records"][1]["criteria"].append(
        {"id": "E9", "verdict": 0, "quote": None}), "E9: 知らない基準"),
    "verdict_out_of_range": (lambda d: d["records"][0]["criteria"][0].update(verdict=2), "範囲外"),
    "verdict_as_string": (lambda d: d["records"][0]["criteria"][0].update(verdict="1"), "範囲外"),
    "verdict_as_bool": (lambda d: d["records"][0]["criteria"][0].update(verdict=True), "範囲外"),
    "missing_quote": (lambda d: d["records"][0]["criteria"][0].update(quote=None), "quote が無い"),
    "quote_on_zero": (lambda d: d["records"][1]["criteria"][0].update(quote="A review"), "null にする"),
    "not_id_order": (lambda d: d["records"][0]["criteria"].reverse(), "ID 順"),
    "missing_record": (lambda d: d["records"].pop(1), "PMID 2: レコードが無い"),
    "foreign_pmid": (lambda d: d["records"][1].update(pmid="3"), "PMID 3: このバッチに無い"),
    "overall_written": (lambda d: d["records"][0].update(overall="include"), "overall は書かない"),
    "wrong_screener": (lambda d: d.update(screener="b"), "screener が"),
    "wrong_batch": (lambda d: d.update(batch=2), "batch が"),
}


@pytest.mark.parametrize("name", sorted(BROKEN))
def test_broken_output_is_sent_back(project, name):
    mutate, expect = BROKEN[name]
    code, _, err = run(CHECK, write_event(project, OUT_A, broken(mutate)), project)
    assert code == 2, name
    assert expect in err, err


def test_invalid_json_is_sent_back(project):
    code, _, err = run(CHECK, write_event(project, OUT_A, '{"review_pmid": "999", '), project)
    assert code == 2
    assert "JSON" in err


def test_screener_cannot_write_other_screeners_folder(project):
    code, _, err = run(CHECK, write_event(project, f"results/screen/b/{RID}/batch_01.json", good_output("b")), project)
    assert code == 2
    assert "results/screen/a/" in err


def test_screener_cannot_write_elsewhere(project):
    code, _, _ = run(CHECK, write_event(project, "notes.md", "x"), project)
    assert code == 2


def test_main_session_writing_screen_output_is_checked_too(project):
    doc = broken(lambda d: d["records"][0]["criteria"].pop(0))
    code, _, _ = run(CHECK, write_event(project, OUT_A, doc, agent=None), project)
    assert code == 2


# ---- adjudicator -------------------------------------------------------------------------------

ADJ_PATH = f"results/adjudication/{RID}.json"
ADJ = {"review_pmid": RID, "records": [
    {"pmid": "1", "status": "agreed_include", "reasons": [], "disagree_criteria": []},
    {"pmid": "2", "status": "needs_human", "reasons": ["overall_disagree"], "disagree_criteria": ["E1"]},
]}


@pytest.fixture
def adj_project(project):
    (project / "results" / "adjudication").mkdir(parents=True)
    (project / ADJ_PATH).write_text(json.dumps(ADJ))
    return project


def with_summary(**changes):
    doc = copy.deepcopy(ADJ)
    doc["records"][1]["summary"] = "E1 で A は総説（-1）、B は原著（1）と判定し、結論が割れた"
    for key, value in changes.items():
        doc["records"][1][key] = value
    return doc


def test_adjudicator_adding_summary_passes(adj_project):
    code, _, err = run(CHECK, write_event(adj_project, ADJ_PATH, with_summary(), agent="adjudicator"), adj_project)
    assert code == 0, err


@pytest.mark.parametrize("changes, expect", [
    ({"status": "agreed_exclude"}, "status を変えない"),
    ({"reasons": []}, "reasons を変えない"),
    ({"summary": ""}, "summary が無い"),
])
def test_adjudicator_changing_rules_is_sent_back(adj_project, changes, expect):
    code, _, err = run(CHECK, write_event(adj_project, ADJ_PATH, with_summary(**changes), agent="adjudicator"),
                       adj_project)
    assert code == 2
    assert expect in err


def test_adjudicator_dropping_a_record_is_sent_back(adj_project):
    doc = with_summary()
    doc["records"].pop(0)
    code, _, err = run(CHECK, write_event(adj_project, ADJ_PATH, doc, agent="adjudicator"), adj_project)
    assert code == 2
    assert "PMID・数・順番" in err


def test_adjudicator_cannot_write_screen_output(adj_project):
    code, _, _ = run(CHECK, write_event(adj_project, OUT_A, good_output(), agent="adjudicator"), adj_project)
    assert code == 2


# ---- SubagentStop: observation only -------------------------------------------------------------

def stop_event(root, message, agent="screener-a"):
    return {"hook_event_name": "SubagentStop", "session_id": "s1", "cwd": str(root), "agent_id": "agent-1",
            "agent_type": agent, "last_assistant_message": message}


def test_subagent_stop_reports_bad_file_without_blocking(project):
    f = project / OUT_A
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps(broken(lambda d: d["records"][0]["criteria"].pop(0))))
    code, out, _ = run(CHECK, stop_event(project, f"wrote {OUT_A} (2 records)"), project)
    assert code == 0  # SubagentStop cannot block
    assert "PMID 1 基準 I1: 無い" in json.loads(out)["systemMessage"]


def test_subagent_stop_quiet_on_good_file(project):
    f = project / OUT_A
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps(good_output()))
    code, out, _ = run(CHECK, stop_event(project, f"wrote {OUT_A} (2 records)"), project)
    assert code == 0
    assert out.strip() == ""


def test_subagent_stop_reports_missing_output(project):
    code, out, _ = run(CHECK, stop_event(project, "done"), project)
    assert code == 0
    assert "パスが無い" in json.loads(out)["systemMessage"]


# ---- agent_gate: at most 6 at once --------------------------------------------------------------

def gate_event(root, name, n, session="s1", agent="screener-a"):
    return {"hook_event_name": name, "session_id": session, "cwd": str(root), "agent_id": f"agent-{n}",
            "agent_type": agent}


def test_gate_allows_six_and_refuses_the_seventh(tmp_path):
    for n in range(6):
        assert run(GATE, gate_event(tmp_path, "SubagentStart", n), tmp_path)[0] == 0
    code, _, err = run(GATE, gate_event(tmp_path, "SubagentStart", 6), tmp_path)
    assert code == 2
    assert "6 まで" in err


def test_gate_frees_a_slot_on_stop(tmp_path):
    for n in range(6):
        run(GATE, gate_event(tmp_path, "SubagentStart", n), tmp_path)
    assert run(GATE, gate_event(tmp_path, "SubagentStop", 0), tmp_path)[0] == 0
    assert run(GATE, gate_event(tmp_path, "SubagentStart", 6), tmp_path)[0] == 0
    assert run(GATE, gate_event(tmp_path, "SubagentStart", 7), tmp_path)[0] == 2


def test_gate_counts_per_session(tmp_path):
    for n in range(6):
        run(GATE, gate_event(tmp_path, "SubagentStart", n, session="s1"), tmp_path)
    assert run(GATE, gate_event(tmp_path, "SubagentStart", 0, session="s2"), tmp_path)[0] == 0


def test_gate_drops_stale_markers(tmp_path):
    for n in range(6):
        run(GATE, gate_event(tmp_path, "SubagentStart", n), tmp_path)
    old = time.time() - 4 * 3600
    for m in (tmp_path / ".claude" / "state" / "running" / "s1").iterdir():
        if not m.name.startswith("."):
            os.utime(m, (old, old))
    assert run(GATE, gate_event(tmp_path, "SubagentStart", 6), tmp_path)[0] == 0


# ---- adjudicator reads only its inputs ---------------------------------------------------------

def read_event(root, path, agent="adjudicator"):
    ev = {"hook_event_name": "PreToolUse", "tool_name": "Read", "session_id": "s1", "cwd": str(root),
          "tool_input": {"file_path": path if path.startswith("/") else str(root / path)}}
    if agent:
        ev["agent_type"] = agent
        ev["agent_id"] = "agent-1"
    return ev


@pytest.mark.parametrize("path", [
    f"results/adjudication/{RID}.json",
    f"results/screen/a/{RID}/batch_01.json",
    f"results/screen/b/{RID}/batch_10.json",
    f"reviews/{RID}/criteria.json",
    f"results/{RID}/candidates.json",
])
def test_adjudicator_reads_inputs(tmp_path, path):
    code, _, err = run(READS, read_event(tmp_path, path), tmp_path)
    assert code == 0, err


@pytest.mark.parametrize("path", [
    "docs/HARNESS.md",
    "CLAUDE.md",
    f"results/batches/{RID}/a/batch_01.json",
    "bench/reviews.jsonl",
    f"results/human/{RID}.json",
    f"reviews/{RID}/criteria.md",
    "../outside.json",
    "/etc/hosts",
])
def test_adjudicator_other_reads_blocked(tmp_path, path):
    code, _, err = run(READS, read_event(tmp_path, path), tmp_path)
    assert code == 2
    assert "入力ファイルだけ" in err


@pytest.mark.parametrize("agent", [None, "screener-a", "query-builder"])
def test_other_agents_read_freely(tmp_path, agent):
    code, _, _ = run(READS, read_event(tmp_path, "docs/HARNESS.md", agent=agent), tmp_path)
    assert code == 0
