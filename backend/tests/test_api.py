from fastapi.testclient import TestClient

from app.main import app


def test_full_planning_flow(fake_llm):
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"

        r = client.post("/chat", json={"thread_id": "t1", "message": "exam thursday, report, gym, huge task"}).json()
        assert r["status"] == "needs_input" and r["kind"] == "negotiate"
        assert "Huge task" in r["message"]

        r = client.post("/resume", json={"thread_id": "t1", "answer": "drop the huge task"}).json()
        assert r["kind"] == "confirm" and r["plan"]
        assert client.get("/week/t1").json() == {"plan": r["plan"], "approved": False}

        r = client.post("/resume", json={"thread_id": "t1", "answer": "ok"}).json()
        assert r["status"] == "done" and "Plan approved" in r["message"]

        assert client.get("/week/t1").json() == {"plan": r["plan"], "approved": True}
        assert client.post("/resume", json={"thread_id": "t1", "answer": "ok"}).status_code == 409


def test_router_sends_changes_to_replan(fake_llm):
    with TestClient(app) as client:
        client.post("/chat", json={"thread_id": "t2", "message": "plan my week"})
        client.post("/resume", json={"thread_id": "t2", "answer": "drop"})
        client.post("/resume", json={"thread_id": "t2", "answer": "ok"})
        r = client.post("/chat", json={"thread_id": "t2", "message": "move gym to thursday"}).json()
        assert r["status"] == "done" and "Replan" in r["message"]


def test_chat_requires_resume_while_thread_is_paused(fake_llm):
    with TestClient(app) as client:
        request = {"thread_id": "pending", "message": "plan my week"}
        assert client.post("/chat", json=request).json()["kind"] == "negotiate"
        assert client.post("/chat", json=request).status_code == 409
        response = client.post("/resume", json={"thread_id": "pending", "answer": "drop"})
        assert response.json()["kind"] == "confirm"


def test_unknown_thread_and_blank_inputs():
    with TestClient(app) as client:
        assert client.get("/week/missing").status_code == 404
        assert client.post("/resume", json={"thread_id": "missing", "answer": "ok"}).status_code == 404
        assert client.post("/chat", json={"thread_id": "t", "message": " "}).status_code == 422
        assert client.post("/resume", json={"thread_id": "t", "answer": " "}).status_code == 422


# Seed a real checkpoint so these tests exercise /chat, interrupts, /resume, and /week.
def seed_approved_week(client, thread_id):
    plan = [
        {"task": "Exam prep (1/2)", "day": 0, "start": "12:00", "end": "14:00"},
        {"task": "Exam prep (2/2)", "day": 2, "start": "14:00", "end": "16:00"},
        {"task": "Report", "day": 3, "start": "10:00", "end": "11:00"},
    ]
    state = {"plan": plan, "approved": True, "user_id": "demo", "blocked": [],
             "fixed_events": [{"day": 2, "start": "15:00", "end": "15:30"}],
             "preferences": {"day_start": 8, "day_end": 21, "timezone": "Africa/Casablanca"},
             "tasks": [{"title": "Exam prep", "duration_hours": 4, "deadline_day": 3, "priority": 5},
                       {"title": "Report", "duration_hours": 1, "deadline_day": 3, "priority": 3}]}
    client.portal.call(app.state.graph.aupdate_state,
                       {"configurable": {"thread_id": thread_id}}, state, "plan_week")
    return plan


def test_replan_moves_only_affected_session_and_commits_after_approval(fake_llm, scheduler_clock):
    from datetime import datetime, timezone
    from app.agent.state import UnavailableChange

    scheduler_clock(datetime(2026, 11, 25, 12, 10, tzinfo=timezone.utc))
    fake_llm.responses[UnavailableChange] = lambda prompt: UnavailableChange(
        window={"day": 2, "start": "14:00", "end": "17:00"})
    with TestClient(app) as client:
        original = seed_approved_week(client, "replan")
        response = client.post("/chat", json={"thread_id": "replan",
                                             "message": "I'm unavailable Wednesday 14:00–17:00."})
        assert response.status_code == 200
        draft = response.json()
        assert draft["status"] == "needs_input" and draft["kind"] == "confirm"
        assert original[0] in draft["plan"]  # elapsed session
        assert original[2] in draft["plan"]  # unaffected future session
        moved = next(b for b in draft["plan"] if b["task"] == "Exam prep (2/2)")
        assert moved != original[1]
        assert (moved["day"], moved["start"]) >= (2, "13:30")
        assert moved["day"] <= 3
        assert moved["day"] != 2 or moved["end"] <= "14:00" or moved["start"] >= "17:00"
        assert moved["day"] != 3 or moved["end"] <= "10:00" or moved["start"] >= "11:00"
        minutes = lambda value: int(value[:2]) * 60 + int(value[3:])
        assert minutes(moved["end"]) - minutes(moved["start"]) == 120
        assert client.get("/week/replan").json() == {"plan": original, "approved": True}
        result = client.post("/resume", json={"thread_id": "replan", "answer": "approve"})
        assert result.status_code == 200 and result.json()["status"] == "done"
        assert result.json()["plan"] == draft["plan"]
        assert client.get("/week/replan").json() == {"plan": draft["plan"], "approved": True}
        snapshot = client.portal.call(app.state.graph.aget_state, {"configurable": {"thread_id": "replan"}})
        assert snapshot.values["blocked"] == [{"day": 2, "start": "14:00", "end": "17:00", "label": "busy"}]


def test_replan_unscheduled_drop_and_cancel_preserve_approved_week(fake_llm, scheduler_clock):
    from datetime import datetime, timezone
    from app.agent.state import UnavailableChange

    # At Thursday 10:00 the two-hour exam session's deadline leaves no alternative.
    scheduler_clock(datetime(2026, 11, 26, 9, tzinfo=timezone.utc))
    fake_llm.responses[UnavailableChange] = lambda prompt: UnavailableChange(
        window={"day": 3, "start": "10:00", "end": "21:00"})
    with TestClient(app) as client:
        original = seed_approved_week(client, "drop-change")
        original[1] = {**original[1], "day": 3, "start": "12:00", "end": "14:00"}
        client.portal.call(app.state.graph.aupdate_state,
                           {"configurable": {"thread_id": "drop-change"}}, {"plan": original}, "plan_week")
        def request():
            return client.post("/chat", json={"thread_id": "drop-change",
                                              "message": "I'm unavailable Thursday 10:00–21:00."})
        draft = request().json()
        assert draft["kind"] == "negotiate"
        assert "Exam prep (2/2)" in draft["message"]
        assert client.get("/week/drop-change").json() == {"plan": original, "approved": True}
        cancelled = client.post("/resume", json={"thread_id": "drop-change", "answer": "cancel"})
        assert cancelled.json()["status"] == "done"
        assert client.get("/week/drop-change").json() == {"plan": original, "approved": True}
        assert request().json()["kind"] == "negotiate"
        confirm = client.post("/resume", json={"thread_id": "drop-change", "answer": "drop"}).json()
        assert confirm["kind"] == "confirm"
        assert client.get("/week/drop-change").json() == {"plan": original, "approved": True}
        result = client.post("/resume", json={"thread_id": "drop-change", "answer": "approve"}).json()
        assert result["status"] == "done" and result["plan"] == [original[0]]
        assert client.get("/week/drop-change").json() == {"plan": [original[0]], "approved": True}


def test_replan_keeps_started_session_and_allows_correcting_or_rejecting_draft(fake_llm, scheduler_clock):
    from datetime import datetime, timezone
    from app.agent.state import UnavailableChange

    scheduler_clock(datetime(2026, 11, 25, 12, 10, tzinfo=timezone.utc))  # local 13:10
    fake_llm.responses[UnavailableChange] = lambda prompt: UnavailableChange(
        window={"day": 2, "start": "12:00", "end": "17:00"})
    with TestClient(app) as client:
        original = seed_approved_week(client, "correct-change")
        original[0] = {**original[0], "day": 2}  # already in progress, overlaps new absence
        client.portal.call(app.state.graph.aupdate_state,
                           {"configurable": {"thread_id": "correct-change"}}, {"plan": original}, "plan_week")
        draft = client.post("/chat", json={"thread_id": "correct-change",
                                           "message": "I'm unavailable Wednesday 12:00–17:00."}).json()
        assert draft["kind"] == "confirm"
        assert original[0] in draft["plan"]
        assert original[1] not in draft["plan"]
        # Correct the proposal to a window that affects none of the original sessions.
        fake_llm.responses[UnavailableChange] = lambda prompt: UnavailableChange(
            window={"day": 4, "start": "14:00", "end": "17:00"})
        revised = client.post("/resume", json={"thread_id": "correct-change",
                                               "answer": "I meant Friday 14:00–17:00."}).json()
        assert revised["kind"] == "confirm" and revised["plan"] == original
        assert client.get("/week/correct-change").json() == {"plan": original, "approved": True}
        rejected = client.post("/resume", json={"thread_id": "correct-change", "answer": "no"}).json()
        assert rejected["status"] == "done" and rejected["plan"] == original
        snapshot = client.portal.call(app.state.graph.aget_state,
                                      {"configurable": {"thread_id": "correct-change"}})
        assert snapshot.values["blocked"] == []
        assert snapshot.values["proposed_plan"] == []
