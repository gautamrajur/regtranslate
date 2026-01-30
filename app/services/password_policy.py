"""§ 2.5.2 Password Requirements (REQUIRED). Policy validation and constants."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

# § 2.5.2 constants
MIN_LENGTH = 12
LOCKOUT_AFTER_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30  # regulation often specifies 30 min
PASSWORD_HISTORY_COUNT = 24
MAX_PASSWORD_AGE_DAYS = 90

# Complexity: at least one of each
COMPLEXITY_UPPER = re.compile(r"[A-Z]")
COMPLEXITY_LOWER = re.compile(r"[a-z]")
COMPLEXITY_DIGIT = re.compile(r"\d")
COMPLEXITY_SPECIAL = re.compile(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~]")


@dataclass
class PasswordPolicyConfig:
    """§ 2.5.2 policy configuration."""

    min_length: int = MIN_LENGTH
    lockout_after_failed_attempts: int = LOCKOUT_AFTER_FAILED_ATTEMPTS
    lockout_duration_minutes: int = LOCKOUT_DURATION_MINUTES
    password_history_count: int = PASSWORD_HISTORY_COUNT
    max_password_age_days: int = MAX_PASSWORD_AGE_DAYS


def validate_password(password: str, config: PasswordPolicyConfig | None = None) -> tuple[bool, list[str]]:
    """
    Validate password against § 2.5.2. Returns (ok, list of violation messages).
    """
    config = config or PasswordPolicyConfig()
    errors: list[str] = []

    if len(password) < config.min_length:
        errors.append(f"Password must be at least {config.min_length} characters")

    if not COMPLEXITY_UPPER.search(password):
        errors.append("Password must contain at least one uppercase letter")
    if not COMPLEXITY_LOWER.search(password):
        errors.append("Password must contain at least one lowercase letter")
    if not COMPLEXITY_DIGIT.search(password):
        errors.append("Password must contain at least one number")
    if not COMPLEXITY_SPECIAL.search(password):
        errors.append("Password must contain at least one special character")

    return (len(errors) == 0, errors)


def is_locked_out(
    failed_attempts: int,
    last_failure_at: datetime | None,
    config: PasswordPolicyConfig | None = None,
) -> bool:
    """
    Returns True if account should be locked out (≥5 failed attempts within lockout window).
    Caller must pass current failed_attempts and last_failure_at from auth store.
    """
    config = config or PasswordPolicyConfig()
    if failed_attempts < config.lockout_after_failed_attempts:
        return False
    if last_failure_at is None:
        return True
    window_end = last_failure_at + timedelta(minutes=config.lockout_duration_minutes)
    return datetime.now(timezone.utc) < window_end


def is_password_in_history(
    password_hash: str,
    history_hashes: list[str],
    config: PasswordPolicyConfig | None = None,
) -> bool:
    """
    Returns True if password (hash) is in the last N hashes (reuse not allowed).
    Caller provides current password hash and list of last N password hashes for the user.
    """
    config = config or PasswordPolicyConfig()
    recent = history_hashes[: config.password_history_count]
    return password_hash in recent


def is_password_expired(
    password_changed_at: datetime | None,
    config: PasswordPolicyConfig | None = None,
) -> bool:
    """
    Returns True if password is past max age (90 days). Caller provides last change time.
    """
    config = config or PasswordPolicyConfig()
    if password_changed_at is None:
        return True
    expiry = password_changed_at + timedelta(days=config.max_password_age_days)
    return datetime.now(timezone.utc) > expiry


def policy_summary(config: PasswordPolicyConfig | None = None) -> dict:
    """Return policy summary for documentation / API."""
    config = config or PasswordPolicyConfig()
    return {
        "source": "§ 2.5.2 - Password Requirements (REQUIRED)",
        "min_length": config.min_length,
        "complexity": ["uppercase", "lowercase", "number", "special character"],
        "lockout_after_failed_attempts": config.lockout_after_failed_attempts,
        "lockout_duration_minutes": config.lockout_duration_minutes,
        "password_history_count": config.password_history_count,
        "max_password_age_days": config.max_password_age_days,
    }
