"""Streamlit UI for RegTranslate: upload, extract, review, export."""

from __future__ import annotations

import logging
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

# Run from project root (regtranslate/) so 'app' is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Log everything to a .txt file
LOG_FILE = ROOT / "streamlit_app_log.txt"
_logger = logging.getLogger("streamlit_app")
if not _logger.handlers:
    _logger.setLevel(logging.DEBUG)
    _logger.addHandler(logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"))
    _logger.handlers[-1].setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))


def _log(msg: str, level: str = "info", **kwargs: str) -> None:
    extra = " | ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
    full = f"{msg} {extra}".strip()
    getattr(_logger, level)(full)

from app.config import JIRA_EMAIL, JIRA_URL
from app.models import ExtractionSubtask, ExtractionTask
from app.services import (
    audit_alerts,
    audit_log,
    deduplication,
    embeddings,
    github_export,
    jira_export,
    pdf_processor,
    task_generator,
    vector_store,
)

REGULATION_OPTIONS = ["HIPAA", "GDPR", "ADA/WCAG", "FDA 21 CFR Part 11", "Custom"]


@st.cache_resource
def _warmup_embeddings() -> None:
    embeddings.warmup()


def _run_process(uploaded_file, regulation_name: str) -> tuple[str | None, int, str | None, list]:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(uploaded_file.read())
        tmp.flush()
        path = Path(tmp.name)
    try:
        chunks = pdf_processor.extract_and_chunk(path)
    except Exception as e:
        return None, 0, str(e), []
    finally:
        path.unlink(missing_ok=True)
    if not chunks:
        return None, 0, "No text extracted from PDF.", []
    chunk_dicts = [
        {"text": c.text, "page": c.page, "section": c.section, "chunk_index": c.chunk_index}
        for c in chunks
    ]
    texts = [c.text for c in chunks]
    emb = embeddings.embed_texts(texts)
    doc_id = str(uuid.uuid4())
    meta = {"regulation_name": regulation_name, "source": uploaded_file.name or "upload.pdf"}
    vector_store.add_document(doc_id, chunk_dicts, emb, meta)
    q_emb = embeddings.embed_query("encryption authentication access control")
    results = vector_store.query(doc_id, q_emb, n_results=5)
    return doc_id, len(chunks), None, results


def _run_extract(
    doc_id: str, regulation_name: str, dedupe: bool, return_coverage: bool = True
) -> tuple[list[ExtractionTask] | None, str | None, dict | None]:
    """Returns (tasks, error, coverage). coverage is for Quick Test (pages, sections, Section 4)."""
    try:
        raw, coverage = task_generator.extract_tasks(doc_id, regulation_name)
        tasks = deduplication.deduplicate(raw) if dedupe and raw else raw
        return tasks, None, coverage if return_coverage else None
    except Exception as e:
        return None, str(e), None


def main() -> None:
    st.set_page_config(page_title="RegTranslate", page_icon="📜", layout="wide")
    _log("App started / main() entered", level="info")
    _warmup_embeddings()

    if "doc_id" not in st.session_state:
        st.session_state.doc_id = None
    if "regulation_name" not in st.session_state:
        st.session_state.regulation_name = "Custom"
    if "tasks" not in st.session_state:
        st.session_state.tasks = []
    if "extract_coverage" not in st.session_state:
        st.session_state.extract_coverage = None

    page = st.sidebar.radio("Section", ["RegTranslate (PDF → Jira/GitHub)", "Audit (§ 2.2.1 / § 2.2.2)"], key="page")
    _log("Page selected", page=page)
    if page == "Audit (§ 2.2.1 / § 2.2.2)":
        _log("Rendering Audit page")
        _render_audit_page()
        return

    st.title("📜 RegTranslate")
    st.caption("Regulatory PDF → Developer tasks → Jira / GitHub")

    # ---- 1. Document upload ----
    st.header("1. Document upload")
    regulation = st.selectbox("Regulation type", REGULATION_OPTIONS, index=4)
    regulation_name = regulation if regulation != "Custom" else "Custom"
    file = st.file_uploader("Upload PDF", type=["pdf"], key="upload")
    if st.button("Process document", type="primary", disabled=file is None):
        _log("Button clicked: Process document", filename=file.name if file else "none", regulation_name=regulation_name)
        if not file:
            _log("Process document: no file", level="warning")
            st.error("Please upload a PDF.")
            return
        with st.spinner("Processing PDF…"):
            _log("Process document: calling _run_process")
            doc_id, n, err, sample = _run_process(file, regulation_name)
        if err:
            _log("Process document: error", error=err, level="error")
            st.error(err)
            return
        assert doc_id is not None
        _log("Process document: success", doc_id=doc_id, chunk_count=str(n))
        st.session_state.doc_id = doc_id
        st.session_state.regulation_name = regulation_name
        st.session_state.tasks = []
        st.success(f"Processed **{n}** chunks. Ready for extraction.")
        st.rerun()

    if st.session_state.doc_id:
        st.info(f"**Document ID:** `{st.session_state.doc_id}` · Regulation: **{st.session_state.regulation_name}**")

    # ---- 2. Task extraction ----
    st.header("2. Task extraction")
    dedupe = st.checkbox("Deduplicate across regulations", value=True, key="dedupe")
    show_coverage = st.checkbox("Show RAG coverage (Quick Test: Parts I–IV, Section 4)", value=True, key="show_coverage")
    if st.button("Extract tasks", disabled=not st.session_state.doc_id):
        _log("Button clicked: Extract tasks", doc_id=st.session_state.doc_id or "", dedupe=str(dedupe))
        with st.spinner("Extracting tasks (RAG + LLM)…"):
            _log("Extract tasks: calling _run_extract")
            tasks, err, coverage = _run_extract(
                st.session_state.doc_id,
                st.session_state.regulation_name,
                dedupe,
                return_coverage=show_coverage,
            )
        if err:
            _log("Extract tasks: error", error=err, level="error")
            st.error(err)
            return
        _log("Extract tasks: success", task_count=str(len(tasks or [])))
        st.session_state.tasks = tasks or []
        st.session_state.extract_coverage = coverage
        st.success(f"Extracted **{len(st.session_state.tasks)}** tasks.")
        st.rerun()

    # Normalize tasks: ensure ExtractionTask (handles dicts from session serialization or old schema)
    raw_tasks = st.session_state.tasks
    tasks: list[ExtractionTask] = []
    for item in raw_tasks:
        if isinstance(item, ExtractionTask):
            # Ensure subtasks attr exists (schema may have been updated)
            if not hasattr(item, "subtasks"):
                item = ExtractionTask(
                    task_id=item.task_id,
                    title=item.title,
                    description=item.description,
                    priority=item.priority,
                    penalty_risk=item.penalty_risk,
                    source_citation=item.source_citation,
                    source_text=item.source_text,
                    responsible_role=item.responsible_role,
                    acceptance_criteria=item.acceptance_criteria,
                    also_satisfies=item.also_satisfies,
                    confidence=item.confidence,
                    subtasks=[],
                )
            tasks.append(item)
        elif isinstance(item, dict):
            subtasks_data = item.get("subtasks", [])
            subtasks = [
                ExtractionSubtask(title=s.get("title", ""), description=s.get("description", ""))
                if isinstance(s, dict)
                else ExtractionSubtask(title=getattr(s, "title", ""), description=getattr(s, "description", ""))
                for s in subtasks_data
            ]
            tasks.append(
                ExtractionTask(
                    task_id=item.get("task_id", ""),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    priority=item.get("priority", "Medium"),
                    penalty_risk=item.get("penalty_risk", ""),
                    source_citation=item.get("source_citation", ""),
                    source_text=item.get("source_text", ""),
                    responsible_role=item.get("responsible_role", "Backend Engineer"),
                    acceptance_criteria=item.get("acceptance_criteria", []),
                    also_satisfies=item.get("also_satisfies", []),
                    confidence=item.get("confidence"),
                    subtasks=subtasks,
                )
            )
    coverage = st.session_state.get("extract_coverage")
    if coverage:
        with st.expander("Quick Test: RAG coverage (Parts I–IV, Section 4)", expanded=True):
            st.write("**Pages in RAG chunks:**", coverage.get("pages_summary", "—"))
            st.write("**Section 4 (API) in chunks:**", "Yes" if coverage.get("section_4_in_chunks") else "No")
            st.write("**Sections detected:**", ", ".join(str(s) for s in (coverage.get("sections") or [])[:20]))
            secs = coverage.get("sections") or []
            if len(secs) > 20:
                st.caption(f"… and {len(secs) - 20} more.")
    if not tasks:
        st.markdown("Process a document, then run **Extract tasks**.")
        st.divider()
        st.markdown("**Pipeline:** PDF → pypdf chunk → embeddings → ChromaDB → RAG + Groq → tasks.")
        return

    # ---- 3. Task review ----
    st.header("3. Task review")
    roles = sorted({t.responsible_role for t in tasks})
    priorities = ["High", "Medium", "Low"]
    role_filter = st.multiselect("Filter by role", roles, default=roles, key="role_filter")
    prio_filter = st.multiselect("Filter by priority", priorities, default=priorities, key="prio_filter")
    filtered = [t for t in tasks if t.responsible_role in role_filter and t.priority in prio_filter]

    st.markdown("Select tasks to export.")
    selected: list[ExtractionTask] = []
    for t in filtered:
        include = st.checkbox("Include", value=True, key=f"export_{t.task_id}")
        if include:
            selected.append(t)
        also = f" · *Also satisfies: {', '.join(t.also_satisfies)}*" if t.also_satisfies else ""
        with st.expander(f"[{t.priority}] **{t.title}**{also}", expanded=False):
            st.markdown(t.description)
            st.markdown(f"**Source:** {t.source_citation}")
            if t.acceptance_criteria:
                st.markdown("**Acceptance criteria:**")
                for c in t.acceptance_criteria:
                    st.markdown(f"- {c}")
            # Defensive: handle tasks from before subtasks existed, or dicts from session serialization
            subtasks = getattr(t, "subtasks", None) or (t.get("subtasks", []) if isinstance(t, dict) else [])
            if subtasks:
                st.markdown("**Subtasks:**")
                for i, st_sub in enumerate(subtasks, 1):
                    title = st_sub.title if hasattr(st_sub, "title") else (st_sub.get("title", "") if isinstance(st_sub, dict) else "")
                    desc = st_sub.description if hasattr(st_sub, "description") else (st_sub.get("description", "") if isinstance(st_sub, dict) else "")
                    if title:
                        st.markdown(f"- **{i}.** {title}")
                        if desc:
                            st.caption(desc)
            st.caption(f"Role: {t.responsible_role} · task_id: {t.task_id}")

    # ---- 4. Export ----
    st.header("4. Export")
    col_j, col_g = st.columns(2)
    with col_j:
        st.subheader("Jira")
        j_url = st.text_input("Jira URL", value=JIRA_URL or "https://your-domain.atlassian.net", key="j_url")
        j_email = st.text_input("Jira email", value=JIRA_EMAIL or "", key="j_email")
        j_token = st.text_input("Jira API token", type="password", key="j_token")
        j_project = st.text_input("Project key", placeholder="PROJ (e.g. CONV for Convergence)", key="j_project")
        j_board = st.text_input("Board ID (optional)", placeholder="e.g. 42 — from URL .../boards/42", key="j_board")
        j_auto_sprint = st.checkbox(
            "Auto-create sprint if none exists",
            value=True,
            key="j_auto_sprint",
            help="Uses active/future sprint, or creates one so tasks appear on the board",
        )
        j_sprint = st.text_input(
            "Sprint ID (optional)",
            placeholder="e.g. 123 — or leave blank + Board ID for auto-create",
            key="j_sprint",
            help="Adds tasks to this sprint. If blank and auto-create is on, uses/creates sprint.",
        )
        if j_board and j_board.strip().isdigit() and j_url and j_email and j_token:
            if st.button("Fetch sprints"):
                try:
                    sprints = jira_export.fetch_active_sprints(
                        int(j_board.strip()),
                        url=j_url.strip() or None,
                        email=j_email.strip() or None,
                        api_token=j_token.strip() or None,
                    )
                    if sprints:
                        st.write("**Sprints:** (use ID in Sprint ID field)")
                        for s in sprints[:10]:
                            st.caption(f"ID: {s['id']} — {s['name']} ({s['state']})")
                        if len(sprints) > 10:
                            st.caption(f"... and {len(sprints) - 10} more")
                    else:
                        st.info("No sprints found.")
                except Exception as e:
                    st.error(str(e))
        with st.expander("Assignee mapping (role → accountId)", expanded=False):
            st.caption("Auto-assign tasks by responsible role. Get accountIds from Jira → People.")
            j_assignee_backend = st.text_input("Backend Engineer accountId", key="j_assignee_backend", placeholder="557058:xxx-xxx")
            j_assignee_frontend = st.text_input("Frontend Engineer accountId", key="j_assignee_frontend", placeholder="557058:yyy-yyy")
            j_assignee_devops = st.text_input("DevOps accountId", key="j_assignee_devops", placeholder="557058:zzz-zzz")
            j_assignee_security = st.text_input("Security accountId", key="j_assignee_security", placeholder="557058:aaa-aaa")
        if st.button("Export selected to Jira"):
            _log("Button clicked: Export selected to Jira", selected_count=str(len(selected)), project=j_project)
            if not selected:
                _log("Export Jira: no tasks selected", level="warning")
                st.warning("Select at least one task.")
            elif not j_project:
                _log("Export Jira: project key missing", level="warning")
                st.warning("Project key required.")
            else:
                try:
                    sprint_id = int(j_sprint.strip()) if j_sprint and j_sprint.strip().isdigit() else None
                    board_id = int(j_board.strip()) if j_board and j_board.strip().isdigit() else None
                    assignees = {}
                    if j_assignee_backend and j_assignee_backend.strip():
                        assignees["Backend Engineer"] = j_assignee_backend.strip()
                    if j_assignee_frontend and j_assignee_frontend.strip():
                        assignees["Frontend Engineer"] = j_assignee_frontend.strip()
                    if j_assignee_devops and j_assignee_devops.strip():
                        assignees["DevOps"] = j_assignee_devops.strip()
                        assignees["DevOps Engineer"] = j_assignee_devops.strip()
                    if j_assignee_security and j_assignee_security.strip():
                        assignees["Security"] = j_assignee_security.strip()
                        assignees["Security Engineer"] = j_assignee_security.strip()
                    _log("Export Jira: calling jira_export.export_to_jira")
                    keys = jira_export.export_to_jira(
                        selected,
                        j_project,
                        url=j_url.strip() or None,
                        email=j_email.strip() or None,
                        api_token=j_token.strip() or None,
                        sprint_id=sprint_id,
                        board_id=board_id,
                        auto_create_sprint=j_auto_sprint and sprint_id is None and board_id is not None,
                        assignee_overrides=assignees if assignees else None,
                    )
                    _log("Export Jira: success", keys=",".join(keys))
                    st.success(f"Created: {', '.join(keys)}")
                except Exception as e:
                    _log("Export Jira: error", error=str(e), level="error")
                    st.error(str(e))
    with col_g:
        st.subheader("GitHub")
        gh_repo = st.text_input("Repo (owner/name)", placeholder="owner/repo", key="gh_repo")
        gh_token = st.text_input("GitHub token", type="password", key="gh_token")
        if st.button("Export selected to GitHub"):
            _log("Button clicked: Export selected to GitHub", selected_count=str(len(selected)), repo=gh_repo or "")
            if not selected:
                _log("Export GitHub: no tasks selected", level="warning")
                st.warning("Select at least one task.")
            elif not gh_token or not gh_repo:
                _log("Export GitHub: token or repo missing", level="warning")
                st.warning("GitHub token and repo required.")
            else:
                try:
                    _log("Export GitHub: calling github_export.export_to_github")
                    urls = github_export.export_to_github(selected, gh_repo.strip(), gh_token)
                    _log("Export GitHub: success", url_count=str(len(urls)))
                    st.success(f"Created {len(urls)} issue(s).")
                    for u in urls[:5]:
                        st.markdown(f"- {u}")
                    if len(urls) > 5:
                        st.caption(f"… and {len(urls) - 5} more")
                except Exception as e:
                    _log("Export GitHub: error", error=str(e), level="error")
                    st.error(str(e))

    st.divider()
    st.caption("RegTranslate · PDF → Embeddings → ChromaDB → RAG + Groq → Jira / GitHub")


def _render_audit_page() -> None:
    """§ 2.2.1 Audit logging | § 2.2.2 Review & alerting: logs, verify, alerts, weekly/monthly reviews."""
    st.title("Audit (§ 2.2.1 / § 2.2.2)")
    st.caption("ePHI audit logs · tamper-evident · 6-year retention · alerts · reviews")

    tab1, tab2, tab3, tab4 = st.tabs(["Logs", "Verify chain", "Alerts & run", "Reviews"])

    with tab1:
        st.header("Audit log entries")
        limit = st.number_input("Limit", min_value=10, max_value=1000, value=100, key="audit_limit")
        entries = audit_log.list_entries(limit=limit)
        st.metric("Entries", len(entries))
        for e in entries[:50]:
            st.text(f"{e.timestamp} | {e.user_id} | {e.action} | {e.resource_accessed} | {e.source_ip}")
        if len(entries) > 50:
            st.caption(f"… and {len(entries) - 50} more")

    with tab2:
        st.header("Tamper-evident chain verification")
        if st.button("Verify chain"):
            _log("Audit: Button clicked: Verify chain")
            ok, errors = audit_log.verify_chain()
            _log("Audit: Verify chain result", ok=str(ok), error_count=str(len(errors)))
            if ok:
                st.success("Chain valid. No tampering detected.")
            else:
                st.error("Chain invalid.")
                for err in errors:
                    st.code(err)
        if st.button("Enforce retention (remove >6 years)"):
            _log("Audit: Button clicked: Enforce retention")
            n = audit_log.enforce_retention()
            _log("Audit: Enforce retention", removed=str(n))
            st.info(f"Removed {n} old entries.")

    with tab3:
        st.header("Automated alerts (suspicious patterns)")
        if st.button("Run automated alerts"):
            _log("Audit: Button clicked: Run automated alerts")
            alerts = audit_alerts.run_automated_alerts()
            _log("Audit: Run automated alerts", generated=str(len(alerts)))
            st.success(f"Generated {len(alerts)} alert(s).")
            for a in alerts:
                st.json(a)
        st.subheader("Recent alerts")
        for a in audit_alerts.list_alerts(limit=20):
            st.text(f"{a.get('generated_at', '')} | {a.get('type', '')} | {a.get('message', '')}")
        st.subheader("High-risk events (weekly review)")
        for e in audit_alerts.get_high_risk_entries(limit=20):
            st.text(f"{e.timestamp} | {e.user_id} | {e.action} | {e.resource_accessed}")

    with tab4:
        st.header("Document findings & remediation (weekly/monthly)")
        review_type = st.selectbox("Review type", ["weekly_high_risk", "monthly_comprehensive"], key="review_type")
        performed_by = st.text_input("Performed by", key="performed_by")
        findings = st.text_area("Findings (one per line)", key="findings")
        remediation = st.text_area("Remediation actions (one per line)", key="remediation")
        if st.button("Save review record"):
            _log("Audit: Button clicked: Save review record", review_type=review_type, performed_by=performed_by or "unknown")
            from app.services.audit_models import AuditReviewRecord
            record = AuditReviewRecord(
                id=str(uuid.uuid4()),
                review_type=review_type,
                performed_at=datetime.now(timezone.utc).isoformat(),
                performed_by=performed_by or "unknown",
                findings=[f.strip() for f in findings.splitlines() if f.strip()],
                remediation_actions=[r.strip() for r in remediation.splitlines() if r.strip()],
                high_risk_event_ids=[],
            )
            audit_alerts.save_review_record(record)
            _log("Audit: Save review record: success", record_id=record.id)
            st.success("Review record saved.")
        st.subheader("Recent reviews")
        for r in audit_alerts.list_review_records(limit=10):
            with st.expander(f"{r.review_type} · {r.performed_at} · {r.performed_by}"):
                st.write("Findings:", r.findings)
                st.write("Remediation:", r.remediation_actions)


if __name__ == "__main__":
    main()
