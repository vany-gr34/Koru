"""Parent graph: router -> one of the subgraphs."""

from langgraph.graph import END, START, StateGraph

from app.agent.router import pick_subgraph, route
from app.agent.state import PlannerState
from app.agent.subgraphs.plan import build_plan_subgraph
from app.agent.subgraphs.replan import build_replan_subgraph
from app.agent.subgraphs.review import build_review_subgraph


def build_graph(checkpointer):
    g = StateGraph(PlannerState)
    g.add_node("router", route)
    g.add_node("plan_week", build_plan_subgraph())
    g.add_node("replan", build_replan_subgraph())
    g.add_node("review", build_review_subgraph())

    g.add_edge(START, "router")
    g.add_conditional_edges("router", pick_subgraph, ["plan_week", "replan", "review"])
    for sub in ("plan_week", "replan", "review"):
        g.add_edge(sub, END)
    return g.compile(checkpointer=checkpointer)
