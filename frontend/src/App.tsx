import { useEffect, useState } from 'react'

import { getStatusPresentation, isHealthyResponse, type ServiceStatus } from './lib/status'

interface HealthResponse {
  status: string
  service: string
  version: string
}

type PhaseState = 'INTEGRATED' | 'ADVANCED' | 'GATED' | 'OPEN'

interface Phase {
  id: number
  title: string
  state: PhaseState
  detail: string
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000')
  .replace(/\/+$/, '')

const phases: Phase[] = [
  { id: 0, title: 'Charter', state: 'ADVANCED', detail: 'Mission, boundaries, risk and evaluation baseline.' },
  { id: 1, title: 'Foundation', state: 'INTEGRATED', detail: 'Application shell, CI, configuration and health.' },
  { id: 2, title: 'Research records', state: 'INTEGRATED', detail: 'Typed records, provenance and audit structures.' },
  { id: 3, title: 'Literature', state: 'INTEGRATED', detail: 'Bounded scholarly retrieval and source provenance.' },
  { id: 4, title: 'Knowledge graph', state: 'INTEGRATED', detail: 'Controlled concepts and tenant-scoped relations.' },
  { id: 5, title: 'Scientific tools', state: 'INTEGRATED', detail: 'Bounded mathematics, units, statistics and plotting.' },
  { id: 6, title: 'Controlled lab', state: 'GATED', detail: 'Execution, artifacts, identity and quotas; sandbox gate remains open.' },
  { id: 7, title: 'Discovery', state: 'GATED', detail: 'Question decomposition, competing hypotheses and prior-work screening.' },
  { id: 8, title: 'Orchestration', state: 'INTEGRATED', detail: 'Finite-state workflows, approvals and recovery.' },
  { id: 9, title: 'Verification', state: 'INTEGRATED', detail: 'Independent bounded numerical verification.' },
  { id: 10, title: 'Scientific memory', state: 'INTEGRATED', detail: 'Versioned evidence, contradiction and rollback.' },
  { id: 11, title: 'Collaboration', state: 'INTEGRATED', detail: 'Bounded roles, budgets and conflict handling.' },
  { id: 12, title: 'Scientific writing', state: 'INTEGRATED', detail: 'Evidence-linked reports and explicit submission authorization.' },
  { id: 13, title: 'Governance', state: 'INTEGRATED', detail: 'Benchmarks, adversarial categories and release decisions.' },
  { id: 14, title: 'Multidisciplinary', state: 'GATED', detail: 'Evidence-gated domains with a hard physical-action boundary.' },
]

const releaseGates = [
  'Reviewed OS-level execution sandbox',
  'Real OIDC/JWKS provider validation and rotation evidence',
  'Sanitized migration, backup, restore and rollback rehearsal',
  'Independent security review and operational deployment validation',
  'Scientific benchmark, replication and domain-expert evidence',
]

const researchPrinciples = [
  ['EVIDENCE', 'Claims stay linked to sources, calculations or explicit hypotheses.'],
  ['FALSIFICATION', 'Competing explanations and discriminating tests are first-class records.'],
  ['PROVENANCE', 'Inputs, outputs, versions and decisions remain traceable.'],
  ['AUTHORIZATION', 'Consequential actions require explicit approval and bounded state transitions.'],
]

export default function App() {
  const [status, setStatus] = useState<ServiceStatus>('checking')
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    async function checkApi() {
      setStatus('checking')
      setErrorMessage(null)

      try {
        const response = await fetch(apiBaseUrl + '/api/v1/health', {
          method: 'GET',
          headers: { Accept: 'application/json' },
          signal: controller.signal,
        })

        if (!response.ok) throw new Error('The API returned HTTP ' + response.status + '.')

        const payload: unknown = await response.json()
        if (!isHealthyResponse(payload)) throw new Error('The API did not report a healthy status.')

        setHealth({ status: payload.status, service: payload.service, version: payload.version })
        setStatus('connected')
      } catch (error) {
        if (controller.signal.aborted) return
        setHealth(null)
        setStatus('unavailable')
        setErrorMessage(
          error instanceof Error ? error.message : 'An unknown connection error occurred.',
        )
      }
    }

    void checkApi()
    return () => controller.abort()
  }, [retryKey])

  const presentation = getStatusPresentation(status)
  const integratedCount = phases.filter((phase) => phase.state === 'INTEGRATED').length
  const gatedCount = phases.filter((phase) => phase.state === 'GATED').length

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true"><span /><span /><span /></div>
          <div>
            <p className="brand-name">ARTIFICIAL</p>
            <p className="brand-name brand-name-secondary">SCIENTIST</p>
          </div>
        </div>

        <div className="sidebar-section-label">RESEARCH SYSTEM</div>
        <nav aria-label="Research workspace">
          <a className="nav-item nav-item-active" href="#overview" aria-current="page">
            <span className="nav-symbol">◫</span> Overview <span className="nav-indicator" />
          </a>
          <a className="nav-item" href="#architecture"><span className="nav-symbol">⌘</span> Architecture</a>
          <a className="nav-item" href="#phases"><span className="nav-symbol">◌</span> Phase map</a>
          <a className="nav-item" href="#release-gates"><span className="nav-symbol">◇</span> Release gates</a>
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-orbit" aria-hidden="true"><span /><span /><span /></div>
          <p className="sidebar-note">Research before autonomy.</p>
          <p className="sidebar-subnote">Evidence, falsification, provenance and authorization are system invariants.</p>
          <div className="sidebar-version">INTEGRATED MAIN · 14 PHASES</div>
        </div>
      </aside>

      <main className="main-content" id="overview">
        <header className="topbar">
          <div className="breadcrumb">
            <span>ASDS</span><span className="breadcrumb-divider">/</span><strong>Governed research workspace</strong>
          </div>
          <div className="topbar-status">
            <span className={status === 'connected' ? 'status-dot status-dot-ok' : 'status-dot'} />
            <span>{status === 'connected' ? 'API CONNECTED' : 'DEVELOPMENT / GATED'}</span>
          </div>
        </header>

        <section className="welcome-section">
          <div className="eyebrow"><span /> ARTIFICIAL SCIENTIST · SYSTEM OVERVIEW</div>
          <h1>Scientific discovery<br /><span>with evidence as the control plane.</span></h1>
          <p className="welcome-copy">
            ASDS is a research-first platform for traceable questions, evidence, hypotheses,
            controlled computation, independent verification and bounded scientific autonomy.
            Capability expansion is gated by implementation evidence and explicit security review.
          </p>
          <div className="welcome-meta">
            <span className="meta-line" /><span>EVIDENCE BEFORE CLAIMS</span>
            <span className="meta-divider">·</span><span>FALSIFICATION BEFORE CONFIDENCE</span>
            <span className="meta-divider">·</span><span>AUTHORIZATION BEFORE CONSEQUENCE</span>
          </div>
        </section>

        <section className="summary-grid" aria-label="System status">
          <article className="summary-card summary-card-primary">
            <div className="card-topline"><span className="card-label">RUNTIME CONNECTION</span><span className="card-icon">◉</span></div>
            <div className="connection-status">
              <span className={status === 'connected' ? 'status-dot status-dot-ok' : status === 'unavailable' ? 'status-dot status-dot-error' : 'status-dot'} />
              <h2>{presentation.label}</h2>
            </div>
            <p className="card-description">{presentation.detail}</p>
            <p className="connection-detail">
              {health ? health.service + ' · v' + health.version : 'Expected API: ' + apiBaseUrl}
            </p>
            {errorMessage && <p className="error-message" role="status">{errorMessage}</p>}
            <button className="secondary-button" type="button" onClick={() => setRetryKey((key) => key + 1)}>
              Retry connection <span aria-hidden="true">↗</span>
            </button>
          </article>

          <article className="summary-card">
            <div className="card-topline"><span className="card-label">CAPABILITY MAP</span><span className="card-icon">⌁</span></div>
            <p className="metric-value">{integratedCount}<span> / {phases.length}</span></p>
            <h2>Capability layers integrated</h2>
            <p className="card-description">{gatedCount} phases remain explicitly gated by acceptance evidence rather than being represented as production-complete.</p>
            <div
              className="milestone-track"
              role="progressbar"
              aria-label="Integrated capability phases"
              aria-valuemin={0}
              aria-valuemax={phases.length}
              aria-valuenow={integratedCount}
            >
              <span style={{ width: ((integratedCount / phases.length) * 100).toFixed(1) + '%' }} />
            </div>
            <p className="metric-footnote">Capability-led roadmap · no fixed delivery dates</p>
          </article>

          <article className="summary-card">
            <div className="card-topline"><span className="card-label">RELEASE POSTURE</span><span className="card-icon">◇</span></div>
            <div className="principle-icon" aria-hidden="true">!</div>
            <h2>Evidence-gated, not production-certified</h2>
            <p className="card-description">
              Repository CI is green, but OS sandbox deployment, live identity verification,
              operational rehearsal, independent security review and scientific validation remain open.
            </p>
            <div className="principle-footnote"><span /> RELEASE GATES ACTIVE</div>
          </article>
        </section>

        <section className="content-grid" id="architecture">
          <article className="workspace-card">
            <div className="section-heading">
              <div><p className="card-label">SCIENTIFIC CONTROL LOOP</p><h2>From question to governed result</h2></div>
              <span className="section-index">CONTROL / 01</span>
            </div>
            <div className="research-steps">
              {[
                ['01', 'Question', 'Define variables, scope and unresolved assumptions.'],
                ['02', 'Evidence', 'Retrieve and preserve source identity and provenance.'],
                ['03', 'Hypotheses', 'Compare alternatives and define falsification criteria.'],
                ['04', 'Experiment', 'Run only bounded, authorized computational work.'],
                ['05', 'Verification', 'Independently check outputs, uncertainty and alternatives.'],
                ['06', 'Memory', 'Retain evidence-linked findings without erasing history.'],
              ].map(([number, title, detail], index, items) => (
                <div className="research-step" key={number}>
                  <div className="step-number">{number}</div>
                  <div className="step-content"><h3>{title}</h3><p>{detail}</p></div>
                  <span className="step-state">BOUNDED</span>
                  {index < items.length - 1 && <span className="step-connector" aria-hidden="true" />}
                </div>
              ))}
            </div>
          </article>

          <article className="workspace-card">
            <div className="section-heading">
              <div><p className="card-label">SYSTEM INVARIANTS</p><h2>Scientific integrity by construction</h2></div>
              <span className="section-index">CORE / 04</span>
            </div>
            <ul className="capability-list">
              {researchPrinciples.map(([label, detail], index) => (
                <li key={label}>
                  <span className="capability-number">0{index + 1}</span>
                  <span><strong className="principle-label">{label}</strong><br /><span className="principle-detail">{detail}</span></span>
                  <span className="planned-tag">REQUIRED</span>
                </li>
              ))}
            </ul>
          </article>
        </section>

        <section className="workspace-card phase-map" id="phases">
          <div className="section-heading">
            <div><p className="card-label">DEVELOPMENT ROADMAP</p><h2>Capability maturity across Phase 0 → 14</h2></div>
            <span className="section-index">STATUS / LIVE REPOSITORY</span>
          </div>
          <div className="phase-grid">
            {phases.map((phase) => (
              <article className={'phase-card phase-' + phase.state.toLowerCase()} key={phase.id}>
                <div className="phase-card-top">
                  <span className="phase-number">{String(phase.id).padStart(2, '0')}</span>
                  <span className="phase-state">{phase.state}</span>
                </div>
                <h3>{phase.title}</h3>
                <p>{phase.detail}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="workspace-card release-panel" id="release-gates">
          <div className="section-heading">
            <div><p className="card-label">RELEASE EVIDENCE REGISTER</p><h2>Open gates that CI cannot self-certify</h2></div>
            <span className="section-index">SECURITY / SCIENCE</span>
          </div>
          <div className="gate-list">
            {releaseGates.map((gate, index) => (
              <div className="gate-row" key={gate}>
                <span className="gate-number">{String(index + 1).padStart(2, '0')}</span>
                <span className="gate-copy">{gate}</span>
                <span className="gate-state">OPEN</span>
              </div>
            ))}
          </div>
          <p className="workflow-note">
            “Open” means evidence is still required. The platform intentionally fails closed where
            a missing security or authorization boundary could otherwise become an implicit capability.
          </p>
        </section>

        <footer className="page-footer">
          <div><span className="footer-mark" /> ARTIFICIAL SCIENTIST <span className="footer-version">ASDS</span></div>
          <p>Research-first · evidence-led · bounded autonomy · no unsupported claims of autonomous discovery</p>
        </footer>
      </main>
    </div>
  )
}
