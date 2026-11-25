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

        r = client.post("/resume", json={"thread_id": "t1", "answer": "ok"}).json()
        assert r["status"] == "done" and "Saved" in r["message"]

        assert client.get("/week/t1").json()["approved"] is True


def test_router_sends_changes_to_replan(fake_llm):
    with TestClient(app) as client:
        client.post("/chat", json={"thread_id": "t2", "message": "plan my week"})
        client.post("/resume", json={"thread_id": "t2", "answer": "drop"})
        client.post("/resume", json={"thread_id": "t2", "answer": "ok"})
        r = client.post("/chat", json={"thread_id": "t2", "message": "move gym to thursday"}).json()
        assert r["status"] == "done" and "Replan" in r["message"]
