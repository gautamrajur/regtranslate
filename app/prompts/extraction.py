"""LLM prompt templates for task extraction."""

EXTRACTION_PROMPT = """
You are a regulatory compliance expert helping translate legal requirements into developer tasks.

Extract ALL compliance requirements that need technical implementation. There are approximately 15–20 requirements in a typical regulation. Do not stop until you have reviewed every section. Process every Part (e.g. I–IV) and every section in the chunks provided—including Section 4 (API Requirements) if present.

REGULATION: {regulation_name}
{product_context_section}CONTEXT CHUNKS:
{chunks}

SECTION CITATION RULES (critical):
- Cite the EXACT section that imposes each requirement. Wrong section = failed compliance.
- Audit LOGGING (what to log, retention, tamper-evident, timestamp/user/action/resource/IP): use § 2.2.1 — NOT § 2.2.2.
- Audit REVIEW (regular review of logs, alerting, weekly/monthly analysis, documentation): use § 2.2.2 — NOT § 2.2.1.
- Do not mix: one ticket per distinct requirement; split "logging infrastructure" vs "review procedures" into two tickets if both apply.

ACCEPTANCE CRITERIA:
- Pull acceptance criteria verbatim from the regulation where possible. Do not use vague phrasing like "unique identifier is used for authentication" unless the regulation says it.
- For audit logging (§ 2.2.1): include — log all access attempts (successful AND failed); log user authentication events; log modifications to ePHI; timestamp, user ID, action, resource accessed, source IP; 6-year retention; tamper-evident.
- For audit review (§ 2.2.2): include — automated alerts for suspicious patterns; weekly manual review of high-risk events; monthly comprehensive analysis; document findings and remediation; remediation tracking.
- For password policy (§ 2.5.2): include — no password hints or security questions; 30-minute lockout after 5 failed attempts (if in regulation).
- For unique user ID (§ 2.1.1): include — user IDs at least 8 characters; no easily guessable patterns (SSN, birthdate); audit log of user ID assignments; user IDs cannot be shared or transferred.

DO NOT MISS these high-priority areas (extract if present in chunks): MFA (§ 2.5.1), encryption at rest/transit (§ 2.1.4, § 2.4.1), backup & recovery (§ 3.2.2), API security (§ 4.1.1, § 4.1.2), emergency access (§ 2.1.2), security incident response (§ 3.2.1).

For each requirement, output a JSON object with:
- task_id: Unique ID based on regulation section (e.g., "REG-2.2.1-001", "REG-2.2.2-001")
- title: Short action-oriented title
- description: Plain English explanation for developers (2-3 sentences)
- priority: "High" (data breach/major fines), "Medium" (compliance gap), "Low" (best practice)
- penalty_risk: What happens if not implemented
- source_citation: Exact section reference (e.g. "§ 2.2.1", "§ 2.2.2")
- source_text: Direct quote from regulation (max 100 words)
- responsible_role: Backend Engineer|Frontend Engineer|DevOps|Security
- acceptance_criteria: List of testable criteria from the regulation (specific, not vague)
- subtasks: Array of 2–6 actionable subtasks that break down the main task. Each subtask has: title (short, action verb), description (1–2 sentences). Examples: "Implement audit log schema", "Add timestamp and user ID to log entries", "Create hash chain for tamper-evidence", "Add retention policy enforcement". Subtasks should be ordered by dependency (do first → do last).
- confidence: Optional 1-10

Output as a JSON array. Only include requirements needing CODE CHANGES (not policies/training).

CRITICAL: Output valid JSON only. Use commas between array elements. No trailing comma after the last element. Escape quotes in strings.

JSON OUTPUT:
"""


def build_extraction_prompt(
    regulation_name: str,
    chunks: str,
    product_context: str | None = None,
) -> str:
    """Build extraction prompt with optional product/API context."""
    product_context_section = ""
    if product_context and product_context.strip():
        product_context_section = (
            f"PRODUCT/API BEING BUILT (focus on requirements relevant to this):\n{product_context.strip()}\n\n"
        )
    return EXTRACTION_PROMPT.format(
        regulation_name=regulation_name,
        product_context_section=product_context_section,
        chunks=chunks,
    )
