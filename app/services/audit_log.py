"""Tamper-evident audit log for ePHI access/modification (§ 2.2.1). Review procedures = § 2.2.2."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.audit_models import AuditLogEntry

_AUDIT_LOG_DIR = Path(os.getenv("AUDIT_LOG_DIR", "./audit_logs"))
_AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_RETENTION_YEARS = int(os.getenv("AUDIT_RETENTION_YEARS", "6"))
LOG_FILE = _AUDIT_LOG_DIR / "audit.jsonl"
CHAIN_FILE = _AUDIT_LOG_DIR / "chain_state.json"


def _hash_entry(prev_hash: str, payload: dict[str, Any]) -> str:
    data = json.dumps({**payload, "prev_hash": prev_hash}, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()


def _serialize(entry: AuditLogEntry) -> dict[str, Any]:
    return {
        "timestamp": entry.timestamp,
        "user_id": entry.user_id,
        "action": entry.action,
        "resource_accessed": entry.resource_accessed,
        "source_ip": entry.source_ip,
        "details": entry.details,
        "prev_hash": entry.prev_hash,
        "entry_hash": entry.entry_hash,
    }


def append_entry(
    user_id: str,
    action: str,
    resource_accessed: str,
    source_ip: str,
    details: str = "",
) -> AuditLogEntry:
    """Append a tamper-evident log entry. Uses hash chain."""
    timestamp = datetime.now(timezone.utc).isoformat()
    prev_hash = ""
    if CHAIN_FILE.exists():
        try:
            raw = CHAIN_FILE.read_text()
            state = json.loads(raw)
            prev_hash = state.get("last_hash", "")
        except Exception:
            prev_hash = ""

    payload = {
        "timestamp": timestamp,
        "user_id": user_id,
        "action": action,
        "resource_accessed": resource_accessed,
        "source_ip": source_ip,
        "details": details,
    }
    entry_hash = _hash_entry(prev_hash, payload)
    entry = AuditLogEntry(
        timestamp=timestamp,
        user_id=user_id,
        action=action,
        resource_accessed=resource_accessed,
        source_ip=source_ip,
        details=details,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )
    line = json.dumps(_serialize(entry)) + "\n"
    with open(LOG_FILE, "a") as f:
        f.write(line)
    CHAIN_FILE.write_text(json.dumps({"last_hash": entry_hash}))
    return entry


def list_entries(limit: int = 500, since_ts: str | None = None) -> list[AuditLogEntry]:
    """List recent entries. Optional since_ts (ISO) filter."""
    if not LOG_FILE.exists():
        return []
    entries = []
    with open(LOG_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                e = AuditLogEntry(**d)
                if since_ts and e.timestamp < since_ts:
                    continue
                entries.append(e)
            except Exception:
                continue
    entries.reverse()
    return entries[:limit]


def verify_chain() -> tuple[bool, list[str]]:
    """Verify tamper-evident chain. Returns (ok, list of error messages)."""
    errors = []
    if not LOG_FILE.exists():
        return True, []
    prev = ""
    with open(LOG_FILE) as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                entry_hash = d.get("entry_hash", "")
                prev_hash = d.get("prev_hash", "")
                if prev_hash != prev:
                    errors.append(f"Line {i+1}: prev_hash mismatch")
                payload = {k: v for k, v in d.items() if k != "entry_hash"}
                expected = _hash_entry(prev_hash, payload)
                if expected != entry_hash:
                    errors.append(f"Line {i+1}: entry_hash mismatch (tampering?)")
                prev = entry_hash
            except Exception as e:
                errors.append(f"Line {i+1}: {e}")
    return len(errors) == 0, errors


def enforce_retention() -> int:
    """Remove entries older than AUDIT_RETENTION_YEARS. Returns count removed."""
    from datetime import timedelta

    if not LOG_FILE.exists():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=365 * AUDIT_RETENTION_YEARS)
    cutoff_ts = cutoff.isoformat()
    kept = []
    removed = 0
    with open(LOG_FILE) as f:
        for line in f:
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                if d.get("timestamp", "") < cutoff_ts:
                    removed += 1
                    continue
                kept.append(line)
            except Exception:
                kept.append(line)
    if removed > 0:
        LOG_FILE.write_text("".join(kept))
    return removed
