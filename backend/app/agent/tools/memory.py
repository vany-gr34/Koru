"""Long-term memory (Postgres tables in db/init.sql) — stub for now.

TODO (phase 2): read/write user_preferences and task_history with psycopg.
"""

DEFAULT_PREFS = {"day_start": 8, "day_end": 21, "max_hours_per_day": 8}


def get_preferences(user_id: str) -> dict:
    return dict(DEFAULT_PREFS)
