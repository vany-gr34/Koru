from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Path as PathParam, Request
from langgraph.types import Command, Interrupt, StateSnapshot
from pydantic import BaseModel, Field, StringConstraints

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


NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
InterruptKind = Literal["negotiate", "confirm"]


class ChatRequest(BaseModel):
    thread_id: NonBlank
    message: NonBlank
    user_id: NonBlank = "demo"


class ResumeRequest(BaseModel):
    thread_id: NonBlank
    answer: NonBlank


class PlanBlock(BaseModel):
    task: str
    day: int = Field(ge=0, le=6, description="Monday is 0 and Sunday is 6.")
    start: str
    end: str


class AgentReply(BaseModel):
    status: Literal["needs_input", "done"]
    kind: InterruptKind | None = None
    message: str
    plan: list[PlanBlock] = Field(default_factory=list)


class WeekReply(BaseModel):
    plan: list[PlanBlock] = Field(default_factory=list)
    approved: bool = False


def _to_reply(result: dict) -> AgentReply:
    interrupts = result.get("__interrupt__")
    if interrupts:
        payload = interrupts[0].value
        return AgentReply(
            status="needs_input",
            kind=payload["kind"],
            message=payload["message"],
            plan=payload.get("plan", []),
        )
    return AgentReply(
        status="done",
        message=result.get("response", ""),
        plan=result.get("plan", []),
    )


def _thread_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _pending_interrupt(snapshot: StateSnapshot) -> Interrupt | None:
    return next((interrupt for task in snapshot.tasks for interrupt in task.interrupts), None)


@app.get("/health")
async def health():
    return {"status": "ok", "persistence": "postgres" if settings.database_url else "memory"}


@app.post("/chat", response_model=AgentReply)
async def chat(req: ChatRequest, request: Request):
    graph = request.app.state.graph
    config = _thread_config(req.thread_id)
    snapshot = await graph.aget_state(config)
    if _pending_interrupt(snapshot) is not None:
        raise HTTPException(status_code=409, detail="This thread is waiting for an answer. Use /resume.")

    result = await graph.ainvoke({"user_input": req.message, "user_id": req.user_id}, config)
    return _to_reply(result)


@app.post("/resume", response_model=AgentReply)
async def resume(req: ResumeRequest, request: Request):
    graph = request.app.state.graph
    config = _thread_config(req.thread_id)
    snapshot = await graph.aget_state(config)
    if snapshot.created_at is None:
        raise HTTPException(status_code=404, detail="Thread not found.")
    if _pending_interrupt(snapshot) is None:
        raise HTTPException(status_code=409, detail="This thread has no pending answer.")

    result = await graph.ainvoke(Command(resume=req.answer), config)
    return _to_reply(result)


@app.get("/week/{thread_id}", response_model=WeekReply)
async def week(request: Request, thread_id: Annotated[NonBlank, PathParam()]):
    snapshot = await request.app.state.graph.aget_state(_thread_config(thread_id))
    if snapshot.created_at is None:
        raise HTTPException(status_code=404, detail="Thread not found.")

    pending = _pending_interrupt(snapshot)
    if snapshot.values.get("approved"):
        return WeekReply.model_validate(snapshot.values)
    if pending is not None:
        return WeekReply(plan=pending.value["plan"])
    return WeekReply.model_validate(snapshot.values)
