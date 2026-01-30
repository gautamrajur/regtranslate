"""RAG pipeline + LLM task extraction from regulatory chunks."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.models.schemas import ExtractionSubtask, ExtractionTask

logger = logging.getLogger(__name__)
from app.prompts.extraction import build_extraction_prompt
from app.services import embeddings, llm_service, vector_store

# Broad query so Parts I–IV and Section 4 (API) are retrieved; 128K context allows many chunks
RAG_QUERY = (
    "compliance requirements technical implementation "
    "security encryption access control audit logging authentication "
    "API requirements Section 4"
)
N_CHUNKS = 50
# Do not truncate chunks when building context (Groq Llama has 128K); cap per-chunk only to avoid runaway
MAX_CHUNK_CHARS_IN_CONTEXT = 6000


def _format_chunks(results: list[dict[str, Any]]) -> str:
    out = []
    for i, r in enumerate(results, 1):
        meta = r.get("metadata") or {}
        page = meta.get("page", "?")
        section = meta.get("section", "")
        full_text = r.get("text") or ""
        text = full_text[:MAX_CHUNK_CHARS_IN_CONTEXT]
        if len(full_text) > MAX_CHUNK_CHARS_IN_CONTEXT:
            text += "..."
        head = f"[{i}] (page {page})"
        if section:
            head += f" {section}"
        out.append(f"{head}\n{text}")
    return "\n\n---\n\n".join(out)


def _repair_json(raw: str) -> str:
    """Fix common LLM JSON errors: trailing commas, missing commas between objects."""
    # Remove trailing commas before } or ]
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    # Fix missing comma between } and { (adjacent objects in array)
    raw = re.sub(r"}\s*\n\s*{", "},\n{", raw)
    return raw


def _extract_json_array(raw: str) -> list[dict[str, Any]]:
    raw = raw.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if m:
        raw = m.group(1).strip()
    # Extract array bounds
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start >= 0 and end > start:
        raw = raw[start:end]
    else:
        raise ValueError("No JSON array found in LLM output")

    last_err: json.JSONDecodeError | None = None
    for text in [raw, _repair_json(raw)]:
        try:
            data = json.loads(text)
            break
        except json.JSONDecodeError as e:
            last_err = e
            continue
    else:
        # Both failed; try json_repair if available
        try:
            import json_repair
            data = json_repair.loads(raw)
            logger.info("Used json_repair to fix LLM JSON")
        except ImportError:
            raise ValueError(f"Failed to parse LLM output as JSON: {last_err}") from last_err
        except Exception:
            raise ValueError(f"Failed to parse LLM output as JSON: {last_err}") from last_err

    if not isinstance(data, list):
        data = [data]
    return data


def _parse_subtasks(raw: list[Any] | None) -> list[ExtractionSubtask]:
    """Parse subtasks from LLM output."""
    if not raw or not isinstance(raw, list):
        return []
    out: list[ExtractionSubtask] = []
    for item in raw:
        if isinstance(item, dict):
            title = str(item.get("title", "")).strip()
            if title:
                out.append(
                    ExtractionSubtask(
                        title=title,
                        description=str(item.get("description", "")).strip(),
                    )
                )
        elif isinstance(item, str) and item.strip():
            out.append(ExtractionSubtask(title=item.strip(), description=""))
    return out


def _task_from_obj(obj: dict[str, Any]) -> ExtractionTask:
    priority = (obj.get("priority") or "Medium").strip()
    if priority not in ("High", "Medium", "Low"):
        priority = "Medium"
    subtasks = _parse_subtasks(obj.get("subtasks"))
    return ExtractionTask(
        task_id=str(obj.get("task_id", "")).strip() or f"TASK-{hash(str(obj)) % 10**6}",
        title=str(obj.get("title", "")).strip() or "Untitled",
        description=str(obj.get("description", "")).strip() or "",
        priority=priority,
        penalty_risk=str(obj.get("penalty_risk", "")).strip(),
        source_citation=str(obj.get("source_citation", "")).strip(),
        source_text=str(obj.get("source_text", "")).strip(),
        responsible_role=str(obj.get("responsible_role", "")).strip() or "Backend Engineer",
        acceptance_criteria=[str(x).strip() for x in (obj.get("acceptance_criteria") or []) if str(x).strip()],
        also_satisfies=[str(x).strip() for x in (obj.get("also_satisfies") or []) if str(x).strip()],
        confidence=obj.get("confidence") if isinstance(obj.get("confidence"), int) else None,
        subtasks=subtasks,
    )


def _coverage_from_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Build coverage info from RAG results for Quick Test (Parts I–IV, Section 4)."""
    pages: set[int] = set()
    sections: list[str] = []
    seen_sections: set[str] = set()
    for r in results:
        meta = r.get("metadata") or {}
        p = meta.get("page")
        if p is not None:
            try:
                pages.add(int(p))
            except (TypeError, ValueError):
                pass
        sec = (meta.get("section") or "").strip()
        if sec and sec not in seen_sections:
            seen_sections.add(sec)
            sections.append(sec)
    return {
        "chunk_count": len(results),
        "pages": sorted(pages),
        "pages_summary": f"pages {min(pages)}–{max(pages)}" if pages else "none",
        "sections": sections,
        "section_4_in_chunks": any("4" in s or "Section 4" in s for s in sections),
    }


def get_rag_coverage(
    doc_id: str,
    rag_query: str = RAG_QUERY,
    n_chunks: int = N_CHUNKS,
) -> dict[str, Any]:
    """
    Quick Test: run RAG query only (no LLM) and return which pages/sections
    are in the top chunks. Use to verify Parts I–IV and Section 4 are covered.
    """
    q_emb = embeddings.embed_query(rag_query)
    results = vector_store.query(doc_id, q_emb, n_results=n_chunks)
    if not results:
        return {"chunk_count": 0, "pages": [], "pages_summary": "none", "sections": [], "section_4_in_chunks": False}
    return _coverage_from_results(results)


def extract_tasks(
    doc_id: str,
    regulation_name: str,
    rag_query: str = RAG_QUERY,
    n_chunks: int = N_CHUNKS,
    product_context: str | None = None,
) -> tuple[list[ExtractionTask], dict[str, Any]]:
    """
    1. Query vector store for relevant chunks
    2. Build context from chunks
    3. Call LLM with extraction prompt
    4. Parse JSON array and validate
    5. Return (list of ExtractionTask, coverage info for Quick Test)
    """
    q_emb = embeddings.embed_query(rag_query)
    results = vector_store.query(doc_id, q_emb, n_results=n_chunks)
    if not results:
        return [], {"chunk_count": 0, "pages": [], "pages_summary": "none", "sections": [], "section_4_in_chunks": False}

    coverage = _coverage_from_results(results)
    logger.info(
        "RAG coverage for extraction: %s chunks, %s; sections: %s; Section 4 in chunks: %s",
        coverage["chunk_count"],
        coverage["pages_summary"],
        coverage["sections"][:15],
        coverage["section_4_in_chunks"],
    )

    chunks_text = _format_chunks(results)
    prompt = build_extraction_prompt(regulation_name, chunks_text, product_context=product_context)
    messages = [("system", "You output only valid JSON. No markdown or commentary."), ("human", prompt)]
    raw = llm_service.invoke_with_fallback(messages)

    try:
        arr = _extract_json_array(raw)
    except (ValueError, json.JSONDecodeError) as e:
        raise ValueError(f"Failed to parse LLM output as JSON: {e}") from e

    tasks: list[ExtractionTask] = []
    for i, obj in enumerate(arr):
        if not isinstance(obj, dict):
            continue
        try:
            tasks.append(_task_from_obj(obj))
        except Exception:
            continue
    return tasks, coverage
