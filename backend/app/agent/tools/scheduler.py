"""CP-SAT scheduler: places task sessions into free time.

Hard constraints: no overlaps, sessions inside working hours, finish before deadline.
Objective: maximize priority-weighted scheduled hours. A task is fully scheduled or dropped,
so the agent can negotiate the dropped ones with the user.
TODO: daily hour cap, spreading work across days, preferred times, breaks.
"""

import math

from ortools.sat.python import cp_model

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SLOT_MIN = 30
MAX_SESSION_SLOTS = 4  # 2h max per session


def _to_slot(day: int, hhmm: str, day_start: int, spd: int, ceil: bool = False) -> int:
    h, m = map(int, hhmm.split(":"))
    minutes = max(0, min((h - day_start) * 60 + m, spd * SLOT_MIN))
    idx = math.ceil(minutes / SLOT_MIN) if ceil else minutes // SLOT_MIN
    return day * spd + idx


def _to_time(slot_in_day: int, day_start: int) -> str:
    minutes = day_start * 60 + slot_in_day * SLOT_MIN
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def solve_schedule(tasks: list[dict], busy: list[dict], prefs: dict,
                   time_limit_s: float = 10) -> tuple[list[dict], list[str]]:
    day_start, day_end = prefs["day_start"], prefs["day_end"]
    spd = (day_end - day_start) * 60 // SLOT_MIN  # slots per day
    m = cp_model.CpModel()
    intervals, sessions, objective, present_vars = [], [], [], []

    for ev in busy:
        s = _to_slot(ev["day"], ev["start"], day_start, spd)
        e = _to_slot(ev["day"], ev["end"], day_start, spd, ceil=True)
        if e > s:
            intervals.append(m.NewFixedSizeIntervalVar(s, e - s, "busy"))

    for ti, t in enumerate(tasks):
        present = m.NewBoolVar(f"present_{ti}")
        present_vars.append(present)
        total = math.ceil(t["duration_hours"] * 60 / SLOT_MIN)
        chunks = [MAX_SESSION_SLOTS] * (total // MAX_SESSION_SLOTS)
        if total % MAX_SESSION_SLOTS:
            chunks.append(total % MAX_SESSION_SLOTS)

        prev_end = None
        for ci, length in enumerate(chunks):
            day = m.NewIntVar(0, t["deadline_day"], f"day_{ti}_{ci}")  # also enforces deadline
            offset = m.NewIntVar(0, spd - length, f"off_{ti}_{ci}")
            start = m.NewIntVar(0, 7 * spd, f"start_{ti}_{ci}")
            m.Add(start == day * spd + offset)
            if prev_end is not None:
                m.Add(start >= prev_end).OnlyEnforceIf(present)
            prev_end = start + length
            intervals.append(m.NewOptionalIntervalVar(start, length, start + length, present, f"iv_{ti}_{ci}"))
            sessions.append((ti, ci, len(chunks), day, offset, length))
        objective.append(t["priority"] * total * present)

    m.AddNoOverlap(intervals)
    m.Maximize(sum(objective))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    if solver.Solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return [], [t["title"] for t in tasks]

    kept = [bool(solver.Value(p)) for p in present_vars]
    plan = []
    for ti, ci, n, day, offset, length in sessions:
        if not kept[ti]:
            continue
        o = solver.Value(offset)
        plan.append({
            "task": tasks[ti]["title"] + (f" ({ci + 1}/{n})" if n > 1 else ""),
            "day": solver.Value(day),
            "start": _to_time(o, day_start),
            "end": _to_time(o + length, day_start),
        })
    plan.sort(key=lambda p: (p["day"], p["start"]))
    unscheduled = [t["title"] for t, k in zip(tasks, kept) if not k]
    return plan, unscheduled


def format_plan(plan: list[dict]) -> str:
    return "\n".join(f"{DAYS[p['day']]} {p['start']}-{p['end']}  {p['task']}" for p in plan)
