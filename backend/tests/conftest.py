"""Fake LLM so tests run offline and without an API key."""

import pytest

from app.agent.state import ParsedWeek, RouteDecision


class FakeStructured:
    def __init__(self, schema, responses):
        self.schema, self.responses = schema, responses

    def invoke(self, prompt):
        return self.responses[self.schema](prompt)


class FakeLLM:
    def __init__(self, responses):
        self.responses = responses

    def with_structured_output(self, schema):
        return FakeStructured(schema, self.responses)


def default_parse(prompt: str) -> ParsedWeek:
    tasks = [
        {"title": "Study for exam", "duration_hours": 6, "deadline_day": 3, "priority": 5},
        {"title": "Report A", "duration_hours": 3, "deadline_day": 4, "priority": 4},
        {"title": "Gym", "duration_hours": 1, "deadline_day": 6, "priority": 2},
    ]
    if "drop the huge task" not in prompt:
        tasks.append({"title": "Huge task", "duration_hours": 80, "deadline_day": 1, "priority": 1})
    return ParsedWeek.model_validate({"tasks": tasks, "blocked": [
        {"day": 2, "start": "13:00", "end": "21:00", "label": "gone"}]})


def default_route(prompt: str) -> RouteDecision:
    return RouteDecision(intent="replan" if "move" in prompt.lower() else "plan_week")


@pytest.fixture
def fake_llm(monkeypatch):
    llm = FakeLLM({ParsedWeek: default_parse, RouteDecision: default_route})
    for mod in ("app.agent.router", "app.agent.subgraphs.plan"):
        monkeypatch.setattr(f"{mod}.get_llm", lambda: llm)
    return llm
