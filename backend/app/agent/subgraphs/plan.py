"""Plan-the-week subgraph.

load_context -> parse -> schedule -> negotiate (if something doesn't fit) -> confirm -> commit
negotiate/confirm pause the graph with interrupt() and wait for the user.
"""

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.agent.state import ParsedWeek, PlannerState
from app.agent.tools import calendar, memory
from app.agent.tools.llm import get_llm
from app.agent.tools.scheduler import format_plan, solve_schedule

PARSE_PROMPT = """Extract this week's tasks and the times the user is unavailable.
Days: 0=Mon ... 6=Sun. Estimate realistic durations if not given.
Later feedback overrides the original request.

Request:
{request}

Feedback so far:
{feedback}"""

APPROVE_WORDS = {"ok", "yes", "approve", "looks good", "go"}


def load_context(state: PlannerState) -> dict:
    uid = state.get("user_id", "demo")
    return {
        "fixed_events": calendar.get_week_events(uid),
        "preferences": memory.get_preferences(uid),
        "feedback": [],
        "approved": False,
    }


def parse(state: PlannerState) -> dict:
    llm = get_llm().with_structured_output(ParsedWeek)
    feedback = "\n".join(f"- {f}" for f in state.get("feedback", [])) or "none"
    parsed: ParsedWeek = llm.invoke(PARSE_PROMPT.format(request=state["user_input"], feedback=feedback))
    return {"tasks": [t.model_dump() for t in parsed.tasks],
            "blocked": [b.model_dump() for b in parsed.blocked]}


def schedule(state: PlannerState) -> dict:
    busy = state["fixed_events"] + state.get("blocked", [])
    plan, unscheduled = solve_schedule(state["tasks"], busy, state["preferences"])
    return {"plan": plan, "unscheduled": unscheduled}


def negotiate(state: PlannerState) -> Command:
    answer = interrupt({
        "kind": "negotiate",
        "message": f"I can't fit: {', '.join(state['unscheduled'])}. "
                   "Say 'drop' to continue without them, or tell me what to change.",
        "plan": state["plan"],
    })
    if answer.strip().lower() == "drop":
        return Command(goto="confirm")
    return Command(goto="parse", update={"feedback": state.get("feedback", []) + [answer]})


def confirm(state: PlannerState) -> Command:
    answer = interrupt({
        "kind": "confirm",
        "message": "Here's your week. Approve it, or tell me what to change.",
        "plan": state["plan"],
    })
    if answer.strip().lower() in APPROVE_WORDS:
        return Command(goto="commit")
    return Command(goto="parse", update={"feedback": state.get("feedback", []) + [answer]})


def commit(state: PlannerState) -> dict:
    n = calendar.write_plan(state.get("user_id", "demo"), state["plan"])
    return {"approved": True, "response": f"Saved {n} sessions to your calendar.\n{format_plan(state['plan'])}"}


def build_plan_subgraph():
    g = StateGraph(PlannerState)
    for name, fn in [("load_context", load_context), ("parse", parse), ("schedule", schedule),
                     ("negotiate", negotiate), ("confirm", confirm), ("commit", commit)]:
        g.add_node(name, fn)
    g.add_edge(START, "load_context")
    g.add_edge("load_context", "parse")
    g.add_edge("parse", "schedule")
    g.add_conditional_edges("schedule", lambda s: "negotiate" if s["unscheduled"] else "confirm",
                            ["negotiate", "confirm"])
    g.add_edge("commit", END)
    return g.compile()
