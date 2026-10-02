"""scripts/ralph/status.py: the Ralph loop's next-task / STOP decision, and the real plan parses."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ralph_status", ROOT / "scripts" / "ralph" / "status.py")
status = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = status  # dataclasses resolve annotations through sys.modules
spec.loader.exec_module(status)


def block(tid, st="todo", deps="none", owner=None, attempts=None, title="t"):
    lines = [f"### {tid} — {title}", f"- status: {st}"]
    if owner:
        lines.append(f"- owner: {owner}")
    lines.append(f"- deps: {deps}")
    if attempts is not None:
        lines.append(f"- attempts: {attempts}")
    lines.append("- do: something with a - status: lookalike inside free text")
    return "\n".join(lines)


def run(text):
    return status.summarise(status.parse_plan(text))


def test_first_ready_task_in_file_order_respecting_deps():
    plan = "\n\n".join([block("T0.1", "done 2026-10-02"), block("T1.1", deps="T1.2"),
                        block("T1.2", deps="T0.1"), block("T1.3", deps="T0.1")])
    line, code, _ = run(plan)
    assert code == 0 and line.startswith("RALPH-STATUS: CONTINUE next=T1.2 ")
    assert "ready=2" in line


def test_kevin_gate_is_never_ready_and_stop_names_it():
    plan = "\n\n".join([block("T2.8", "done 2026-10-03"), block("G3", owner="kevin", deps="T2.8", title="review"),
                        block("T2.9", deps="G3")])
    line, code, _ = run(plan)
    assert code == status.STOP_EXIT
    assert line.startswith("RALPH-STATUS: STOP nothing-ready") and "waiting on Kevin: G3 (review)" in line


def test_blocked_and_dropped():
    plan = "\n\n".join([block("T1", "blocked (network): run scrape locally"), block("T2", deps="T1"),
                        block("T3", "dropped: out of scope"), block("T4", deps="T3")])
    line, code, _ = run(plan)
    assert code == 0 and "next=T4" in line
    plan = "\n\n".join([block("T1", "blocked (network): run scrape locally"), block("T2", deps="T1")])
    line, code, _ = run(plan)
    assert code == status.STOP_EXIT and "blocked: T1 ((network): run scrape locally)" in line


def test_all_done_stops():
    line, code, _ = run("\n\n".join([block("T1", "done 2026-10-02"), block("T2", "dropped: n/a")]))
    assert code == status.STOP_EXIT and line.startswith("RALPH-STATUS: STOP all-done")


def test_attempts_warning():
    _, _, warnings = run(block("T1", attempts=3))
    assert warnings and "T1 has 3 attempts" in warnings[0]


@pytest.mark.parametrize("text, msg", [
    (block("T1", deps="T9"), "unknown task"),
    (block("T1") + "\n\n" + block("T1"), "duplicate"),
    (block("T1", "finished"), "unknown status"),
    ("### T1 — no status line\n- deps: none", "no '- status:' line"),
    ("### T9.9: colon instead of dash\n- status: todo\n- deps: none", "malformed task header"),
    ("### T1.2.1 — three-level id\n- status: todo\n- deps: none", "malformed task header"),
    ("# nothing here", "no tasks"),
])
def test_malformed_plans_raise(text, msg):
    with pytest.raises(status.PlanError, match=msg):
        status.parse_plan(text)


def test_main_exit_codes(tmp_path, capsys):
    p = tmp_path / "plan.md"
    p.write_text(block("T1", deps="T9"))
    assert status.main(["--plan", str(p)]) == status.PLAN_ERROR_EXIT
    assert "PLAN-ERROR" in capsys.readouterr().out


def test_real_plan_parses():
    tasks = status.parse_plan((ROOT / status.DEFAULT_PLAN).read_text(encoding="utf-8"))
    ids = {t.id for t in tasks}
    assert {"T0.1", "G3", "G4"} <= ids
    assert all(t.owner == "kevin" for t in tasks if t.id.startswith("G"))
