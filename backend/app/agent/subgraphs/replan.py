"""Replan subgraph — placeholder (phase 3).

Planned flow: understand the change -> free/block affected time -> keep past and unaffected
blocks fixed -> re-run the solver -> confirm -> commit.
"""

from langgraph.graph import END, START, StateGraph

from app.agent.state import PlannerState


def replan_stub(state: PlannerState) -> dict:
    return {"response": f"(Replan coming soon) I heard: {state['user_input']!r}"}


def build_replan_subgraph():
    g = StateGraph(PlannerState)
    g.add_node("replan", replan_stub)
    g.add_edge(START, "replan")
    g.add_edge("replan", END)
    return g.compile()
