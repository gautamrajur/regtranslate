# RegTranslate React UI

React frontend for RegTranslate — regulatory PDF → developer tasks → Jira / GitHub.

## Features

- **Hero page** — Landing with problem statement, FAQ, Get started
- **Dashboard** — Upload PDF, extract tasks (RAG + LLM), review, export to Jira/GitHub
- **Batch PDF processing** — Multiple files at once
- **Task management** — Search, filter, bulk select, manual task creation with templates
- **Export** — Jira, GitHub, CSV; saved presets
- **Dark mode** — Theme toggle
- **Audit trail** — View tamper-evident logs (§ 2.2.1)
- **Keyboard shortcuts** — Ctrl+Shift+E: Extract, Ctrl+Shift+S: Export Jira

## Prerequisites

- Node.js 18+
- RegTranslate API running at `http://localhost:8000`

## Setup

```bash
npm install
```

## Development

```bash
# Start the RegTranslate API first (from project root)
uvicorn app.main:app --reload

# In another terminal, start the React dev server
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api` requests to the FastAPI backend.

**Prepopulated credentials:** Add `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` (and optionally `GITHUB_REPO`, `GITHUB_TOKEN`) to your `.env` in the project root. The export form will prepopulate these values. Restart the API after changing `.env`.

## Build

```bash
npm run build
```

Output in `dist/`. Serve with any static host; configure the API base URL via environment or build-time config if not using the same origin.
