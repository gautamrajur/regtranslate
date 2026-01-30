"""FastAPI application for RegTranslate."""

import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.services import embeddings, pdf_processor, task_generator, vector_store

app = FastAPI(
    title="RegTranslate",
    description="AI-powered regulatory document to developer task converter",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProcessRequest(BaseModel):
    """Request to process a document (when passing path instead of upload)."""

    regulation_name: str = "Custom"


class ProcessResponse(BaseModel):
    """Response from document processing pipeline."""

    doc_id: str
    chunk_count: int
    regulation_name: str
    sample_query: str
    sample_results: list[dict]


class ExtractRequest(BaseModel):
    doc_id: str
    regulation_name: str
    dedupe: bool = True
    return_coverage: bool = False


class ExtractResponse(BaseModel):
    tasks: list[dict]
    coverage: dict | None = None  # Quick Test: pages, sections, section_4_in_chunks


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/process", response_model=ProcessResponse)
async def process_document(
    file: UploadFile = File(...),
    regulation_name: str = "Custom",
):
    """
    Upload a PDF, extract and chunk text, embed, and store in ChromaDB.
    Returns doc_id, chunk count, and sample query results to verify the pipeline.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "File must be a PDF")

    doc_id = str(uuid.uuid4())
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        try:
            content = await file.read()
            tmp.write(content)
            tmp.flush()
            path = Path(tmp.name)
        except Exception as e:
            raise HTTPException(500, f"Failed to save upload: {e}")

    try:
        chunks = pdf_processor.extract_and_chunk(path)
    except Exception as e:
        raise HTTPException(422, f"PDF processing failed: {e}")
    finally:
        path.unlink(missing_ok=True)

    if not chunks:
        raise HTTPException(422, "No text extracted from PDF")

    chunk_dicts = [
        {"text": c.text, "page": c.page, "section": c.section, "chunk_index": c.chunk_index}
        for c in chunks
    ]
    texts = [c.text for c in chunks]
    emb = embeddings.embed_texts(texts)

    meta = {"regulation_name": regulation_name, "source": file.filename or "upload.pdf"}
    vector_store.add_document(doc_id, chunk_dicts, emb, meta)

    sample_query = "encryption authentication access control"
    q_emb = embeddings.embed_query(sample_query)
    sample_results = vector_store.query(doc_id, q_emb, n_results=3)

    return ProcessResponse(
        doc_id=doc_id,
        chunk_count=len(chunks),
        regulation_name=regulation_name,
        sample_query=sample_query,
        sample_results=[
            {"text": r["text"][:300] + "..." if len(r["text"]) > 300 else r["text"], "metadata": r["metadata"]}
            for r in sample_results
        ],
    )


@app.get("/process/{doc_id}/coverage")
def get_coverage(doc_id: str):
    """
    Quick Test: return RAG coverage (pages, sections, Section 4) for the doc without running LLM.
    Use to verify all 4 Parts (I–IV) and Section 4 (API Requirements) are in the retrieved chunks.
    """
    try:
        coverage = task_generator.get_rag_coverage(doc_id)
        return coverage
    except Exception as e:
        raise HTTPException(500, f"Coverage check failed: {e}")


@app.post("/extract", response_model=ExtractResponse)
def extract_tasks_endpoint(req: ExtractRequest) -> ExtractResponse:
    """
    Run RAG + LLM extraction on a processed document.
    Optionally deduplicate across regulations. Returns tasks for review and export.
    Set return_coverage=True for Quick Test: pages/sections in RAG chunks (Parts I–IV, Section 4).
    """
    from app.services import deduplication

    try:
        raw, coverage = task_generator.extract_tasks(req.doc_id, req.regulation_name)
        tasks = deduplication.deduplicate(raw) if req.dedupe and raw else raw
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, f"Extraction failed: {e}")
    return ExtractResponse(
        tasks=[t.model_dump() for t in tasks],
        coverage=coverage if req.return_coverage else None,
    )


# --- § 2.2.1 Audit logging; § 2.2.2 = review/alerting ---


class AuditLogAppendRequest(BaseModel):
    user_id: str
    action: str
    resource_accessed: str
    source_ip: str
    details: str = ""


class AuditReviewCreateRequest(BaseModel):
    review_type: str  # "weekly_high_risk" | "monthly_comprehensive"
    performed_by: str
    findings: list[str] = []
    remediation_actions: list[str] = []
    high_risk_event_ids: list[str] = []


@app.post("/audit/log")
def audit_append(req: AuditLogAppendRequest, x_forwarded_for: str | None = None):
    """Append a tamper-evident audit log entry (timestamp, user_id, action, resource, source_ip)."""
    from app.services import audit_log as audit_svc
    source_ip = (x_forwarded_for or "").split(",")[0].strip() or req.source_ip
    entry = audit_svc.append_entry(
        user_id=req.user_id,
        action=req.action,
        resource_accessed=req.resource_accessed,
        source_ip=source_ip,
        details=req.details,
    )
    return {"ok": True, "entry_hash": entry.entry_hash}


@app.get("/audit/logs")
def audit_list(limit: int = 500, since: str | None = None):
    """List audit log entries (optional since ISO timestamp)."""
    from app.services import audit_log as audit_svc
    entries = audit_svc.list_entries(limit=limit, since_ts=since)
    return {"entries": [e.model_dump() for e in entries]}


@app.get("/audit/verify")
def audit_verify():
    """Verify tamper-evident chain integrity."""
    from app.services import audit_log as audit_svc
    ok, errors = audit_svc.verify_chain()
    return {"valid": ok, "errors": errors}


@app.post("/audit/retention")
def audit_enforce_retention():
    """Enforce retention (remove entries older than 6 years)."""
    from app.services import audit_log as audit_svc
    removed = audit_svc.enforce_retention()
    return {"removed": removed}


@app.get("/audit/alerts")
def audit_alerts_list(limit: int = 100):
    """List automated alerts (suspicious patterns)."""
    from app.services import audit_alerts
    return {"alerts": audit_alerts.list_alerts(limit=limit)}


@app.post("/audit/alerts/run")
def audit_alerts_run():
    """Run automated alerting for suspicious patterns."""
    from app.services import audit_alerts
    alerts = audit_alerts.run_automated_alerts()
    return {"generated": len(alerts), "alerts": alerts}


@app.get("/audit/reviews")
def audit_reviews_list(limit: int = 50):
    """List review records (weekly/monthly, findings, remediation)."""
    from app.services import audit_alerts
    records = audit_alerts.list_review_records(limit=limit)
    return {"reviews": [r.model_dump() for r in records]}


@app.post("/audit/reviews")
def audit_review_create(req: AuditReviewCreateRequest):
    """Record a weekly high-risk or monthly comprehensive review (findings + remediation)."""
    from datetime import datetime, timezone
    from app.services import audit_alerts
    from app.services.audit_models import AuditReviewRecord
    record = AuditReviewRecord(
        id=str(__import__("uuid").uuid4()),
        review_type=req.review_type,
        performed_at=datetime.now(timezone.utc).isoformat(),
        performed_by=req.performed_by,
        findings=req.findings,
        remediation_actions=req.remediation_actions,
        high_risk_event_ids=req.high_risk_event_ids,
    )
    audit_alerts.save_review_record(record)
    return {"ok": True, "id": record.id}


# --- § 2.5.2 Password Requirements (REQUIRED) ---


class ValidatePasswordRequest(BaseModel):
    password: str


@app.get("/compliance/password-policy")
def get_password_policy():
    """§ 2.5.2 policy summary: min length 12, complexity, lockout 5, history 24, max age 90 days."""
    from app.services import password_policy
    return password_policy.policy_summary()


@app.post("/compliance/validate-password")
def validate_password_endpoint(req: ValidatePasswordRequest):
    """Validate password against § 2.5.2 (length, complexity)."""
    from app.services import password_policy
    valid, errors = password_policy.validate_password(req.password)
    return {"valid": valid, "errors": errors}
