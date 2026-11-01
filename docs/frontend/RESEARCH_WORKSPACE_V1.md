# Research Workspace v1 — Implementation and Acceptance Notes

**Branch:** \`feat/research-workspace-v1\`  
**Base:** \`phase-release-verification-hardening\`  
**Status:** implementation in progress; CI and review evidence required before integration  
**Scope:** the first usable frontend-to-API research workflow

This document records what this branch introduces. It does not supersede the external release gates in \`docs/release/EVIDENCE_MATRIX.md\`.

## Delivered user-facing surfaces

The previous overview-only page is replaced by a navigable React research workspace. The first nine planned capability areas now have working screens backed by existing API endpoints:

| Surface | Frontend behavior | API integration |
|---|---|---|
| Scientific Command Center | Runtime health, research workflow overview, 12-panel maturity and explicit availability boundaries | \`GET /api/v1/health\` |
| Research Agenda & Problem Observatory | Create a durable research-task record; decompose a question; edit researcher-confirmed variables | \`POST /api/v1/records\`, \`POST /api/v1/discovery/decompose\` |
| Literature & Evidence Explorer | Search OpenAlex/Crossref metadata; inspect provider status; save bibliographic sources as unassessed records | \`POST /api/v1/literature/search\`, \`POST /api/v1/records\` |
| Scientific Knowledge Graph & Vocabulary | Create and search concepts; read the supported controlled vocabulary; add proposed relationship assertions; inspect bounded graph neighborhoods | `GET /api/v1/knowledge/vocabulary`, `GET /api/v1/knowledge/concepts`, `POST /api/v1/knowledge/concepts`, `POST /api/v1/knowledge/relationships`, `GET /api/v1/knowledge/graph/neighborhood` |
| Hypothesis & Discovery Lab | Create deterministic directional candidate templates; perform bounded prior-work metadata screen; assess and persist candidates | \`POST /api/v1/discovery/generate\`, \`POST /api/v1/discovery/prior-work-screen\`, \`POST /api/v1/discovery/assess\` |
| Computational Laboratory & Simulation Center | Submit bounded declarative lab runs using allowlisted operations; inspect step outcomes, hashes and run history; replay and compare outputs in development only | `POST /api/v1/lab/runs`, `GET /api/v1/lab/runs`, `GET /api/v1/lab/runs/{run_id}`, `POST /api/v1/lab/runs/{run_id}/verify` |
| Experiment Journal & Reproducibility | Browse persisted run history; inspect run records, hashes, environment manifests and result artifacts; compare a replay; download a checksum-manifest ZIP | `GET /api/v1/lab/runs`, `GET /api/v1/lab/runs/{run_id}`, `GET /api/v1/lab/runs/{run_id}/artifacts`, `POST /api/v1/lab/runs/{run_id}/verify`, `GET /api/v1/lab/runs/{run_id}/export` |
| Data Analysis & Results Observatory | Calculate descriptive statistics and bounded function plots from supplied numeric inputs | `POST /api/v1/math/statistics`, `POST /api/v1/math/plot` |
| Mathematics & Formal Reasoning Workbench | Submit bounded symbolic simplification, differentiation, integration, solving and evaluation | \`POST /api/v1/math/symbolic\` |
| Research Records (supporting surface) | Browse paginated immutable record envelopes and their content identifiers | \`GET /api/v1/records\` |

The record browser is a supporting surface rather than a claim that all 12 planned panels are complete. The initial release now contains nine implemented capability screens; several data-mutating screens remain gated in production until OIDC is connected. The knowledge-graph UI preserves the backend's distinction between proposed, reviewed, disputed and rejected relationships; creating an edge does not establish that it is true.

## API client controls

\`frontend/src/lib/api.ts\` introduces a typed JSON client with the following controls:

- refuses to send requests when the API origin is not configured;
- accepts only absolute same-origin-relative API paths, rejecting external and protocol-relative paths;
- omits browser credentials and does not store responses in cache;
- rejects redirects and malformed / non-JSON success responses;
- exposes HTTP status and safe API error details to the UI;
- does not embed a shared API key or pretend to establish an authenticated session.

The production API origin continues to use the existing fail-closed \`resolveApiBaseUrl\` validation. HTTPS and a real backend origin are required in production.

## Scientific and security boundaries shown in the UI

- Question decomposition is a bounded text heuristic. The researcher must confirm and correct extracted variables.
- Candidate hypotheses are deterministic templates, not LLM outputs or scientific discoveries.
- Completeness rubric scores describe required structure; they are not probabilities, confidence estimates or measures of truth.
- Literature search retrieves bibliographic metadata only. It does not download full text, extract claims or prove novelty.
- Knowledge graph concepts and relationships are immutable records. Newly created concepts are proposed; newly created relationships are proposed assertions without independent source verification. Neighborhood traversal is bounded and excludes rejected edges.
- Retrieved source records are saved as \`unassessed\`; users must inspect original material.
- The browser client does not yet have a reviewed OIDC sign-in/session or tenant-selection adapter. In production, protected write, record, discovery and knowledge-graph operations are disabled in the UI until that adapter and a real identity provider are configured. Development-only bypasses do not imply production identity readiness.
- The Data Analysis workspace uses the existing descriptive-statistics and plot endpoints. Statistics describe only supplied values; plots are bounded mathematical visualizations, not scientific conclusions.
- The Computational Laboratory UI accepts declarative JSON only and exposes the existing bounded operations: symbolic math, integration, root finding, statistics and unit conversion. The run definition is validated by the backend; arbitrary code, notebook execution and shell commands are not accepted.
- The Experiment Journal is also development-only and uses the same authenticated tenant and sandbox gate as the Computational Lab. It exposes persisted run and artifact metadata, replay comparison, and ZIP export; it does not treat a checksum as a digital signature or a replay as scientific validation.
- The lab UI is intentionally development-only. It is disabled in production builds until a reviewed OS-level sandbox, adversarial isolation evidence and authenticated tenant session are deployed. The UI's development-mode access is not itself evidence of a secure production execution boundary.
- Lab run replay compares configuration, runtime environment and step outputs. A matching replay supports computational reproducibility only; it is not evidence of scientific validity.

## Verification introduced

- API-client unit tests cover missing configuration, unsafe paths, JSON GET/POST behavior, response errors and refusal of non-JSON success responses.
- Playwright covers keyboard operation across the new workspaces, visible capability boundaries, knowledge-graph, computational-lab, experiment-journal and data-analysis navigation, and the research-record surface.
- Automated axe accessibility checks remain part of the frontend workflow.
- Type-check, unit tests, production build, E2E, Python suites and release-gate jobs are required CI evidence for the exact branch head.

A passing frontend test suite verifies the interface and API-client contract. It does not prove live OIDC, database operations, third-party provider availability, sandbox isolation or production operation.

## Remaining frontend sequence

1. Add Scientific Memory and Learning, Manuscript Studio, and Review/Governance interfaces through existing backend services and documented approval semantics.
2. Add OIDC login/session and tenant selection only after selecting and configuring a real provider; never replace identity with a client-side role selector.
3. Complete real browser acceptance for each role and protected API operation; add end-to-end tests with isolated test identities and tenant fixtures.
4. Add a provider-independent AI model gateway only after provider choice, data-governance and operating-cost approval.

## Integration and release rule

This branch is stacked on the release-hardening work. It must be reviewed as its own change set and tested against its final head. Do not merge it, mark all panels complete, configure fabricated production API endpoints, provision paid infrastructure, or promote a deployment as a result of this UI implementation alone.
