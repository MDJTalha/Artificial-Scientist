import { useEffect, useState } from 'react'

import { getStatusPresentation, isHealthyResponse, type ServiceStatus } from './lib/status'

interface HealthResponse {
  status: string
  service: string
  version: string
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000')
  .replace(/\/+$/, '')

const researchSteps = [
  { number: '01', title: 'Define a question', detail: 'Scope a testable research objective.' },
  { number: '02', title: 'Gather evidence', detail: 'Retrieve sources with traceable provenance.' },
  { number: '03', title: 'Test a hypothesis', detail: 'Use controlled computation and verification.' },
  { number: '04', title: 'Record the result', detail: 'Preserve methods, outcomes, and limitations.' },
]

const plannedCapabilities = [
  'Literature retrieval and citation verification',
  'Mathematical computation and simulation',
  'Hypothesis generation and experiment orchestration',
  'Scientific memory and reproducible reports',
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

        if (!response.ok) {
          throw new Error('The API returned HTTP ' + response.status + '.')
        }

        const payload: unknown = await response.json()
        if (!isHealthyResponse(payload)) {
          throw new Error('The API did not report a healthy status.')
        }

        setHealth({
          status: payload.status,
          service: payload.service,
          version: payload.version,
        })
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

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div>
            <p className="brand-name">ARTIFICIAL</p>
            <p className="brand-name brand-name-secondary">SCIENTIST</p>
          </div>
        </div>

        <div className="sidebar-section-label">RESEARCH SYSTEM</div>
        <nav aria-label="Research workspace">
          <a className="nav-item nav-item-active" href="#overview" aria-current="page">
            <span className="nav-symbol">◫</span>
            Overview
            <span className="nav-indicator" />
          </a>
          <button className="nav-item nav-item-disabled" type="button" disabled>
            <span className="nav-symbol">⌕</span>
            Research agenda
            <span className="nav-soon">PLANNED</span>
          </button>
          <button className="nav-item nav-item-disabled" type="button" disabled>
            <span className="nav-symbol">⌘</span>
            Evidence explorer
            <span className="nav-soon">PLANNED</span>
          </button>
          <button className="nav-item nav-item-disabled" type="button" disabled>
            <span className="nav-symbol">∑</span>
            Computing lab
            <span className="nav-soon">PLANNED</span>
          </button>
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-orbit" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <p className="sidebar-note">A research-first project</p>
          <p className="sidebar-subnote">Built around evidence, verification, and discovery.</p>
          <div className="sidebar-version">FOUNDATION 0.1.0</div>
        </div>
      </aside>

      <main className="main-content" id="overview">
        <header className="topbar">
          <div className="breadcrumb">
            <span>WORKSPACE</span>
            <span className="breadcrumb-divider">/</span>
            <strong>System overview</strong>
          </div>
          <div className="topbar-status">
            <span className={status === 'connected' ? 'status-dot status-dot-ok' : 'status-dot'} />
            <span>{status === 'connected' ? 'LOCAL API ONLINE' : 'LOCAL DEVELOPMENT'}</span>
          </div>
        </header>

        <section className="welcome-section">
          <div className="eyebrow"><span /> PHASE 1 · CORE FOUNDATION</div>
          <h1>Scientific discovery<br /><span>starts with a question.</span></h1>
          <p className="welcome-copy">
            A foundation for rigorous, multidisciplinary research. The current milestone
            establishes the application shell and connection checks before research engines are added.
          </p>
          <div className="welcome-meta">
            <span className="meta-line" />
            <span>RESEARCH BEFORE AUTONOMY</span>
            <span className="meta-divider">·</span>
            <span>EVIDENCE BEFORE CLAIMS</span>
          </div>
        </section>

        <section className="summary-grid" aria-label="System summary">
          <article className="summary-card summary-card-primary">
            <div className="card-topline">
              <span className="card-label">APPLICATION STATUS</span>
              <span className="card-icon">◉</span>
            </div>
            <div className="connection-status">
              <span className={status === 'connected' ? 'status-dot status-dot-ok' : status === 'unavailable' ? 'status-dot status-dot-error' : 'status-dot'} />
              <h2>{presentation.label}</h2>
            </div>
            <p className="card-description">{presentation.detail}</p>
            {health ? (
              <p className="connection-detail">{health.service} · v{health.version}</p>
            ) : (
              <p className="connection-detail">Expected API: {apiBaseUrl}</p>
            )}
            {errorMessage && <p className="error-message" role="status">{errorMessage}</p>}
            <button className="secondary-button" type="button" onClick={() => setRetryKey((key) => key + 1)}>
              Retry connection <span aria-hidden="true">↗</span>
            </button>
          </article>

          <article className="summary-card">
            <div className="card-topline">
              <span className="card-label">CURRENT MILESTONE</span>
              <span className="card-icon">⌁</span>
            </div>
            <p className="metric-value">01<span> / 14</span></p>
            <h2>Core application foundation</h2>
            <p className="card-description">
              Establishing a tested backend, frontend workspace, and reliable development checks.
            </p>
            <div className="milestone-track" aria-label="Phase 1 of 14 planned development phases">
              <span />
            </div>
            <p className="metric-footnote">Capability-led roadmap · no fixed delivery dates</p>
          </article>

          <article className="summary-card">
            <div className="card-topline">
              <span className="card-label">SCIENTIFIC INTEGRITY</span>
              <span className="card-icon">◇</span>
            </div>
            <div className="principle-icon" aria-hidden="true">✓</div>
            <h2>Evidence over assertion</h2>
            <p className="card-description">
              The system must distinguish verified results, source-reported claims, calculations,
              and hypotheses. No research capability is marked active until implemented and tested.
            </p>
            <div className="principle-footnote"><span /> FOUNDATIONAL REQUIREMENT</div>
          </article>
        </section>

        <section className="content-grid">
          <article className="workspace-card" id="research-cycle">
            <div className="section-heading">
              <div>
                <p className="card-label">TARGET WORKFLOW</p>
                <h2>From question to evidence</h2>
              </div>
              <span className="section-index">WORKFLOW / 01</span>
            </div>
            <div className="research-steps">
              {researchSteps.map((step, index) => (
                <div className="research-step" key={step.number}>
                  <div className="step-number">{step.number}</div>
                  <div className="step-content">
                    <h3>{step.title}</h3>
                    <p>{step.detail}</p>
                  </div>
                  <span className="step-state">PLANNED</span>
                  {index < researchSteps.length - 1 && <span className="step-connector" aria-hidden="true" />}
                </div>
              ))}
            </div>
            <p className="workflow-note">
              This describes the intended workflow. Automated research execution is not connected yet.
            </p>
          </article>

          <article className="workspace-card" id="planned-capabilities">
            <div className="section-heading">
              <div>
                <p className="card-label">CAPABILITY REGISTER</p>
                <h2>Planned foundations</h2>
              </div>
              <span className="section-index">NEXT</span>
            </div>
            <p className="register-intro">
              These capabilities will be implemented in later milestones and enabled only after validation.
            </p>
            <ul className="capability-list">
              {plannedCapabilities.map((capability, index) => (
                <li key={capability}>
                  <span className="capability-number">0{index + 1}</span>
                  <span>{capability}</span>
                  <span className="planned-tag">PLANNED</span>
                </li>
              ))}
            </ul>
          </article>
        </section>

        <footer className="page-footer">
          <div><span className="footer-mark" /> ARTIFICIAL SCIENTIST <span className="footer-version">0.1.0</span></div>
          <p>Research project · No commercial features · No claims of autonomous discovery yet</p>
        </footer>
      </main>
    </div>
  )
}
