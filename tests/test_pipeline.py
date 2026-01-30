"""Tests for PDF → embeddings → ChromaDB pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Project root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services import pdf_processor


class TestPDFChunking:
    """Unit tests for chunking logic (no PDF file)."""

    def test_detect_section_article(self) -> None:
        text = "Article 32 Security of processing. 1. Taking into account..."
        section = pdf_processor._detect_section(text)
        assert "Article" in section and "32" in section

    def test_detect_section_citation(self) -> None:
        text = "§ 164.312(a)(2)(i) Implement a mechanism to encrypt..."
        section = pdf_processor._detect_section(text)
        assert "164" in section or "§" in section

    def test_chunk_text_respects_size(self) -> None:
        full = "x " * 2000  # ~4000 chars
        chunks = pdf_processor._chunk_text(
            full,
            page_breaks=[(0, len(full))],
            chunk_size=400,
            overlap=80,
        )
        assert len(chunks) >= 1
        for c in chunks:
            assert len(c.text) <= 450  # some margin for word-boundary trim

    def test_chunk_text_page_assignment(self) -> None:
        p1 = "page one " * 200
        p2 = "page two " * 200
        full = p1 + "\n\n" + p2
        brks = [(0, len(p1) + 2), (len(p1) + 2, len(full))]
        chunks = pdf_processor._chunk_text(full, brks, chunk_size=500, overlap=100)
        assert len(chunks) >= 1
        pages = {c.page for c in chunks}
        assert 1 in pages or 2 in pages

    def test_extract_and_chunk_requires_pdf(self) -> None:
        with pytest.raises(ValueError, match="PDF"):
            pdf_processor.extract_and_chunk(Path(__file__))

    def test_extract_and_chunk_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            pdf_processor.extract_and_chunk(Path("/nonexistent/file.pdf"))
