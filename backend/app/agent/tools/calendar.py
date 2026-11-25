"""Google Calendar integration — stubs for now.

TODO (phase 5): replace with google-api-python-client + per-user OAuth tokens.
"""


def get_week_events(user_id: str) -> list[dict]:
    return [
        {"day": 0, "start": "09:00", "end": "12:00", "label": "Class"},
        {"day": 2, "start": "10:00", "end": "11:00", "label": "Team meeting"},
    ]


def write_plan(user_id: str, plan: list[dict]) -> int:
    """Insert plan blocks as calendar events. Returns number written."""
    return len(plan)
