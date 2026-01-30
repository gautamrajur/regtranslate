"""PDF text extraction and chunking for regulatory documents."""

import re
from pathlib import Path

from pypdf import PdfReader

from app.config import CHUNK_OVERLAP_CHARS, CHUNK_SIZE_CHARS
from app.models.schemas import PDFChunk


def _detect_section(text: str) -> str:
    """Extract section header (Article, §, Section) from text for source tracking."""
    patterns = [
        r"(?:Article\s+\d+(?:\.\d+)*[^\n]*)",
        r"(?:§\s*[\d.]+\s*[^\n]*)",
        r"(?:Section\s+[\d.]+\s*[^\n]*)",
        r"(?:\d+\.\d+\.\d+\s+[^\n]{0,80})",  # e.g. 164.312(a)(2)
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(0).strip()[:120]
    return ""


def _chunk_text(
    full_text: str,
    page_breaks: list[tuple[int, int]],
    chunk_size: int = CHUNK_SIZE_CHARS,
    overlap: int = CHUNK_OVERLAP_CHARS,
) -> list[PDFChunk]:
    """Split text into overlapping chunks; assign page and section from page_breaks."""
    chunks: list[PDFChunk] = []
    start = 0
    chunk_index = 0

    def page_at(pos: int) -> int:
        for p, (pb_start, pb_end) in enumerate(page_breaks):
            if pb_start <= pos < pb_end:
                return p
        return len(page_breaks) - 1 if page_breaks else 0

    while start < len(full_text):
        end = min(start + chunk_size, len(full_text))
        segment = full_text[start:end]

        # Avoid splitting mid-word when possible
        if end < len(full_text):
            last_space = segment.rfind(" ")
            if last_space > chunk_size // 2:
                end = start + last_space + 1
                segment = full_text[start:end]

        page = page_at(start)
        section = _detect_section(segment)

        chunks.append(
            PDFChunk(
                text=segment.strip(),
                page=page + 1,  # 1-based for display
                section=section,
                chunk_index=chunk_index,
            )
        )
        chunk_index += 1
        next_start = end - overlap if end < len(full_text) else len(full_text)
        start = max(next_start, start + 1)

    return chunks


def extract_and_chunk(
    pdf_path: str | Path,
    chunk_size: int = CHUNK_SIZE_CHARS,
    overlap: int = CHUNK_OVERLAP_CHARS,
) -> list[PDFChunk]:
    """
    Extract text from a PDF and return chunks with metadata (page, section).

    Uses pypdf for extraction. Chunk size/overlap approximate 1000/200 tokens
    (~4000/800 chars). Preserves section headers and citations for source tracking.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError("File must be a PDF")

    reader = PdfReader(path)
    full_text_parts: list[str] = []
    page_breaks: list[tuple[int, int]] = []  # (start_char_index, end)

    for i, page in enumerate(reader.pages):
        start_idx = sum(len(p) for p in full_text_parts)
        raw = page.extract_text() or ""
        # Normalize whitespace but keep structure
        raw = re.sub(r"\s+", " ", raw).strip()
        if raw:
            full_text_parts.append(raw)
            full_text_parts.append("\n\n")
        end_idx = sum(len(p) for p in full_text_parts)
        page_breaks.append((start_idx, end_idx))

    full_text = "".join(full_text_parts).strip()
    if not full_text:
        raise ValueError("No text extracted from PDF. File may be scanned/image-only; use an OCR'd version.")

    return _chunk_text(full_text, page_breaks, chunk_size=chunk_size, overlap=overlap)
