from typing import Literal, TypedDict

from pydantic import BaseModel, Field

Intent = Literal["plan_week", "replan", "review"]


# ---------- LLM structured-output schemas ----------
class Task(BaseModel):
    title: str
    duration_hours: float = Field(gt=0, description="Total effort needed this week")
    deadline_day: int = Field(6, ge=0, le=6, description="0=Mon..6=Sun, last day it can be worked on")
    priority: int = Field(3, ge=1, le=5, description="5 = most important")


class Block(BaseModel):
    """Time the user is NOT available."""
    day: int = Field(ge=0, le=6)
    start: str = Field(description="HH:MM")
    end: str = Field(description="HH:MM")
    label: str = "busy"


class ParsedWeek(BaseModel):
    tasks: list[Task]
    blocked: list[Block] = []


class RouteDecision(BaseModel):
    intent: Intent


class UnavailableChange(BaseModel):
    window: Block | None = Field(
        default=None, description="One new unavailable window, or null for unsupported changes")


# ---------- Graph state (shared by the parent graph and all subgraphs) ----------
class PlannerState(TypedDict, total=False):
    user_id: str
    user_input: str          # latest user message
    intent: Intent
    feedback: list[str]      # corrections given during the current planning round
    preferences: dict
    fixed_events: list[dict]
    tasks: list[dict]
    blocked: list[dict]
    plan: list[dict]
    proposed_plan: list[dict]
    proposed_blocked: list[dict]
    unscheduled: list[str]
    approved: bool
    response: str            # final message for the user
