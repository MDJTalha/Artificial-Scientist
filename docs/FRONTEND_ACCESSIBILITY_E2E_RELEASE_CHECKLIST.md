# Frontend Accessibility, Integrated Journey, and Release Verification

This checklist separates repository/CI evidence from checks that require a real browser, API process, deployment, or human review. Do not mark a manual check complete from a successful TypeScript build alone.

## 1. Automated checks (GitHub Actions)

- [x] Frontend typecheck, unit tests, and production build passed on commit `3c20312d4ba55611fc1886a722449419eb50f028` (re-run CI after any subsequent changes).
- [x] Browser-based Playwright end-to-end suite runs against the built frontend; selected API responses are mocked, so this is not a live-backend integration test.
- [x] axe-core accessibility scans run across the six primary workspace sections; no serious/critical violations remained on commit `3c20312d4ba55611fc1886a722449419eb50f028`.
- [x] Playwright failure screenshots/traces and test-results are configured for upload as a 14-day CI artifact; successful-run evidence is limited to the CI logs and test summary.

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

## 4. Browser E2E checks versus integrated API checks

The automated Playwright suite currently intercepts selected API requests with deterministic fixtures. It verifies browser interactions, keyboard access, error rendering, and serious/critical axe findings; **it does not prove that the frontend works against a running backend**. Keep these as separate evidence categories.

### Windows Chrome manual integrated run (requires a running API)

Once the repository is checked out on the Windows PC, open two PowerShell terminals from the repository root. In terminal 1, follow `backend/README.md` to create/activate the virtual environment, install `backend` with its dev extras, configure any required environment variables, and start the API. In terminal 2:

```powershell
cd frontend
npm install
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000'
npm run dev
```

Open the local Vite URL printed in the terminal in Chrome. Use the API URL actually configured by the backend if it differs from `127.0.0.1:8000`. Do not paste secrets into screenshots or chat.

Start the backend using the repository's current setup instructions and run the frontend with its configured API base URL. Do not use fabricated responses for the integrated manual checks.

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

Automated repository CI passed on commit `3c20312d4ba55611fc1886a722449419eb50f028` (frontend checks and backend tests on Python 3.12 and 3.13). Any subsequent commit must pass CI again. No evidence is available here of a live integrated environment, a production deployment, physical-device testing, or an independent assistive-technology audit. Those remain **unverified**, not passed.
