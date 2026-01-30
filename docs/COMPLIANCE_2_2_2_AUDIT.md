# § 2.2.2 – Audit Log Review (REQUIRED)

**Requirement:** Covered entities MUST implement procedures for regular review of audit logs to detect security incidents, including modifications to ePHI and user authentication events. Logs must be retained at least 6 years and include timestamp, user ID, action, resource accessed, and source IP. Automated alerting for suspicious patterns is required.

## Acceptance Criteria → Implementation

| Criterion | Implementation |
|-----------|----------------|
| **Audit logs retained at least 6 years** | `app/services/audit_log.py`: `AUDIT_RETENTION_YEARS=6` (env); `enforce_retention()` removes entries older than 6 years. Run periodically (e.g. cron) or via Streamlit **Audit → Verify chain → Enforce retention**. |
| **Logs include timestamp, user ID, action, resource accessed, source IP** | `app/services/audit_models.AuditLogEntry`: `timestamp`, `user_id`, `action`, `resource_accessed`, `source_ip`. Use `audit_log.append_entry(user_id, action, resource_accessed, source_ip, details)` for every ePHI access/modification and auth event. |
| **Automated alerting for suspicious patterns** | `app/services/audit_alerts.py`: `run_automated_alerts()` detects multiple login failures, same-IP many users, high-risk actions (delete, bulk_export, admin_access, login_failure). Run on a schedule or via Streamlit **Audit → Alerts & run → Run automated alerts**. |
| **Weekly manual review of high-risk access events** | `audit_alerts.get_high_risk_entries()` returns high-risk entries. Streamlit **Audit → Alerts & run** shows "High-risk events (weekly review)". Use **Reviews** tab with `review_type=weekly_high_risk` to document findings and remediation. |
| **Monthly comprehensive audit log analysis** | Streamlit **Audit → Reviews**: `review_type=monthly_comprehensive`, document findings and remediation. `save_review_record()` persists to `audit_logs/reviews.jsonl`. |

## Logging ePHI and Auth Events

Call `audit_log.append_entry()` for:

- **ePHI access:** `action="access"`, `resource_accessed` = e.g. `/api/patient/123`
- **ePHI modification:** `action="create"` / `"update"` / `"delete"`, `resource_accessed` = resource identifier
- **Authentication:** `action="login"` / `"login_failure"` / `"logout"`, `resource_accessed` = e.g. `"auth"`

Example:

```python
from app.services import audit_log

audit_log.append_entry(
    user_id="user@example.com",
    action="access",  # or "update", "login", "login_failure", etc.
    resource_accessed="/api/patient/123",
    source_ip=request.client.host,
    details="view record",
)
```

## API Endpoints

- `POST /audit/log` – append entry
- `GET /audit/logs` – list entries
- `GET /audit/verify` – verify tamper-evident chain
- `POST /audit/retention` – enforce 6-year retention
- `GET /audit/alerts`, `POST /audit/alerts/run` – automated alerting
- `GET /audit/reviews`, `POST /audit/reviews` – weekly/monthly review records
