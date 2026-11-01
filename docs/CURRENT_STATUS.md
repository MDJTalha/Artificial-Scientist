# ASDS Artificial Scientist — Current Engineering Status

**Snapshot:** 2026-11-01 18:15 PKT  
**Repository:** `MDJTalha/Artificial-Scientist`  
**Default branch:** `main`  
**Status:** Active release-candidate development; not production-certified.

This document separates the merged baseline from the current unmerged development stack. Pull-request changes are not part of `main` until reviewed and merged by the repository owner.

## Verified repository state

### Merged baseline

The last independently recorded merged baseline in the repository status history is main commit `b28b6bdaffa4851a2dec390460706e100302d138`, with successful CI run 1114. The current development work is being prepared in open pull requests stacked on that baseline.

Do not describe unmerged pull-request functionality as already integrated into `main`.

### Active pull-request stack

| PR | Branch | Scope | State |
|---|---|---|---|
| [#40](https://github.com/MDJTalha/Artificial-Scientist/pull/40) | `feat/complete-functional-workspaces` | Functional scientific workspace panels | Open, draft |
| [#41](https://github.com/MDJTalha/Artificial-Scientist/pull/41) | `fix/auth0-deployment-and-readiness-audit` | Auth0/OIDC alignment, API authorization and fail-closed release gates | Open, ready for review |
| This status update | `docs/current-status-2026-11-01` | Synchronize engineering status evidence | Proposed stacked documentation change |

PR #41 targets PR #40's branch, and PR #40 targets `main`. Preserve this dependency order during review. Neither PR has been merged. No production settings or production branch have been changed as part of this work.

## Exact-commit CI evidence

The GitHub Actions checks were queried against the exact current head SHAs:

| Pull request | Head SHA | Backend Python 3.12 | Backend Python 3.13 | Frontend checks | Container smoke |
|---|---|---|---|---|---|
| #40 | `f95bb8107e78586e8d5a0ac98f3165a0022b9f7c` | Passed | Passed | Passed | Passed |
| #41 | `766e45eacc2d93ce3ec4409d536e3e5c3164b2ef` | Passed | Passed | Passed | Passed |

Frontend checks include type-checking, unit tests and production asset build. These results establish repository CI for those exact commits only; they do not establish production readiness.

A Codex code-review summary on PR #41 reported no findings for reviewed commit `d4c2bbda8dbfaaacb554d0f7fdbab308d604df15`. That review is not an independent security audit and should not be represented as one.

## Preview deployment evidence

- A Vercel notification reported a Ready Preview for PR #41: [open preview](https://artificial-scienti-git-a1de43-muhammad-talhas-projects-381912c6.vercel.app).
- Earlier deployment attempts were rejected by the Vercel free-plan daily deployment limit (`api-deployments-free-per-day`).
- The Ready Preview is a preview deployment only. Its existence does not verify the production environment, live backend connectivity, Auth0 token flow, durable persistence or release acceptance.
- Record the exact deployment ID and deployed commit whenever a release candidate is assessed.

## Phase status

| Phase | Engineering status | Release interpretation |
|---|---|---|
| 0 | Repository baseline complete | External evaluation and review remain evidence-dependent |
| 1–5 | Implemented in the merged baseline | Operational setup, provider availability, licensing and scientific benchmark evidence remain environment-dependent |
| 6 | Hardened implementation; release-gated | Reviewed OS sandbox, live identity-provider validation, migration/recovery rehearsal, operational validation and independent security review remain open |
| 7 | Implemented with acceptance gates | Tenant-isolation and discovery controls require exact-deployment validation; truth, novelty and domain-expert validation remain open |
| 8–14 | Bounded implementation and governance controls in the merged baseline | Broader benchmark, external review and domain-specific evidence remain required |
| Frontend workspace expansion | Implemented in open PR #40, not merged | Requires owner review and ordered integration |
| Auth0 deployment/auth hardening | Implemented in open PR #41, not merged | Requires owner review, live provider configuration and end-to-end token validation |

## Current change summaries

### PR #40 — functional scientific workspaces

- Replaces four placeholder panels with research workflows for experiment journaling, scientific-memory drafts, collaboration and manuscript drafting.
- Memory and manuscript drafts remain browser-session only; they are not represented as durable server-side records.
- Protected research operations remain fail-closed pending tenant-scoped authorization review.
- Computational execution remains gated pending reviewed sandbox deployment and authenticated OIDC integration.

### PR #41 — Auth0 and API authorization hardening

- Aligns deployment documentation and environment examples with Auth0 SPA/API configuration.
- Requires the actual Auth0 API Identifier to be confirmed by the tenant owner; no audience or scope is invented.
- Applies OIDC protection to the relevant literature, knowledge, discovery and autonomy routes while preserving the explicit public vocabulary endpoint.
- Registers the Phase 7 record/discovery fail-closed isolation gate in the middleware stack.
- Removes the legacy shared lab API key as an alternative to per-user OIDC identity.
- Adds regression tests for missing/valid bearer tokens and fail-closed behavior.

## External release blockers

These cannot be certified complete by repository edits, mocks, or CI alone:

1. **Auth0 production integration:** confirm the Auth0 API Identifier and any required scopes; configure exact frontend/backend settings; validate real access tokens against the deployed backend, including issuer, audience, signature, expiry, JWKS rotation and tenant membership.
2. **Tenant-scoped records:** retain fail-closed behavior until record ownership, server-side authorization, migration and cross-tenant adversarial tests are independently reviewed.
3. **Durable persistence:** implement and rehearse an approved durable database strategy, including sanitized migration, backup, restore, WAL/recovery, rollback and ownership reconciliation. A `DATABASE_URL` alone does not convert SQLite-specific stores to PostgreSQL.
4. **Reviewed execution sandbox:** deploy and independently test filesystem, network, syscall/capability, identity, CPU, memory, PID, artifact and cleanup boundaries. The current bounded subprocess worker and POSIX resource limits are not an OS-level sandbox.
5. **Operations and security:** verify TLS, secrets management, least privilege, audit retention, monitoring, alerting, rate limiting, incident response and independent security review.
6. **Scientific assurance:** perform reproducibility/replication benchmarks, domain-expert review, source-quality and prompt-injection assessments, and explicit uncertainty/limitation reporting.

## Required review and release sequence

1. Review PR #40 and its exact-head checks; do not merge it without owner approval.
2. Review PR #41 after #40's scope and target are understood; retain the fail-closed controls.
3. Review the documentation synchronization change independently.
4. Configure Auth0 with owner-confirmed identifiers and run live browser-to-backend integration tests.
5. Complete the persistence, sandbox, operational, independent-security and scientific-evaluation evidence gates.
6. Only then prepare a production release candidate with exact commit SHAs, CI links, deployment IDs, test outcomes, limitations and explicit owner approval.

## Engineering rule

No phase, security control, deployment, scientific conclusion or certification is marked complete solely because documentation exists or automated tests pass. Every external gate remains **OPEN** until concrete evidence, scope, version, outcomes, limitations, reviewer and sign-off are recorded.

Never include credentials, access tokens, private connection strings or private research data in this status record.
