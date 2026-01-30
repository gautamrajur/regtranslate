"""Export history for created Jira tickets and GitHub issues."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_HISTORY_DIR = Path(__file__).resolve().parents[1].parent / "export_history"
_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_FILE = _HISTORY_DIR / "exports.json"
MAX_ENTRIES = 500


def _load() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(entries: list[dict]) -> None:
    HISTORY_FILE.write_text(json.dumps(entries, indent=2))


def append_jira(project_key: str, keys: list[str], task_count: int, url: str | None = None) -> None:
    """Record a Jira export."""
    entries = _load()
    base = (url or "").rstrip("/") or "https://your-domain.atlassian.net"
    entries.insert(
        0,
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target": "jira",
            "project_key": project_key,
            "keys": keys,
            "task_count": task_count,
            "jira_url": base,
        },
    )
    _save(entries[-MAX_ENTRIES:])


def append_github(repo: str, urls: list[str], task_count: int) -> None:
    """Record a GitHub export."""
    entries = _load()
    entries.insert(
        0,
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target": "github",
            "repo": repo,
            "urls": urls,
            "task_count": task_count,
        },
    )
    _save(entries[-MAX_ENTRIES:])


def list_entries(limit: int = 100) -> list[dict]:
    """List export history, most recent first."""
    entries = _load()
    return entries[:limit]
