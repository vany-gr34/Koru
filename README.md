# Weekly Planner Agent

Turn a messy list of tasks into a realistic week, synced with your calendar.
A LangGraph agent with a router and subgraphs. The LLM understands your text, OR-Tools builds the schedule,
Postgres stores state and memory, and a mobile app (Expo) is the UI.

Full design: [docs/architecture.md](docs/architecture.md)

## Repo layout

```
weekly-planner/
├── docker-compose.yml        # Postgres + backend
├── db/init.sql               # memory tables (users, user_preferences, task_history)
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI: /chat, /resume, /week, /health
│   │   ├── config.py         # settings from .env
│   │   └── agent/
│   │       ├── graph.py      # parent graph: router -> subgraph
│   │       ├── router.py     # classifies intent (plan_week / replan / review)
│   │       ├── state.py      # shared state + LLM output schemas
│   │       ├── subgraphs/
│   │       │   ├── plan.py   # load -> parse -> schedule -> negotiate/confirm -> commit  ✅
│   │       │   ├── replan.py # placeholder
│   │       │   └── review.py # placeholder
│   │       └── tools/
│   │           ├── scheduler.py  # OR-Tools CP-SAT  ✅
│   │           ├── llm.py        # model factory
│   │           ├── calendar.py   # Google Calendar (stub)
│   │           └── memory.py     # Postgres prefs (stub)
│   └── tests/                # run offline with a fake LLM
├── mobile/                   # Expo app (to scaffold, see mobile/README.md)
└── docs/architecture.md
```

## Quick start

```bash
cp .env.example .env          # add your LLM API key
make install                  # backend deps
make test                     # works with no key and no DB
make db                       # Postgres in Docker
make dev                      # API on http://localhost:8000 (docs at /docs)
```

Or run everything in Docker with `make up`.

### Try it

```bash
curl -X POST localhost:8000/chat -H 'content-type: application/json' \
  -d '{"thread_id":"me-week48","message":"Exam Friday, 2 reports due Thursday, gym 3x, Wednesday afternoon is gone"}'
# -> {"status":"needs_input","kind":"confirm","plan":[...]}

curl -X POST localhost:8000/resume -H 'content-type: application/json' \
  -d '{"thread_id":"me-week48","answer":"ok"}'
```

`thread_id` identifies a conversation. Because state is checkpointed in Postgres,
the agent can wait for an answer for as long as needed, even across restarts.

## Status

| Part | State |
|---|---|
| Plan-the-week subgraph | working |
| CP-SAT scheduler | working (todo: daily cap, spread work, preferred times) |
| Router | working |
| Postgres checkpointer | working |
| Memory tables | schema ready, not wired yet |
| Replan / review subgraphs | placeholders |
| Google Calendar | stub |
| Mobile app | not started |
