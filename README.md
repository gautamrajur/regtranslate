# RegTranslate

> Upload a HIPAA/GDPR/FDA/ADA regulation PDF. Get developer-ready Jira/GitHub tasks in seconds.

---

## Demo

![Demo](assets/demo.mp4)

---

## What it does

1. **Upload** a regulatory PDF (HIPAA, GDPR, ADA/WCAG, FDA 21 CFR Part 11, or Custom)
2. **Extract** — RAG + Groq/Llama LLM generates structured tasks with acceptance criteria, subtasks, and confidence scores
3. **Deduplicate** — semantic similarity merges overlapping requirements across regulations
4. **Export** — one click to Jira, GitHub Issues, or CSV

**Full pipeline is regulation-aware.** No other tool combines extraction → deduplication → export in a single flow.

---

## Stack

| Layer | Tech |
|---|---|
| API | FastAPI (Python 3.11+) |
| LLM | Groq `llama-3.3-70b-versatile` · optional Gemini fallback |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (local) |
| Vector DB | ChromaDB (local, persistent) |
| Frontend | React + Vite + TypeScript |
| Legacy UI | Streamlit |

---

## Quick Start

```bash
# 1. Install
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Add GROQ_API_KEY (required). Optional: GOOGLE_API_KEY, CHROMA_PERSIST_DIR.

# 3. Run API + React UI
uvicorn app.main:app --reload              # Terminal 1
cd react-ui && npm install && npm run dev  # Terminal 2
# → http://localhost:5173
```

Or via curl:
```bash
curl -X POST "http://127.0.0.1:8000/process?regulation_name=GDPR" -F "file=@regulation.pdf"
```

---

## React UI Features

- Upload single or multiple PDFs
- Filter tasks by priority / confidence
- Bulk select · manual task templates
- Export to Jira, GitHub, or CSV with saved presets
- Tamper-evident audit log viewer (§ 2.2.2)
- Dark mode · keyboard shortcuts (`Ctrl+Shift+E` extract, `Ctrl+Shift+S` export)

---

## Pipeline

1. **PDF** → pypdf extracts text, chunked (~1000 tokens / 4000 chars, 200 overlap)
2. **Embeddings** → `sentence-transformers/all-MiniLM-L6-v2` (local, first run ~90MB download)
3. **ChromaDB** → one collection per document; stores chunks + metadata (page, section, regulation)
4. **RAG + LLM** → Groq `llama-3.3-70b-versatile` via official SDK; optional Gemini fallback
5. **Deduplication** → semantic similarity clusters merged into tasks with `also_satisfies` cross-refs
6. **Export** → Jira (basic auth), GitHub Issues (PyGithub), CSV with saved presets
7. **Audit (§ 2.2.2)** → tamper-evident hash-chain log, 6-year retention, automated alerts for suspicious patterns, weekly high-risk + monthly comprehensive review

---

## Project Structure

```
regtranslate/
├── app/
│   ├── main.py                  # FastAPI routes
│   ├── services/                # PDF, embeddings, vector store, LLM, export
│   └── prompts/extraction.py    # Regulation-aware prompts
├── react-ui/                    # Hero page + dashboard
├── frontend/streamlit_app.py    # Legacy UI
└── tests/
```

---

## License

MIT
