from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.agent.subgraphs.plan import schedule
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


def test_current_week_from_wednesday_respects_now_deadline_and_busy(scheduler_clock):
    # 12:10 UTC is 13:10 in the user's timezone; partial slots are unavailable.
    instant = datetime(2026, 11, 25, 12, 10, tzinfo=timezone.utc)
    scheduler_clock(instant)
    busy = [{"day": 2, "start": "14:00", "end": "17:00"}]
    result = schedule({
        "tasks": [{"title": "Exam prep", "duration_hours": 2,
                   "deadline_day": 3, "priority": 5}],
        "fixed_events": [], "blocked": busy,
        "preferences": {**PREFS, "timezone": "Africa/Casablanca"},
    })
    assert result["unscheduled"] == []
    plan = result["plan"]
    assert not _overlaps(plan, busy)
    monday = datetime(2026, 11, 23, tzinfo=ZoneInfo("Africa/Casablanca"))
    duration = timedelta()
    for block in plan:
        def at(value):
            hour, minute = map(int, value.split(":"))
            return monday + timedelta(days=block["day"], hours=hour, minutes=minute)
        assert at(block["start"]) > instant
        assert block["day"] <= 3
        duration += at(block["end"]) - at(block["start"])
    assert duration == timedelta(hours=2)


@pytest.mark.parametrize(("instant", "expected_day", "expected_start"), [
    ("2026-11-25T12:00:01+00:00", 2, "13:30"),
    ("2026-11-25T05:00:00+00:00", 2, "08:00"),
    ("2026-11-25T20:00:00+00:00", 3, "08:00"),
    ("2026-11-24T23:10:00+00:00", 2, "08:00"),
])
def test_cutoff_uses_local_time_and_rounds_up(instant, expected_day, expected_start):
    plan, dropped = solve_schedule(
        [{"title": "Task", "duration_hours": .5, "deadline_day": 3, "priority": 3}],
        [], {**PREFS, "timezone": "Africa/Casablanca"},
        now=datetime.fromisoformat(instant))
    assert dropped == []
    assert (plan[0]["day"], plan[0]["start"]) >= (expected_day, expected_start)


def test_expired_deadline_drops_only_unavailable_task():
    tasks = [{"title": "Expired", "duration_hours": 2, "deadline_day": 1, "priority": 5},
             {"title": "Possible", "duration_hours": 2, "deadline_day": 3, "priority": 3}]
    plan, dropped = solve_schedule(tasks, [], PREFS,
                                  now=datetime(2026, 11, 25, 12, tzinfo=timezone.utc))
    assert dropped == ["Expired"]
    assert [block["task"] for block in plan] == ["Possible"]


def test_no_time_left_in_week():
    plan, dropped = solve_schedule(
        [{"title": "Task", "duration_hours": 2, "deadline_day": 6, "priority": 3}],
        [], PREFS, now=datetime(2026, 11, 29, 21, tzinfo=timezone.utc))
    assert plan == []
    assert dropped == ["Task"]
