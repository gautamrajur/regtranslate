"""Section citation guidance so extracted tasks cite correct sections and include full acceptance criteria."""

# Map: topic -> correct section (avoid citing review section for logging, etc.)
SECTION_GUIDANCE = """
CRITICAL: Cite the EXACT section that imposes each requirement. Do not mix sections.

- Audit LOGGING (what to log, retention, tamper-evident): § 2.2.1 — NOT § 2.2.2
- Audit REVIEW (regular review, alerting, weekly/monthly analysis): § 2.2.2 — NOT § 2.2.1
- Unique user identification: § 2.1.1
- Emergency access procedure: § 2.1.2
- Encryption (at rest / in transit): § 2.1.4, § 2.4.1
- Password policy: § 2.5.2
- MFA: § 2.5.1 (REQUIRED; high penalty)
- Backup & recovery: § 3.2.2
- Security incident response: § 3.2.1
- API security: § 4.1.1, § 4.1.2
"""

# Acceptance criteria that MUST be included when extracting these topics (from regulation text)
ACCEPTANCE_CRITERIA_BY_TOPIC = {
    "audit_logging_2_2_1": [
        "Log all access attempts (successful AND failed)",
        "Log all modifications to ePHI",
        "Log user authentication events",
        "Logs include timestamp, user ID, action, resource accessed, source IP",
        "Logs retained at least 6 years",
        "Logs are tamper-evident",
    ],
    "audit_review_2_2_2": [
        "Automated alerts for suspicious patterns",
        "Weekly manual review of high-risk access events",
        "Monthly comprehensive audit log analysis",
        "Findings and remediation actions documented",
        "Remediation tracking",
    ],
    "password_policy_2_5_2": [
        "No password hints or security questions",
        "30-minute lockout duration after 5 failed attempts",
    ],
    "unique_user_id_2_1_1": [
        "User IDs at least 8 characters",
        "User IDs must not contain easily guessable patterns (SSN, birthdate)",
        "System maintains audit log of all user ID assignments",
        "User IDs cannot be shared or transferred between individuals",
    ],
}

# High-priority sections that must not be missed
CRITICAL_SECTIONS = [
    "§ 2.5.1",   # MFA — REQUIRED, $75K–$300K penalty
    "§ 2.1.4", "§ 2.4.1",  # Encryption at rest/transit
    "§ 3.2.2",  # Backup & recovery — $250K–$1M penalty
    "§ 4.1.1", "§ 4.1.2",  # API security
    "§ 2.1.2",  # Emergency access procedure
    "§ 3.2.1",  # Security incident response
]
