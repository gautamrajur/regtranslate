# Compliance Ticket Guidance (Sample Regulation)

Use this when reviewing or creating Jira tickets from regulatory extraction so citations and acceptance criteria match the regulation.

## Section citation

| Topic | Correct section | Wrong section | Notes |
|-------|-----------------|---------------|--------|
| Audit **logging** (what to log, retention, tamper-evident, fields) | **§ 2.2.1** | § 2.2.2 | § 2.2.2 is review, not logging |
| Audit **review** (regular review, alerting, weekly/monthly, documentation) | **§ 2.2.2** | § 2.2.1 | |
| Unique user identification | § 2.1.1 | | |
| Emergency access procedure | § 2.1.2 | | |
| Encryption (at rest / in transit) | § 2.1.4, § 2.4.1 | | |
| MFA | § 2.5.1 | | REQUIRED; $75K–$300K penalty |
| Password policy | § 2.5.2 | | |
| Backup & recovery | § 3.2.2 | | $250K–$1M penalty |
| Security incident response | § 3.2.1 | | |
| API security | § 4.1.1, § 4.1.2 | | |

## Acceptance criteria by ticket

### Ticket 1a: Audit logging (§ 2.2.1) — infrastructure
- Log all **access attempts (successful AND failed)**  
- Log all **modifications to ePHI**  
- Log **user authentication events**  
- Logs include: timestamp, user ID, action, resource accessed, source IP  
- Logs retained at least **6 years**  
- Logs are **tamper-evident**  

### Ticket 1b: Audit review (§ 2.2.2) — procedures
- Automated alerts for suspicious patterns  
- Weekly manual review of high-risk access events  
- Monthly comprehensive audit log analysis  
- Findings and remediation actions documented  
- **Remediation tracking**  

### Ticket 2: Password policy (§ 2.5.2)
- **No password hints or security questions**  
- **30-minute lockout duration after 5 failed attempts**  
- (Plus any other criteria from regulation text)

### Ticket 3: Unique user identification (§ 2.1.1)
- User IDs **at least 8 characters**  
- User IDs **must not contain easily guessable patterns** (SSN, birthdate)  
- System **maintains audit log of all user ID assignments**  
- User IDs **cannot be shared or transferred** between individuals  
- Avoid vague phrasing like “unique identifier is used for authentication” unless the regulation says it.

## Big missing tickets (must not be skipped)

- **MFA (§ 2.5.1)** — REQUIRED, $75K–$300K penalty  
- **Encryption at rest/transit (§ 2.1.4, § 2.4.1)** — REQUIRED  
- **Backup & recovery (§ 3.2.2)** — REQUIRED, $250K–$1M penalty  
- **API security (§ 4.1.1, § 4.1.2)** — REQUIRED  
- **Emergency access procedure (§ 2.1.2)** — REQUIRED  
- **Security incident response (§ 3.2.1)** — REQUIRED  

## Extraction prompt

The app’s extraction prompt (`app/prompts/extraction.py`) has been updated to:
- Enforce § 2.2.1 vs § 2.2.2 (logging vs review)  
- Require the acceptance criteria above where applicable  
- Call out the critical sections so MFA, encryption, backup, API security, emergency access, and incident response are not missed  

Re-run extraction on the regulation PDF to get tickets with correct citations and fuller acceptance criteria.
