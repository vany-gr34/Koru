-- Long-term memory tables.
-- (LangGraph checkpoint tables are created automatically by the backend on startup.)

CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    name        TEXT,
    timezone    TEXT NOT NULL DEFAULT 'Africa/Casablanca',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id     TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    day_start   SMALLINT NOT NULL DEFAULT 8,    -- hour, 0-23
    day_end     SMALLINT NOT NULL DEFAULT 21,
    max_hours_per_day REAL NOT NULL DEFAULT 8,
    extra       JSONB NOT NULL DEFAULT '{}'      -- free-form prefs ("deep work in the morning", ...)
);

-- Estimated vs actual durations, used by the review subgraph to improve estimates.
CREATE TABLE IF NOT EXISTS task_history (
    id              BIGSERIAL PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    week_start      DATE NOT NULL,
    title           TEXT NOT NULL,
    category        TEXT,
    estimated_hours REAL,
    actual_hours    REAL,
    completed       BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_task_history_user_week ON task_history (user_id, week_start);

INSERT INTO users (id, name) VALUES ('demo', 'Demo user') ON CONFLICT DO NOTHING;
INSERT INTO user_preferences (user_id) VALUES ('demo') ON CONFLICT DO NOTHING;
