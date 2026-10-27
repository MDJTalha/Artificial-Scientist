# Frontend Accessibility, Integrated Journey, and Release Verification

This checklist separates repository/CI evidence from checks that require a real browser, API process, deployment, or human review. Do not mark a manual check complete from a successful TypeScript build alone.

## 1. Automated checks (GitHub Actions)

- [ ] Frontend typecheck, unit tests, production build pass on the final PR commit.
- [ ] Add and run a browser-based end-to-end suite against the built frontend and a running backend.
- [ ] Add an automated accessibility scan (axe-core or equivalent) for each primary workspace section; triage all serious/critical findings.
- [ ] Keep screenshots, browser/version, viewport, run SHA, and test results as CI artifacts where possible.

## 2. Keyboard-only and screen-reader smoke test

Use Chrome or Edge on Windows. Do not use the mouse during this pass.

- [ ] Reload the page and press Tab. “Skip to main content” must appear visibly.
- [ ] Press Enter on the skip link. Focus must move to the main workspace.
- [ ] Use Tab / Shift+Tab to traverse every interactive element in logical order; no keyboard trap.
- [ ] Use Enter/Space to activate navigation and buttons. Focus indicator must remain visible.
- [ ] Confirm the current navigation item is announced as current and navigation has a useful accessible name.
- [ ] Trigger an API error (stop backend temporarily or use an invalid API URL); the error must be announced and readable.
- [ ] Trigger a successful request; the updated result/status must be announced without stealing focus.
- [ ] Inspect labels for all inputs, selects, checkboxes and textareas; placeholders do not replace labels.
- [ ] Check zoom at 200% and Windows display scaling; text and controls must not overlap or disappear.
- [ ] If a screen reader is available, test NVDA with Firefox or Chrome for headings, navigation, form labels, error announcements and result updates.

Record any defect with section, exact steps, expected/actual behavior, browser version, viewport and screenshot.

## 3. Responsive/browser matrix (manual, requires a running app)

Test at minimum:
- [ ] Desktop: 1440 × 900 and 1280 × 720.
- [ ] Tablet: 768 × 1024.
- [ ] Mobile: 390 × 844 and 320 × 720.
- [ ] Current Chrome/Edge and Firefox; Safari/iOS only if available.
- [ ] Portrait and landscape on a real mobile device if one is available.
- [ ] No horizontal page overflow, clipped navigation, inaccessible controls, or overlapping fixed elements.

## 4. End-to-end user journeys (must use a running API)

Start the backend using the repository's current setup instructions and run the frontend with its configured API base URL. Do not use fabricated responses.

- [ ] Initial load: health endpoint displays connected when healthy and unavailable when backend is stopped.
- [ ] Literature: submit a valid query; inspect provider response; verify empty/error/loading states; persistence checkbox behavior is truthful.
- [ ] Records: load list, filter by type, create a valid record, refresh list, verify it appears; test invalid JSON and backend validation errors.
- [ ] Knowledge: search with and without a query; inspect empty and server-error states.
- [ ] Mathematics: run each of the four supplied examples; alter a payload to cause a validation error; ensure results correspond to actual API responses.
- [ ] Controlled lab: submit a valid bounded plan; verify server rejection when authorization/configuration is absent; do not interpret UI access as proof of sandbox security.
- [ ] Rapidly switch sections during a slow request; stale responses must not overwrite the active section.
- [ ] Refresh the browser directly on the app entry URL; verify routing and API configuration.
- [ ] Inspect browser console and network tab for uncaught errors, failed assets, unexpected cross-origin requests, or sensitive data.

Capture date/time, commit SHA, API version, environment (local/staging/production), browser/OS, screenshots and pass/fail results. Redact tokens, cookies, personal data and secrets.

## 5. Production deployment verification (owner/operator required)

These cannot be completed from a source-code PR alone.

- [ ] Select and document a real deployment target and responsible operator.
- [ ] Configure production `VITE_API_BASE_URL`, HTTPS, CORS allowlist, secrets, health checks and logging without exposing secrets in frontend bundles.
- [ ] Deploy the exact reviewed commit to staging first; record deployment URL and commit SHA.
- [ ] Verify HTTPS certificate, redirects, cache headers, error pages, accessibility and all journeys above against staging.
- [ ] Test a clean browser profile and at least one non-developer device/network.
- [ ] Run rollback/redeploy rehearsal and confirm previous known-good release can be restored.
- [ ] Only then repeat smoke tests in production and record evidence.

## Evidence status

At the time this checklist was added, repository CI had passed for the previous frontend commit, but no evidence was available here of a live integrated environment, a production deployment, physical-device testing, or an independent assistive-technology audit. Those remain **unverified**, not passed.
