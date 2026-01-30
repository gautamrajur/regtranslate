# § 2.5.2 – Password Requirements (REQUIRED)

**Requirement:** Covered entities MUST implement password policies meeting minimum security standards.

## Acceptance Criteria → Implementation

| Criterion | Implementation |
|-----------|----------------|
| **Password length at least 12 characters** | `app/services/password_policy.py`: `MIN_LENGTH = 12`; `validate_password()` enforces. |
| **Complexity: uppercase, lowercase, number, special character** | `validate_password()` checks one of each via regex. |
| **Account lockout after 5 failed attempts** | `LOCKOUT_AFTER_FAILED_ATTEMPTS = 5`; `is_locked_out(failed_attempts, last_failure_at)` returns True when ≥5 failures; lockout duration 30 min (`LOCKOUT_DURATION_MINUTES`). Auth layer must track failed attempts and call `is_locked_out()`. |
| **Password history: prevent reuse of last 24** | `PASSWORD_HISTORY_COUNT = 24`; `is_password_in_history(password_hash, history_hashes)` returns True if hash is in last 24. Auth layer must store password hashes history and call before accepting new password. |
| **Maximum password age 90 days** | `MAX_PASSWORD_AGE_DAYS = 90`; `is_password_expired(password_changed_at)` returns True if older than 90 days. Auth layer must store `password_changed_at` and enforce change when expired. |

## Usage

```python
from app.services.password_policy import (
    validate_password,
    is_locked_out,
    is_password_in_history,
    is_password_expired,
    PasswordPolicyConfig,
    policy_summary,
)

# Validate new password
ok, errors = validate_password("MyP@ssw0rd123")
if not ok:
    print(errors)

# Check lockout (auth layer provides failed_attempts and last_failure_at)
if is_locked_out(failed_attempts=5, last_failure_at=last_failure_ts):
    return "Account locked. Try again in 30 minutes."

# Check history (auth layer provides new hash and list of last 24 hashes)
if is_password_in_history(new_password_hash, user.password_history_hashes):
    return "Cannot reuse one of the last 24 passwords."

# Check expiry (auth layer provides password_changed_at)
if is_password_expired(user.password_changed_at):
    return "Password expired. Change password."
```

## API

- `GET /compliance/password-policy` – returns policy summary (§ 2.5.2)
- `POST /compliance/validate-password` – body `{"password": "..."}` → `{"valid": bool, "errors": [...]}`
