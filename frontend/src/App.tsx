import { useEffect, useRef, useState } from 'react'
import { getStatusPresentation, isHealthyResponse, type ServiceStatus } from './lib/status'

type JsonRecord = Record<string, unknown>
type Section = 'overview' | 'literature' | 'records' | 'knowledge' | 'math' | 'lab'
interface HealthResponse { status: string; service: string; version: string }
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/+$/, '')
const nav: { id: Section; label: string; eyebrow: string; symbol: string }[] = [
  { id: 'overview', label: 'Command center', eyebrow: 'SYSTEM', symbol: '⌂' },
  { id: 'literature', label: 'Literature search', eyebrow: 'EVIDENCE', symbol: '⌕' },
  { id: 'records', label: 'Research records', eyebrow: 'PROVENANCE', symbol: '▤' },
  { id: 'knowledge', label: 'Knowledge graph', eyebrow: 'CONCEPTS', symbol: '⌘' },
  { id: 'math', label: 'Mathematics lab', eyebrow: 'COMPUTATION', symbol: '∑' },
  { id: 'lab', label: 'Controlled lab', eyebrow: 'EXPERIMENTS', symbol: '⌬' },
]
const tools = [
  { title: 'Symbolic mathematics', detail: 'Simplify, differentiate, integrate, solve and substitute expressions.', method: 'POST', path: '/api/v1/math/symbolic', sample: { operation: 'differentiate', expression: 'x^3 + 2*x^2 - 5*x', variable: 'x' } },
  { title: 'Descriptive statistics', detail: 'Summarise a numeric sample with validated statistical measures.', method: 'POST', path: '/api/v1/math/statistics', sample: { values: [2, 4, 4, 4, 5, 5, 7, 9] } },
  { title: 'Numerical integration', detail: 'Integrate a bounded function and inspect its error estimate.', method: 'POST', path: '/api/v1/math/numeric/integrate', sample: { expression: 'x^2', variable: 'x', lower: 0, upper: 1 } },
  { title: 'Unit conversion', detail: 'Convert compatible units from the server allowlist.', method: 'POST', path: '/api/v1/math/units/convert', sample: { value: 100, source_unit: 'cm', target_unit: 'm' } },
]
const pretty = (value: unknown) => JSON.stringify(value, null, 2)
const asObject = (value: unknown): JsonRecord => typeof value === 'object' && value !== null ? value as JsonRecord : { result: value }
function ErrorNotice({ message }: { message: string }) { return <div className="notice notice-error" role="alert">{message}</div> }
function DataView({ data }: { data: unknown }) { return <pre className="json-view">{pretty(data)}</pre> }
export default function App() {
  const [section, setSection] = useState<Section>('overview')
  const [status, setStatus] = useState<ServiceStatus>('checking')
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthError, setHealthError] = useState('')
  const [retryKey, setRetryKey] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<unknown>(null)
  const [records, setRecords] = useState<JsonRecord[]>([])
  const [recordTotal, setRecordTotal] = useState<number | null>(null)
  const [recordQuery, setRecordQuery] = useState('')
  const [literatureQuery, setLiteratureQuery] = useState('')
  const [literatureLimit, setLiteratureLimit] = useState('10')
  const [saveSources, setSaveSources] = useState(false)
  const [conceptQuery, setConceptQuery] = useState('')
  const [mathTool, setMathTool] = useState(0)
  const [mathInput, setMathInput] = useState(pretty(tools[0].sample))
  const [labInput, setLabInput] = useState(pretty({ title: 'Example bounded calculation', steps: [{ step_id: 'integral_one', operation: 'integrate', inputs: { expression: 'x^2', variable: 'x', lower: 0, upper: 1 } }] }))
  const [recordInput, setRecordInput] = useState(pretty({ record_type: 'research_task', title: 'Research question', research_question: 'What measurable question should this research investigate?', objective: 'Establish a testable baseline.' }))
  const [healthBusy, setHealthBusy] = useState(false)
  const actionEpoch = useRef(0)
  const presentation = getStatusPresentation(status)
  const active = nav.find(item => item.id === section) ?? nav[0]
  const recordCountLabel = recordTotal === null ? '—' : recordTotal.toLocaleString()
  const request = async (path: string, init?: RequestInit) => {
    const response = await fetch(apiBaseUrl + path, { ...init, headers: { Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}), ...init?.headers } })
    const contentType = response.headers.get('content-type') ?? ''
    const body = contentType.includes('application/json') ? await response.json() : await response.text()
    if (!response.ok) {
      const detail = typeof body === 'object' && body !== null && 'detail' in body ? String((body as JsonRecord).detail) : String(body || response.statusText)
      throw new Error(`HTTP ${response.status}: ${detail}`)
    }
    return body
  }
  const runAction = async (action: () => Promise<unknown>) => {
    const epoch = ++actionEpoch.current
    setBusy(true); setError(''); setResult(null)
    try {
      const value = await action()
      if (epoch === actionEpoch.current) setResult(value)
      return value
    } catch (e) {
      if (epoch === actionEpoch.current) setError(e instanceof Error ? e.message : 'Request failed.')
      return null
    } finally {
      if (epoch === actionEpoch.current) setBusy(false)
    }
  }
  const checkHealth = async () => {
    setHealthBusy(true)
    try {
      const payload = await request('/api/v1/health')
      if (!isHealthyResponse(payload)) throw new Error('API response did not match the expected health schema.')
      setHealth({ status: payload.status, service: payload.service, version: payload.version }); setStatus('connected'); setHealthError('')
    } catch (e) { setHealth(null); setStatus('unavailable'); setHealthError(e instanceof Error ? e.message : 'API connection failed.') }
    finally { setHealthBusy(false) }
  }
  useEffect(() => { void checkHealth() }, [retryKey])
  const loadRecords = async () => {
    // A navigation change invalidates the request epoch. Do not let an older
    // records response mutate the records panel after the user has moved away.
    const epoch = actionEpoch.current
    const query = new URLSearchParams({ limit: '20', offset: '0' })
    if (recordQuery.trim()) query.set('record_type', recordQuery.trim())
    const data = asObject(await request('/api/v1/records?' + query.toString()))
    if (epoch === actionEpoch.current) {
      setRecords(Array.isArray(data.items) ? data.items.map(asObject) : [])
      setRecordTotal(typeof data.total === 'number' ? data.total : null)
    }
    return data
  }
  const loadKnowledge = async () => request('/api/v1/knowledge/concepts?' + new URLSearchParams({ limit: '20', ...(conceptQuery.trim() ? { query: conceptQuery.trim() } : {}) }))
  const doLiteratureSearch = () => runAction(() => request('/api/v1/literature/search', { method: 'POST', body: JSON.stringify({ query: literatureQuery.trim(), limit: Number(literatureLimit), persist_results: saveSources }) }))
  const doMath = () => runAction(() => request(tools[mathTool].path, { method: 'POST', body: mathInput }))
  const doLab = () => runAction(() => request('/api/v1/lab/runs', { method: 'POST', body: labInput }))
  const doCreateRecord = async () => {
    const value = await runAction(() => request('/api/v1/records', { method: 'POST', body: recordInput }))
    if (value) { try { await loadRecords() } catch { /* The create response remains visible if the refresh fails. */ } }
  }
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to main content</a>
    <aside className="sidebar">
      <a className="brand" href="#overview" onClick={e => { e.preventDefault(); setSection('overview') }}>
        <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
        <span className="brand-copy"><strong>ARTIFICIAL</strong><strong>SCIENTIST</strong><small>AUTONOMOUS DISCOVERY SYSTEM</small></span>
      </a>
      <div className="sidebar-label">RESEARCH WORKSPACE</div>
      <nav className="nav-list" aria-label="Main navigation">{nav.map(item => <button key={item.id} className={section === item.id ? 'nav-item active' : 'nav-item'} onClick={() => { actionEpoch.current += 1; setBusy(false); setSection(item.id); setError(''); setResult(null) }} aria-current={section === item.id ? 'page' : undefined}><span className="nav-icon">{item.symbol}</span><span className="nav-label">{item.label}<small>{item.eyebrow}</small></span>{section === item.id && <span className="nav-active-mark" />}</button>)}</nav>
      <div className="sidebar-foot"><div className="integrity-seal">✓</div><strong>Evidence before assertion</strong><p>Research results must be traceable, bounded and independently verifiable.</p><div className="sidebar-build"><span>BUILD</span><b>PHASE 6 · CONTROLLED LAB</b></div></div>
    </aside>
    <main className="main-content" id="main-content" tabIndex={-1}>
      <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">{result !== null ? "Request completed. Response is available in the current workspace section." : ""}</p>
      <header className="topbar"><div className="breadcrumbs"><span>ASDS</span><span className="slash">/</span><strong>{active.label}</strong></div><div className="topbar-right"><span className={status === 'connected' ? 'live-dot online' : status === 'unavailable' ? 'live-dot offline' : 'live-dot'} /> <span role="status" aria-live="polite">{status === 'connected' ? 'API CONNECTED' : status === 'unavailable' ? 'API UNAVAILABLE' : 'CHECKING API'}</span><button className="icon-button" disabled={healthBusy} onClick={() => setRetryKey(k => k + 1)} title="Refresh API status" aria-label="Refresh API status">↻</button></div></header>
      <section className="page-heading"><div><p className="eyebrow"><span /> AUTONOMOUS SCIENTIFIC DISCOVERY SYSTEM</p><h1>{section === 'overview' ? <>Research with <em>rigour.</em></> : active.label}</h1><p className="page-subtitle">{section === 'overview' ? 'A traceable workspace for scholarly evidence, scientific records, mathematical tools and controlled computational experiments.' : section === 'literature' ? 'Search scholarly metadata through the configured OpenAlex and Crossref providers. Search results are not full-text review or proof of a claim.' : section === 'records' ? 'Inspect and create typed research records with server-generated provenance and integrity checks.' : section === 'knowledge' ? 'Explore controlled scientific concepts and evidence-linked relationships without inferring unsupported facts.' : section === 'math' ? 'Run bounded scientific calculations through the backend’s validated mathematical API.' : 'Submit a declarative computational plan to the configured lab runner. Execution is constrained by server-side policy.'}</p></div><div className="heading-badge"><span className="badge-pulse" /> RESEARCH SYSTEM <small>PRE-RELEASE</small></div></section>
      {section === 'overview' && <><section className="hero-panel"><div className="hero-copy"><span className="kicker">THE SCIENTIFIC METHOD, OPERATIONALISED</span><h2>From a well-formed question<br />to <span>verifiable evidence.</span></h2><p>Build a defensible chain from literature and research records to computation and experiment outputs. Capabilities are shown only where an implemented API exists.</p><button className="primary-button" onClick={() => setSection('literature')}>Explore research tools <span>→</span></button></div><div className="hero-visual" aria-label="Abstract scientific network illustration"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit orbit-three" /><div className="core-node">AS<span>CORE</span></div><i className="node node-a" /><i className="node node-b" /><i className="node node-c" /><i className="node node-d" /><span className="visual-caption">EVIDENCE · METHODS · RESULTS</span></div></section>
      <section className="metric-grid" aria-label="Live system metrics"><article className="metric-card"><span className="metric-label">API HEALTH</span><div className="metric-value"><span className={status === 'connected' ? 'live-dot online' : status === 'unavailable' ? 'live-dot offline' : 'live-dot'} />{presentation.label}</div><p>{health ? `${health.service} · v${health.version}` : 'Live health endpoint check'}</p><button className="text-action" onClick={() => setRetryKey(k => k + 1)}>Check connection ↗</button>{healthError && <small className="inline-error">{healthError}</small>}</article><article className="metric-card"><span className="metric-label">RESEARCH RECORDS</span><div className="metric-value">{recordCountLabel}</div><p>{recordTotal === null ? 'Load the record index to count stored items' : 'Total returned by the record service'}</p><button className="text-action" onClick={() => { setSection('records'); void runAction(loadRecords) }}>Load records ↗</button></article><article className="metric-card"><span className="metric-label">AVAILABLE TOOLSETS</span><div className="metric-value">04 <small>verified API groups</small></div><p>Literature, records, knowledge graph and bounded mathematics.</p><button className="text-action" onClick={() => setSection('math')}>Open tool registry ↗</button></article><article className="metric-card"><span className="metric-label">SCIENTIFIC INTEGRITY</span><div className="metric-value integrity-value">Evidence first</div><p>Checksums, typed records, bounded requests and honest capability status.</p><span className="status-chip">DESIGN PRINCIPLE</span></article></section>
      <section className="section-block"><div className="section-title"><div><span className="kicker">WORKSPACE DIRECTORY</span><h2>Research instruments</h2></div><span className="section-note">CONNECTED TO IMPLEMENTED API ROUTES</span></div><div className="instrument-grid">{nav.slice(1).map((item, i) => <button className="instrument-card" key={item.id} onClick={() => setSection(item.id)}><span className="instrument-symbol">{item.symbol}</span><span className="instrument-index">0{i + 1} / {item.eyebrow}</span><strong>{item.label}</strong><p>{['Retrieve scholarly metadata with configurable limits and optional record persistence.','Create, list and verify structured research records and audit events.','Search concepts and inspect evidence-linked scientific relationships.','Use symbolic, statistical, integration and unit-conversion endpoints.','Submit bounded declarative runs and inspect server responses.'][i]}</p><span className="instrument-link">Open workspace <b>↗</b></span></button>)}</div></section>
      <section className="integrity-banner"><span className="integrity-icon">✓</span><div><strong>Capability honesty is part of the architecture.</strong><p>Autonomous hypothesis generation, full-text claim verification, multi-agent orchestration and production sandbox certification are not represented as completed features.</p></div></section></>}
      {section === 'literature' && <section className="workspace-panel"><div className="panel-title"><div><span className="kicker">SCHOLARLY METADATA</span><h2>Search the literature</h2></div><span className="status-chip">OPENALEX + CROSSREF</span></div><p className="muted">Search provider metadata only. Results may be incomplete and are not an assessment of scientific truth.</p><form onSubmit={e => { e.preventDefault(); void doLiteratureSearch() }} className="form-stack"><label>Research query<input value={literatureQuery} onChange={e => setLiteratureQuery(e.target.value)} required minLength={3} maxLength={500} placeholder="e.g. protein folding uncertainty estimation" /></label><div className="form-row"><label>Maximum results<select value={literatureLimit} onChange={e => setLiteratureLimit(e.target.value)}><option value="5">5 results</option><option value="10">10 results</option></select></label><label className="checkbox-label"><input type="checkbox" checked={saveSources} onChange={e => setSaveSources(e.target.checked)} /> Save returned sources as research records</label></div><button className="primary-button" disabled={busy || !literatureQuery.trim()}>{busy ? 'Searching…' : 'Search scholarly sources →'}</button></form>{error && <ErrorNotice message={error} />}{result !== null && <ResultPanel title="Search response" data={result} />}</section>}
      {section === 'records' && <section className="workspace-panel"><div className="panel-title"><div><span className="kicker">PROVENANCE STORE</span><h2>Research record explorer</h2></div><span className="status-chip">{recordTotal === null ? 'NOT LOADED' : `${recordTotal} TOTAL`}</span></div><div className="toolbar"><label>Filter by record type<input value={recordQuery} onChange={e => setRecordQuery(e.target.value)} placeholder="Optional record type" /></label><button className="secondary-button" disabled={busy} onClick={() => void runAction(loadRecords)}>Load records</button></div>{error && <ErrorNotice message={error} />}{records.length > 0 ? <div className="record-table-wrap"><table className="record-table"><thead><tr><th>Record</th><th>Type</th><th>Created</th><th>Integrity</th></tr></thead><tbody>{records.map((record, i) => <tr key={String(record.id ?? i)}><td><strong>{String((typeof record.payload === 'object' && record.payload !== null ? (record.payload as JsonRecord).title ?? (record.payload as JsonRecord).preferred_label ?? (record.payload as JsonRecord).claim_text ?? (record.payload as JsonRecord).hypothesis : undefined) ?? record.id ?? 'Untitled record')}</strong><small>{String(record.id ?? '')}</small></td><td>{String(record.record_type ?? '—')}</td><td>{String(record.created_at ?? '—')}</td><td><span className="status-chip">CHECKSUM STORED</span></td></tr>)}</tbody></table></div> : <div className="empty-state"><span>▤</span><strong>No records loaded yet</strong><p>Load the server-backed record index. An empty view is not evidence that the database is empty.</p></div>}<div className="subsection"><div className="panel-title"><div><span className="kicker">CREATE A TRACEABLE ENTRY</span><h2>New research record</h2></div></div><p className="muted">The API validates the record schema and creates provenance metadata. Use the exact request schema documented by the backend.</p><label>Record JSON<textarea className="code-input" value={recordInput} onChange={e => setRecordInput(e.target.value)} spellCheck={false} rows={8} /></label><button className="primary-button" disabled={busy} onClick={() => void doCreateRecord()}>Validate and create record →</button></div>{result !== null && <ResultPanel title="Latest API response" data={result} />}</section>}
      {section === 'knowledge' && <section className="workspace-panel"><div className="panel-title"><div><span className="kicker">CONTROLLED VOCABULARY</span><h2>Scientific knowledge graph</h2></div><span className="status-chip">BOUNDED TRAVERSAL</span></div><p className="muted">Search existing concepts or load the controlled vocabulary. Graph edges are stored assertions, not automatically verified scientific facts.</p><form className="toolbar" onSubmit={e => { e.preventDefault(); void runAction(loadKnowledge) }}><label>Search concepts<input value={conceptQuery} onChange={e => setConceptQuery(e.target.value)} minLength={2} placeholder="Concept label, alias or definition" /></label><button className="primary-button" disabled={busy}>Search concepts →</button></form><div className="action-row"><button className="secondary-button" disabled={busy} onClick={() => void runAction(() => request('/api/v1/knowledge/vocabulary'))}>View supported vocabulary</button></div>{error && <ErrorNotice message={error} />}{result !== null && <ResultPanel title="Knowledge API response" data={result} />}</section>}
      {section === 'math' && <section className="workspace-panel"><div className="panel-title"><div><span className="kicker">BOUNDED COMPUTATION</span><h2>Mathematics workbench</h2></div><span className="status-chip">SERVER VALIDATED</span></div><p className="muted">Select a real API operation, edit its JSON request, and inspect the returned values and validation errors.</p><div className="tool-picker">{tools.map((tool, i) => <button key={tool.path} className={mathTool === i ? 'tool-option selected' : 'tool-option'} onClick={() => { setMathTool(i); setMathInput(pretty(tool.sample)); setResult(null); setError('') }}><span>{String(i + 1).padStart(2, '0')}</span><strong>{tool.title}</strong><small>{tool.path}</small></button>)}</div><p className="muted">{tools[mathTool].detail}</p><label>Request body (JSON)<textarea className="code-input" value={mathInput} onChange={e => setMathInput(e.target.value)} spellCheck={false} rows={8} /></label><button className="primary-button" disabled={busy} onClick={() => void doMath()}>{busy ? 'Computing…' : 'Run calculation →'}</button>{error && <ErrorNotice message={error} />}{result !== null && <ResultPanel title="Calculation response" data={result} />}</section>}
      {section === 'lab' && <section className="workspace-panel"><div className="panel-title"><div><span className="kicker">CONTROLLED EXECUTION</span><h2>Computational laboratory</h2></div><span className="status-chip">POLICY-BOUNDED</span></div><div className="notice notice-warning"><strong>Execution boundary</strong><p>The lab API requires configured authentication and may enforce tenant membership outside development. Only submit declarative plans that match the backend schema. This interface is not an OS-isolated sandbox certification.</p></div><label>Lab run request (JSON)<textarea className="code-input" value={labInput} onChange={e => setLabInput(e.target.value)} spellCheck={false} rows={12} /></label><button className="primary-button" disabled={busy} onClick={() => void doLab()}>{busy ? 'Submitting run…' : 'Submit controlled run →'}</button>{error && <ErrorNotice message={error} />}{result !== null && <ResultPanel title="Lab API response" data={result} />}</section>}
      <footer className="page-footer"><div><span className="footer-mark" /> <strong>ARTIFICIAL SCIENTIST</strong><span className="footer-version">ASDS · 0.1.0</span></div><p>Evidence over assertion · Reproducibility over convenience · No invented findings</p></footer>
    </main>
  </div>
}
function ResultPanel({ title, data }: { title: string; data: unknown }) { return <section className="result-panel" aria-label={title} aria-live="polite" aria-atomic="true"><div className="panel-title"><h3>{title}</h3><span className="status-chip">SERVER RESPONSE</span></div><DataView data={data} /></section> }
export { apiBaseUrl }
