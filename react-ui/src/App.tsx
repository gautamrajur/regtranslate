import { useState } from 'react'
import { processDocument, extractTasks, exportToJira, exportToGitHub } from './api'
import type { ExtractionTask } from './types'
import './App.css'

const REGULATION_OPTIONS = ['HIPAA', 'GDPR', 'ADA/WCAG', 'FDA 21 CFR Part 11', 'Custom']

function App() {
  const [docId, setDocId] = useState<string | null>(null)
  const [regulationName, setRegulationName] = useState('Custom')
  const [tasks, setTasks] = useState<ExtractionTask[]>([])
  const [loading, setLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [dedupe, setDedupe] = useState(true)
  const [productContext, setProductContext] = useState('')
  const [selectedTasks, setSelectedTasks] = useState<Set<string>>(new Set())

  // Export state
  const [jiraUrl, setJiraUrl] = useState('https://your-domain.atlassian.net')
  const [jiraEmail, setJiraEmail] = useState('')
  const [jiraToken, setJiraToken] = useState('')
  const [jiraProject, setJiraProject] = useState('')
  const [jiraBoard, setJiraBoard] = useState('')
  const [jiraSprint, setJiraSprint] = useState('')
  const [jiraAutoSprint, setJiraAutoSprint] = useState(true)
  const [ghRepo, setGhRepo] = useState('')
  const [ghToken, setGhToken] = useState('')

  const clearMessages = () => {
    setError(null)
    setSuccess(null)
  }

  const handleUpload = async () => {
    if (!selectedFile) return
    clearMessages()
    setLoading('Processing PDF…')
    try {
      const res = await processDocument(selectedFile, regulationName)
      setDocId(res.doc_id)
      setRegulationName(res.regulation_name)
      setTasks([])
      setSuccess(`Processed ${res.chunk_count} chunks. Ready for extraction.`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Processing failed')
    } finally {
      setLoading(null)
    }
  }

  const handleExtract = async () => {
    if (!docId) return
    clearMessages()
    setLoading('Extracting tasks (RAG + LLM)…')
    try {
      const res = await extractTasks({
        doc_id: docId,
        regulation_name: regulationName,
        dedupe,
        return_coverage: true,
        product_context: productContext.trim() || null,
        rag_query: productContext.trim() || null,
      })
      setTasks(res.tasks)
      setSelectedTasks(new Set(res.tasks.map((t) => t.task_id)))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Extraction failed')
    } finally {
      setLoading(null)
    }
  }

  const toggleTask = (taskId: string) => {
    setSelectedTasks((prev) => {
      const next = new Set(prev)
      if (next.has(taskId)) next.delete(taskId)
      else next.add(taskId)
      return next
    })
  }

  const updateTask = (taskId: string, updates: Partial<ExtractionTask>) => {
    setTasks((prev) =>
      prev.map((t) => (t.task_id === taskId ? { ...t, ...updates } : t))
    )
  }

  const handleExportJira = async () => {
    const toExport = tasks.filter((t) => selectedTasks.has(t.task_id))
    if (!toExport.length || !jiraProject) {
      setError('Select at least one task and provide project key.')
      return
    }
    clearMessages()
    setLoading('Exporting to Jira…')
    try {
      const res = await exportToJira({
        tasks: toExport,
        project_key: jiraProject,
        url: jiraUrl || null,
        email: jiraEmail || null,
        api_token: jiraToken || null,
        sprint_id: jiraSprint ? parseInt(jiraSprint, 10) : null,
        board_id: jiraBoard ? parseInt(jiraBoard, 10) : null,
        auto_create_sprint: jiraAutoSprint && !jiraSprint && !!jiraBoard,
      })
      setSuccess(`Created: ${res.keys.join(', ')}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Jira export failed')
    } finally {
      setLoading(null)
    }
  }

  const handleExportGitHub = async () => {
    const toExport = tasks.filter((t) => selectedTasks.has(t.task_id))
    if (!toExport.length || !ghRepo || !ghToken) {
      setError('Select at least one task and provide repo + token.')
      return
    }
    clearMessages()
    setLoading('Exporting to GitHub…')
    try {
      const res = await exportToGitHub({
        tasks: toExport,
        repo: ghRepo,
        token: ghToken,
      })
      setSuccess(`Created ${res.urls.length} issue(s).`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'GitHub export failed')
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-title">
          <span>📜</span> RegTranslate
        </div>
        <nav className="sidebar-nav">
          <a href="#" className="active">PDF → Jira / GitHub</a>
        </nav>
      </aside>

      <main className="main">
        <h1>RegTranslate</h1>
        <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>
          Regulatory PDF → Developer tasks → Jira / GitHub
        </p>

        {error && (
          <div className="alert alert-error">{error}</div>
        )}
        {success && (
          <div className="alert alert-success">{success}</div>
        )}
        {loading && (
          <div className="alert alert-info">{loading}</div>
        )}

        {/* 1. Document upload */}
        <section className="section">
          <h2>1. Document upload</h2>
          <div className="input-group">
            <label>Regulation type</label>
            <select
              value={regulationName}
              onChange={(e) => setRegulationName(e.target.value)}
            >
              {REGULATION_OPTIONS.map((r) => (
                <option key={r} value={r === 'Custom' ? 'Custom' : r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <div
            className={`upload-zone ${selectedFile ? 'has-file' : ''}`}
            onClick={() => document.getElementById('file-input')?.click()}
          >
            <input
              id="file-input"
              type="file"
              accept=".pdf"
              onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
            />
            {selectedFile ? (
              <p>{selectedFile.name}</p>
            ) : (
              <p>Drop a PDF here or click to upload</p>
            )}
          </div>
          <button
            className="btn btn-primary"
            onClick={handleUpload}
            disabled={!selectedFile || !!loading}
          >
            Process document
          </button>
        </section>

        {docId && (
          <div className="alert alert-info" style={{ marginBottom: '1.5rem' }}>
            Document ID: <code style={{ fontFamily: 'var(--font-mono)' }}>{docId}</code> · Regulation: {regulationName}
          </div>
        )}

        {/* 2. Task extraction */}
        <section className="section">
          <h2>2. Task extraction</h2>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <input
              type="checkbox"
              checked={dedupe}
              onChange={(e) => setDedupe(e.target.checked)}
            />
            Deduplicate across regulations
          </label>
          <div className="input-group">
            <label>Product context (optional — for product-focused extraction)</label>
            <textarea
              placeholder="e.g. I'm building a patient portal API that handles ePHI, prescriptions, and lab results..."
              value={productContext}
              onChange={(e) => setProductContext(e.target.value)}
              rows={3}
            />
          </div>
          <button
            className="btn btn-primary"
            onClick={handleExtract}
            disabled={!docId || !!loading}
          >
            Extract tasks
          </button>
        </section>

        {/* 3. Task review */}
        {tasks.length > 0 && (
          <section className="section">
            <h2>3. Task review</h2>
            <p>Select tasks to export. Edit before exporting if needed.</p>
            {tasks.map((task) => (
              <TaskCard
                key={task.task_id}
                task={task}
                selected={selectedTasks.has(task.task_id)}
                onToggle={() => toggleTask(task.task_id)}
                onUpdate={(updates) => updateTask(task.task_id, updates)}
              />
            ))}
          </section>
        )}

        {/* 4. Export */}
        {tasks.length > 0 && (
          <section className="section">
            <h2>4. Export</h2>
            <div className="export-grid">
              <div className="export-panel">
                <h3>Jira</h3>
                <div className="input-group">
                  <label>URL</label>
                  <input
                    type="text"
                    value={jiraUrl}
                    onChange={(e) => setJiraUrl(e.target.value)}
                    placeholder="https://your-domain.atlassian.net"
                  />
                </div>
                <div className="input-group">
                  <label>Email</label>
                  <input
                    type="text"
                    value={jiraEmail}
                    onChange={(e) => setJiraEmail(e.target.value)}
                  />
                </div>
                <div className="input-group">
                  <label>API token</label>
                  <input
                    type="password"
                    value={jiraToken}
                    onChange={(e) => setJiraToken(e.target.value)}
                  />
                </div>
                <div className="input-group">
                  <label>Project key</label>
                  <input
                    type="text"
                    value={jiraProject}
                    onChange={(e) => setJiraProject(e.target.value)}
                    placeholder="PROJ"
                  />
                </div>
                <div className="input-group">
                  <label>Board ID (optional)</label>
                  <input
                    type="text"
                    value={jiraBoard}
                    onChange={(e) => setJiraBoard(e.target.value)}
                    placeholder="e.g. 42"
                  />
                </div>
                <div className="input-group">
                  <label>Sprint ID (optional)</label>
                  <input
                    type="text"
                    value={jiraSprint}
                    onChange={(e) => setJiraSprint(e.target.value)}
                    placeholder="e.g. 123"
                  />
                </div>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                  <input
                    type="checkbox"
                    checked={jiraAutoSprint}
                    onChange={(e) => setJiraAutoSprint(e.target.checked)}
                  />
                  Auto-create sprint if none exists
                </label>
                <button
                  className="btn btn-primary"
                  onClick={handleExportJira}
                  disabled={!!loading}
                >
                  Export selected to Jira
                </button>
              </div>
              <div className="export-panel">
                <h3>GitHub</h3>
                <div className="input-group">
                  <label>Repo (owner/name)</label>
                  <input
                    type="text"
                    value={ghRepo}
                    onChange={(e) => setGhRepo(e.target.value)}
                    placeholder="owner/repo"
                  />
                </div>
                <div className="input-group">
                  <label>Token</label>
                  <input
                    type="password"
                    value={ghToken}
                    onChange={(e) => setGhToken(e.target.value)}
                  />
                </div>
                <button
                  className="btn btn-primary"
                  onClick={handleExportGitHub}
                  disabled={!!loading}
                >
                  Export selected to GitHub
                </button>
              </div>
            </div>
          </section>
        )}

        {!tasks.length && docId && (
          <p style={{ color: 'var(--text-muted)' }}>
            Process a document, then run <strong>Extract tasks</strong>.
          </p>
        )}
      </main>
    </div>
  )
}

function TaskCard({
  task,
  selected,
  onToggle,
  onUpdate,
}: {
  task: ExtractionTask
  selected: boolean
  onToggle: () => void
  onUpdate: (updates: Partial<ExtractionTask>) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editForm, setEditForm] = useState({
    title: task.title,
    description: task.description,
    priority: task.priority,
    responsible_role: task.responsible_role,
    acceptance_criteria: task.acceptance_criteria.join('\n'),
    subtasks: task.subtasks.map((s) => `${s.title} | ${s.description}`).join('\n'),
  })

  const handleSave = () => {
    const ac = editForm.acceptance_criteria
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean)
    const sub = editForm.subtasks.split('\n').map((line) => {
      const trimmed = line.trim()
      if (!trimmed) return { title: '', description: '' }
      if (trimmed.includes(' | ')) {
        const [t, d] = trimmed.split(' | ', 2)
        return { title: t.trim(), description: d.trim() }
      }
      return { title: trimmed, description: '' }
    }).filter((s) => s.title)
    onUpdate({
      title: editForm.title,
      description: editForm.description,
      priority: editForm.priority as ExtractionTask['priority'],
      responsible_role: editForm.responsible_role,
      acceptance_criteria: ac,
      subtasks: sub,
    })
    setEditing(false)
  }

  return (
    <div className="task-card">
      <div className="task-card-header">
        <input
          type="checkbox"
          className="task-card-checkbox"
          checked={selected}
          onChange={onToggle}
        />
        <span
          className="task-card-title"
          onClick={() => setExpanded(!expanded)}
          style={{ cursor: 'pointer', flex: 1 }}
        >
          {task.title}
        </span>
        <span className={`task-card-priority ${task.priority}`}>{task.priority}</span>
      </div>
      {expanded && (
        <div className="task-card-expanded">
          <div className="task-card-desc">{task.description}</div>
          <div className="task-card-meta">Source: {task.source_citation}</div>
          {task.acceptance_criteria.length > 0 && (
            <>
              <strong>Acceptance criteria:</strong>
              <ul>
                {task.acceptance_criteria.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </>
          )}
          {task.subtasks.length > 0 && (
            <>
              <strong>Subtasks:</strong>
              <ul>
                {task.subtasks.map((s, i) => (
                  <li key={i}>
                    <strong>{s.title}</strong>
                    {s.description && ` — ${s.description}`}
                  </li>
                ))}
              </ul>
            </>
          )}
          <div className="task-card-meta">Role: {task.responsible_role} · task_id: {task.task_id}</div>

          {!editing ? (
            <button
              className="btn btn-secondary"
              style={{ marginTop: '0.75rem' }}
              onClick={() => setEditing(true)}
            >
              ✏️ Edit task
            </button>
          ) : (
            <div className="edit-form">
              <div className="input-group">
                <label>Title</label>
                <input
                  value={editForm.title}
                  onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))}
                />
              </div>
              <div className="input-group">
                <label>Description</label>
                <textarea
                  value={editForm.description}
                  onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
                  rows={4}
                />
              </div>
              <div className="input-group">
                <label>Priority</label>
                <select
                  value={editForm.priority}
                  onChange={(e) => setEditForm((f) => ({ ...f, priority: e.target.value as ExtractionTask['priority'] }))}
                >
                  <option value="High">High</option>
                  <option value="Medium">Medium</option>
                  <option value="Low">Low</option>
                </select>
              </div>
              <div className="input-group">
                <label>Responsible role</label>
                <input
                  value={editForm.responsible_role}
                  onChange={(e) => setEditForm((f) => ({ ...f, responsible_role: e.target.value }))}
                />
              </div>
              <div className="input-group">
                <label>Acceptance criteria (one per line)</label>
                <textarea
                  value={editForm.acceptance_criteria}
                  onChange={(e) => setEditForm((f) => ({ ...f, acceptance_criteria: e.target.value }))}
                  rows={3}
                />
              </div>
              <div className="input-group">
                <label>Subtasks (one per line: Title | Description)</label>
                <textarea
                  value={editForm.subtasks}
                  onChange={(e) => setEditForm((f) => ({ ...f, subtasks: e.target.value }))}
                  rows={3}
                />
              </div>
              <button className="btn btn-primary" onClick={handleSave}>
                Save changes
              </button>
              <button
                className="btn btn-secondary"
                style={{ marginLeft: '0.5rem' }}
                onClick={() => setEditing(false)}
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App
