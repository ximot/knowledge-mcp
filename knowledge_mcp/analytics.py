"""
In-memory usage analytics.

Tracks search calls (across both the MCP tool interface and the dashboard's
REST search) so the dashboard can chart "searches per day". This is
intentionally in-process and non-persistent — it resets on restart, same as
the server's uptime counter in http_server.py — since adding a durable
event store is out of scope for a lightweight self-hosted tool.
"""

from collections import defaultdict
from datetime import datetime, timedelta

_search_counts: dict[str, int] = defaultdict(int)


def record_search() -> None:
    """Record one search call against today's date (UTC)."""
    today = datetime.utcnow().date().isoformat()
    _search_counts[today] += 1


def get_search_counts(days: int = 14) -> dict[str, int]:
    """Return a date -> count map for the last `days` days, zero-filled."""
    today = datetime.utcnow().date()
    return {
        (today - timedelta(days=offset)).isoformat(): _search_counts.get(
            (today - timedelta(days=offset)).isoformat(), 0
        )
        for offset in range(days - 1, -1, -1)
    }
