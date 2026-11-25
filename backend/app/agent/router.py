from app.agent.state import PlannerState, RouteDecision
from app.agent.tools.llm import get_llm

ROUTER_PROMPT = """Classify the user's message about their weekly schedule.
- plan_week: they describe tasks/deadlines to plan a (new) week
- replan: they want to change an existing plan (move, cancel, lost time, sick...)
- review: they ask how their week went / want a summary of what got done
Has a plan already been made this week? {has_plan}

Message: {message}"""


def route(state: PlannerState) -> dict:
    llm = get_llm().with_structured_output(RouteDecision)
    decision: RouteDecision = llm.invoke(ROUTER_PROMPT.format(
        has_plan="yes" if state.get("plan") else "no",
        message=state["user_input"],
    ))
    intent = decision.intent
    if intent != "plan_week" and not state.get("plan"):
        intent = "plan_week"  # nothing to replan/review yet
    return {"intent": intent}


def pick_subgraph(state: PlannerState) -> str:
    return state["intent"]
