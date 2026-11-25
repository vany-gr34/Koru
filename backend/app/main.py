from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI
from langgraph.types import Command
from pydantic import BaseModel

from app.agent.graph import build_graph
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.database_url:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(settings.database_url) as saver:
            await saver.setup()  # creates checkpoint tables if missing
            app.state.graph = build_graph(saver)
            yield
    else:
        from langgraph.checkpoint.memory import MemorySaver

        app.state.graph = build_graph(MemorySaver())
        yield


app = FastAPI(title="Weekly Planner Agent", lifespan=lifespan)


class ChatRequest(BaseModel):
    thread_id: str
    message: str
    user_id: str = "demo"


class ResumeRequest(BaseModel):
    thread_id: str
    answer: str


class AgentReply(BaseModel):
    status: Literal["needs_input", "done"]
    kind: str | None = None          # "negotiate" | "confirm" when needs_input
    message: str
    plan: list[dict[str, Any]] = []


def _to_reply(result: dict) -> AgentReply:
    if "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        return AgentReply(status="needs_input", kind=payload.get("kind"),
                          message=payload["message"], plan=payload.get("plan", []))
    return AgentReply(status="done", message=result.get("response", ""), plan=result.get("plan", []))


@app.get("/health")
async def health():
    return {"status": "ok", "persistence": "postgres" if settings.database_url else "memory"}


@app.post("/chat", response_model=AgentReply)
async def chat(req: ChatRequest):
    config = {"configurable": {"thread_id": req.thread_id}}
    result = await app.state.graph.ainvoke({"user_input": req.message, "user_id": req.user_id}, config)
    return _to_reply(result)


@app.post("/resume", response_model=AgentReply)
async def resume(req: ResumeRequest):
    config = {"configurable": {"thread_id": req.thread_id}}
    result = await app.state.graph.ainvoke(Command(resume=req.answer), config)
    return _to_reply(result)


@app.get("/week/{thread_id}")
async def week(thread_id: str):
    snap = await app.state.graph.aget_state({"configurable": {"thread_id": thread_id}})
    return {"plan": snap.values.get("plan", []), "approved": snap.values.get("approved", False)}
