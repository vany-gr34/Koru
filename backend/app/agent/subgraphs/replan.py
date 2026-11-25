"""Propose one added unavailable window without replacing the approved week."""

import re
from datetime import time

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.agent.state import PlannerState, UnavailableChange
from app.agent.subgraphs.plan import APPROVE_WORDS
from app.agent.tools.llm import get_llm
from app.agent.tools.scheduler import format_plan, local_now, solve_schedule

PROMPT = """Extract one new unavailable time window for the current week.
Days: 0=Monday ... 6=Sunday; times must be HH:MM, start before end on the same day.
Only adding an unavailable window is supported. Return window=null for other changes,
multiple windows, or missing/ambiguous day or times. Do not invent missing times.
Later feedback corrects the requested window.
Request: {request}
Feedback: {feedback}"""


def prepare(state: PlannerState) -> dict:
    return {"feedback": [], "proposed_plan": [], "proposed_blocked": [], "unscheduled": []}


def propose(state: PlannerState) -> Command:
    if not state.get("approved"):
        return Command(goto=END, update={"response": "Approve a week before changing it."})
    change = get_llm().with_structured_output(UnavailableChange).invoke(
        PROMPT.format(request=state["user_input"], feedback="\n".join(state.get("feedback", []))))
    window = change.window
    if window is None:
        return Command(goto=END, update={"response":
            "Replanning currently supports one new unavailable window. Please give its day, start, and end time."})
    try:
        start, end = time.fromisoformat(window.start), time.fromisoformat(window.end)
        valid = (re.fullmatch(r"\d{2}:\d{2}", window.start)
                 and re.fullmatch(r"\d{2}:\d{2}", window.end) and start < end)
    except ValueError:
        valid = False
    if not valid:
        return Command(goto=END, update={"response": "Please give a valid same-day window in HH:MM format."})

    now = local_now(state["preferences"])
    current_minute = now.hour * 60 + now.minute + now.second / 60 + now.microsecond / 60_000_000
    kept, affected = [], []
    for session in state["plan"]:
        hour, minute = map(int, session["start"].split(":"))
        future = (session["day"], hour * 60 + minute) >= (now.weekday(), current_minute)
        overlaps = (session["day"] == window.day and session["start"] < window.end
                    and window.start < session["end"])
        if not (future and overlaps):
            kept.append(session)  # elapsed, in-progress, and unaffected sessions stay fixed
            continue
        # Existing plans store display titles, including the scheduler's chunk suffix.
        matches = [task for task in state["tasks"] if session["task"] == task["title"]
                   or re.fullmatch(re.escape(task["title"]) + r" \(\d+/\d+\)", session["task"])]
        if len(matches) != 1:
            return Command(goto=END, update={"response":
                "I couldn't identify this session's original deadline. Your approved week is unchanged."})
        end_hour, end_minute = map(int, session["end"].split(":"))
        affected.append({**matches[0], "title": session["task"],
                         "duration_hours": (end_hour * 60 + end_minute - hour * 60 - minute) / 60})

    blocked = state.get("blocked", []) + [window.model_dump()]
    busy = state.get("fixed_events", []) + blocked + kept
    moved, unscheduled = solve_schedule(affected, busy, state["preferences"], now=now)
    proposal = sorted(kept + moved, key=lambda b: (b["day"], b["start"]))
    return Command(goto="negotiate" if unscheduled else "confirm", update={
        "proposed_plan": proposal, "proposed_blocked": blocked, "unscheduled": unscheduled})


def _answer(state: PlannerState, kind: str, message: str) -> str:
    return interrupt({"kind": kind, "message": message, "plan": state["proposed_plan"]}).strip()


def _feedback(state: PlannerState, answer: str) -> Command:
    if answer.lower() in {"cancel", "no", "reject"}:
        return Command(goto=END, update={"proposed_plan": [], "proposed_blocked": [],
                                        "unscheduled": [], "response": "Change cancelled. Your approved week is unchanged."})
    return Command(goto="propose", update={"feedback": state.get("feedback", []) + [answer]})


def negotiate(state: PlannerState) -> Command:
    answer = _answer(state, "negotiate", f"I can't fit: {', '.join(state['unscheduled'])}. "
                     "Say 'drop' to continue without them, correct the window, or say 'cancel'.")
    if answer.lower() == "drop":
        return Command(goto="confirm")
    return _feedback(state, answer)


def confirm(state: PlannerState) -> Command:
    answer = _answer(state, "confirm", "Approve this revised week, correct the window, or say 'cancel'.")
    if answer.lower() in APPROVE_WORDS:
        return Command(goto="commit")
    return _feedback(state, answer)


def commit(state: PlannerState) -> dict:
    return {"plan": state["proposed_plan"], "blocked": state["proposed_blocked"],
            "approved": True, "proposed_plan": [], "proposed_blocked": [],
            "response": f"Revised plan approved.\n{format_plan(state['proposed_plan'])}"}


def build_replan_subgraph():
    graph = StateGraph(PlannerState)
    for name, fn in [("prepare", prepare), ("propose", propose), ("negotiate", negotiate),
                     ("confirm", confirm), ("commit", commit)]:
        graph.add_node(name, fn)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "propose")
    graph.add_edge("commit", END)
    return graph.compile()
