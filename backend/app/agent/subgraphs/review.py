"""Review subgraph — placeholder (phase 6).

Planned flow: ask what got done -> compare planned vs actual -> save to task_history
-> summary card (completion rate, streak, estimate accuracy).
"""

from langgraph.graph import END, START, StateGraph

from app.agent.state import PlannerState


def review_stub(state: PlannerState) -> dict:
    n = len(state.get("plan", []))
    return {"response": f"(Review coming soon) You had {n} planned sessions this week."}


def build_review_subgraph():
    g = StateGraph(PlannerState)
    g.add_node("review", review_stub)
    g.add_edge(START, "review")
    g.add_edge("review", END)
    return g.compile()
