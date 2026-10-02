#!/usr/bin/env python3
"""Ralph loop status: read IMPLEMENTATION_PLAN.md and say whether the loop should go on.

    python3 scripts/ralph/status.py [--plan PATH]

Stdlib only, so it runs before the venv exists. The last line printed is always one of

    RALPH-STATUS: CONTINUE next=<id> (<title>) | ready=.. todo=.. done=.. blocked=.. waiting-kevin=..
    RALPH-STATUS: STOP all-done | ...
    RALPH-STATUS: STOP nothing-ready | waiting on Kevin: ...; blocked: ... | ...

Exit codes: 0 CONTINUE, 3 STOP, 2 the plan file is malformed (fix it before anything else).

Plan format (one block per task, in priority order):

    ### T1.2 — Title
    - status: todo | done <date> | blocked (<who>): <why> | dropped: <why>
    - owner: agent | kevin          (optional, default agent; kevin = a human gate)
    - deps: T1.1, T0.2 | none
    - attempts: 0                   (optional)

A task is ready when its status is todo, its owner is agent and every dep is done or dropped.
The next task is the first ready one in file order.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

DEFAULT_PLAN = Path("plans/2026-10-02-ralph-phases-3-5/IMPLEMENTATION_PLAN.md")
HEADER_RE = re.compile(r"^###\s+(?P<id>[A-Z]\d+(?:\.\d+)?[a-z]?)\s+[—–-]\s+(?P<title>.+?)\s*$")
TASKLIKE_RE = re.compile(r"^###\s+[A-Z]\d")  # looks like a task header; must then match HEADER_RE
FIELD_RE = re.compile(r"^-\s+(?P<key>status|owner|deps|attempts):\s*(?P<value>.*?)\s*$")
STATUSES = ("todo", "done", "blocked", "dropped")
STOP_EXIT, PLAN_ERROR_EXIT = 3, 2


@dataclass
class Task:
    id: str
    title: str
    line: int
    status: Optional[str] = None
    status_detail: str = ""
    owner: str = "agent"
    deps: List[str] = field(default_factory=list)
    attempts: int = 0


class PlanError(ValueError):
    pass


def parse_plan(text: str) -> List[Task]:
    tasks: List[Task] = []
    current: Optional[Task] = None
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        m = HEADER_RE.match(line)
        if m:
            current = Task(m["id"], m["title"], n)
            tasks.append(current)
            continue
        if TASKLIKE_RE.match(line):
            raise PlanError(f"line {n}: malformed task header {line!r} "
                            f"(want '### T1.2 — Title' or '### T1.2a — Title')")
        if line.startswith("## ") or (line.startswith("### ") and not m):
            current = None
            continue
        if current is None:
            continue
        f = FIELD_RE.match(line)
        if not f:
            continue
        key, value = f["key"], f["value"]
        if key == "status":
            word = re.split(r"[\s(:]", value, maxsplit=1)[0].lower()
            if word not in STATUSES:
                raise PlanError(f"line {n}: {current.id} has unknown status {value!r} (want one of {STATUSES})")
            current.status, current.status_detail = word, value[len(word):].strip(" :")
        elif key == "owner":
            if value not in ("agent", "kevin"):
                raise PlanError(f"line {n}: {current.id} owner must be agent or kevin, got {value!r}")
            current.owner = value
        elif key == "deps":
            current.deps = [] if value.lower() in ("", "none", "-") else [d.strip() for d in value.split(",") if d.strip()]
        elif key == "attempts":
            try:
                current.attempts = int(value.split()[0])
            except (ValueError, IndexError):
                raise PlanError(f"line {n}: {current.id} attempts must be an integer, got {value!r}") from None
    ids = [t.id for t in tasks]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise PlanError(f"duplicate task ids: {', '.join(dupes)}")
    known = set(ids)
    for t in tasks:
        if t.status is None:
            raise PlanError(f"line {t.line}: {t.id} has no '- status:' line")
        missing = [d for d in t.deps if d not in known]
        if missing:
            raise PlanError(f"line {t.line}: {t.id} depends on unknown task(s) {', '.join(missing)}")
    if not tasks:
        raise PlanError("no tasks found (expected '### <ID> — <title>' headers)")
    return tasks


def summarise(tasks: List[Task]) -> tuple[str, int, List[str]]:
    by_id = {t.id: t for t in tasks}
    satisfied = lambda t: all(by_id[d].status in ("done", "dropped") for d in t.deps)
    ready = [t for t in tasks if t.status == "todo" and t.owner == "agent" and satisfied(t)]
    waiting = [t for t in tasks if t.status == "todo" and t.owner == "kevin" and satisfied(t)]
    blocked = [t for t in tasks if t.status == "blocked"]
    count = lambda s: sum(1 for t in tasks if t.status == s)
    tally = (f"ready={len(ready)} todo={count('todo')} done={count('done')} "
             f"blocked={len(blocked)} dropped={count('dropped')} waiting-kevin={len(waiting)}")
    warnings = [f"WARNING: {t.id} has {t.attempts} attempts and is still todo; "
                f"block it with the reason if this iteration can't finish it"
                for t in tasks if t.status == "todo" and t.attempts >= 3]
    if ready:
        nxt = ready[0]
        return f"RALPH-STATUS: CONTINUE next={nxt.id} ({nxt.title}) | {tally}", 0, warnings
    if all(t.status in ("done", "dropped") for t in tasks):
        return f"RALPH-STATUS: STOP all-done | {tally}", STOP_EXIT, warnings
    parts = []
    if waiting:
        parts.append("waiting on Kevin: " + "; ".join(f"{t.id} ({t.title})" for t in waiting))
    if blocked:
        parts.append("blocked: " + "; ".join(f"{t.id} ({t.status_detail or 'no reason given'})" for t in blocked))
    if not parts:
        parts.append("remaining todo tasks wait on blocked or Kevin-owned tasks further up the chain")
    return f"RALPH-STATUS: STOP nothing-ready | {' | '.join(parts)} | {tally}", STOP_EXIT, warnings


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    args = ap.parse_args(argv)
    try:
        tasks = parse_plan(args.plan.read_text(encoding="utf-8"))
    except (OSError, PlanError) as exc:
        print(f"RALPH-STATUS: PLAN-ERROR {exc}")
        return PLAN_ERROR_EXIT
    line, code, warnings = summarise(tasks)
    for w in warnings:
        print(w)
    print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
