# Research Workspace v1 — Implementation and Acceptance Notes

**Branch:** \`feat/research-workspace-v1\`  
**Base:** \`phase-release-verification-hardening\`  
**Status:** implementation in progress; CI and review evidence required before integration  
**Scope:** the first usable frontend-to-API research workflow

This document records what this branch introduces. It does not supersede the external release gates in \`docs/release/EVIDENCE_MATRIX.md\`.

## Delivered user-facing surfaces

The previous overview-only page is replaced by a navigable React research workspace. The first five planned capability areas now have working screens backed by existing API endpoints:

| Surface | Frontend behavior | API integration |
|---|---|---|
| Scientific Command Center | Runtime health, research workflow overview, 12-panel maturity and explicit availability boundaries | \`GET /api/v1/health\` |
| Research Agenda & Problem Observatory | Create a durable research-task record; decompose a question; edit researcher-confirmed variables | \`POST /api/v1/records\`, \`POST /api/v1/discovery/decompose\` |
| Literature & Evidence Explorer | Search OpenAlex/Crossref metadata; inspect provider status; save bibliographic sources as unassessed records | \`POST /api/v1/literature/search\`, \`POST /api/v1/records\` |
| Hypothesis & Discovery Lab | Create deterministic directional candidate templates; perform bounded prior-work metadata screen; assess and persist candidates | \`POST /api/v1/discovery/generate\`, \`POST /api/v1/discovery/prior-work-screen\`, \`POST /api/v1/discovery/assess\` |
| Mathematics & Formal Reasoning Workbench | Submit bounded symbolic simplification, differentiation, integration, solving and evaluation | \`POST /api/v1/math/symbolic\` |
| Research Records (supporting surface) | Browse paginated immutable record envelopes and their content identifiers | \`GET /api/v1/records\` |

The record browser is a supporting surface rather than a claim that all 12 planned panels are complete.

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
- Retrieved source records are saved as \`unassessed\`; users must inspect original material.
- The browser client does not yet have a reviewed OIDC sign-in/session or tenant-selection adapter. In production, protected write and record/discovery endpoints remain unavailable until that adapter and a real identity provider are configured.
- No execution UI is exposed as production-ready. The lab still requires reviewed OS-level sandbox deployment and external security acceptance.

## Verification introduced

- API-client unit tests cover missing configuration, unsafe paths, JSON GET/POST behavior, response errors and refusal of non-JSON success responses.
- Playwright covers keyboard operation across the new workspaces, visible capability boundaries and the research-record surface.
- Automated axe accessibility checks remain part of the frontend workflow.
- Type-check, unit tests, production build, E2E, Python suites and release-gate jobs are required CI evidence for the exact branch head.

A passing frontend test suite verifies the interface and API-client contract. It does not prove live OIDC, database operations, third-party provider availability, sandbox isolation or production operation.

## Remaining frontend sequence

1. Add the Knowledge Graph and Vocabulary interface with tenant-safe concept and relationship operations.
2. Add Data Analysis and Results views for statistics, plots and comparison of retained outputs.
3. Add Lab, Experiment Journal and Reproducibility interfaces only with explicit blocked states until reviewed execution controls are actually deployed.
4. Add Scientific Memory and Learning, Manuscript Studio, and Review/Governance interfaces through the existing backend services and documented approval semantics.
5. Add OIDC login/session and tenant selection only after selecting and configuring a real provider; never replace identity with a client-side role selector.
6. Complete real browser acceptance for each role and protected API operation; add end-to-end tests with isolated test identities and tenant fixtures.

## Integration and release rule

This branch is stacked on the release-hardening work. It must be reviewed as its own change set and tested against its final head. Do not merge it, mark all panels complete, configure fabricated production API endpoints, provision paid infrastructure, or promote a deployment as a result of this UI implementation alone.
