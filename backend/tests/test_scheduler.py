from app.agent.tools.scheduler import solve_schedule

PREFS = {"day_start": 8, "day_end": 21}


def _overlaps(plan, busy):
    blocks = [(p["day"], p["start"], p["end"]) for p in plan] + [(b["day"], b["start"], b["end"]) for b in busy]
    for i, a in enumerate(blocks):
        for b in blocks[i + 1:]:
            if a[0] == b[0] and a[1] < b[2] and b[1] < a[2]:
                return True
    return False


def test_fits_and_respects_constraints():
    tasks = [{"title": "Exam prep", "duration_hours": 5, "deadline_day": 2, "priority": 5},
             {"title": "Gym", "duration_hours": 1, "deadline_day": 6, "priority": 2}]
    busy = [{"day": 0, "start": "09:00", "end": "12:00"}]
    plan, unscheduled = solve_schedule(tasks, busy, PREFS)
    assert unscheduled == []
    assert not _overlaps(plan, busy)
    assert all(p["day"] <= 2 for p in plan if p["task"].startswith("Exam prep"))
    assert sum(1 for p in plan if p["task"].startswith("Exam prep")) == 3  # 5h -> 2h+2h+1h


def test_impossible_task_is_dropped_not_everything():
    tasks = [{"title": "Small", "duration_hours": 1, "deadline_day": 6, "priority": 3},
             {"title": "Impossible", "duration_hours": 80, "deadline_day": 0, "priority": 1}]
    plan, unscheduled = solve_schedule(tasks, [], PREFS)
    assert unscheduled == ["Impossible"]
    assert [p["task"] for p in plan] == ["Small"]
