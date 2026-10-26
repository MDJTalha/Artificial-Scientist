# Phase 3 — Scholarly Literature Retrieval and Evidence Provenance

**Status:** Implementation acceptance checks passed on code commit `a3d139a56526ad0d512ab568c1dca71cba815b8a`. See the [passing GitHub Actions run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40264595989).  
**Branch:** \`phase-3-literature-retrieval\`  
**Objective:** retrieve bounded scholarly metadata from documented public APIs, normalize it into consistent source records, preserve how it was retrieved, and fail transparently when a provider cannot be used.

## Delivered capability

### Provider adapters

- **OpenAlex Works API:** topic search through the fixed \`https://api.openalex.org/works\` endpoint.
- **Crossref REST API:** bibliographic search through the fixed \`https://api.crossref.org/works\` endpoint.

Each adapter maps provider-specific responses into a common typed metadata representation. API keys and contact email are optional environment configuration; no keys or contact information are hard-coded. OpenAlex keys are sent in an authorization header. A configured contact email is included as the standard \`mailto\` parameter for polite API usage.

### Normalized metadata

Each result may include a title, authors, normalized DOI, exact publication date when present, publication year, an HTTP(S) landing URL, type classification, provider identifiers, retraction metadata where available, open-access-location metadata where available, citation counts where available, and the ID of a saved source record.

Missing metadata remains missing. The implementation does not fabricate dates, authors, DOI values, abstracts, licenses, or citation counts. The connectors retrieve bibliographic metadata only. They do not download full text or conclude that a paper's claims are true.

### Search API

\`POST /api/v1/literature/search\`

Example request:

\`\`\`json
{
  "query": "numerical methods for differential equations",
  "limit": 5,
  "providers": ["openalex", "crossref"],
  "persist_results": true
}
\`\`\`

- \`query\`: 3–500 characters after whitespace trimming.
- \`limit\`: 1–10 results requested per provider; the response is capped to the requested result limit after deduplication.
- \`providers\`: one or both of \`openalex\` and \`crossref\`; duplicate provider names are rejected.
- \`persist_results\`: when true (default), normalized metadata is stored as an append-only \`SourceRecord\`; when false, the search returns metadata without creating source records.

The response reports an overall \`ok\`, \`partial\`, or \`unavailable\` status, per-provider status and result counts, normalized results, and retrieval time. One provider failing does not discard successful results from the other provider.

### Duplicate handling and database migration

Schema version 2 introduces a \`source_identity\` table. DOI records from both providers share the same normalized DOI identity, so a paper found through both APIs or a later repeated search is linked to the existing stored source instead of duplicated. When a DOI is unavailable, a provider identifier or normalized HTTP(S) landing URL is used as the fallback identity.

Existing schema-v1 source rows are backfilled into the identity table during upgrade after checksum and schema validation. Duplicate identities in historical data map to the earliest source entry without rewriting or deleting historical records. The migration is transactional. A database declaring a schema version newer than the application remains rejected.

### Retrieval provenance

A saved source record retains the query, provider names and provider identifiers, retrieval timestamp, retrieval method, and connector name. It is explicitly marked \`unassessed\`. Provider identifiers help trace metadata to its source, while a SHA-256 checksum protects the stored record payload from undetected modification; neither is proof of scientific truth.

## Reliability and security controls

- Fixed provider hosts only; users cannot submit a URL for the server to fetch.
- Redirects are rejected to prevent unreviewed destination changes.
- Request timeouts and a 2 MiB decoded-response limit.
- JSON content type and structure validation.
- Rate limits, 5xx responses, malformed JSON, and unexpected redirects have distinct non-sensitive status messages.
- The provider error body is not returned to the caller.
- Provider responses are normalized into typed models; malformed individual records are skipped.
- Search results are deduplicated by normalized DOI when available.
- No API key or secret is written to source records or responses.
- External metadata is treated as untrusted and is never executed.
- Results explicitly warn that bibliographic metadata is not scientific verification.

## Configuration

Optional environment variables:

- \`OPENALEX_API_KEY\`: an API key for OpenAlex higher-throughput use; keyless basic search is supported.
- \`CROSSREF_CONTACT_EMAIL\`: contact email for the Crossref polite pool; when set, the value is sent as the API's documented \`mailto\` parameter.

Never commit credentials to GitHub. API availability, rate limits, field availability, and source coverage may change; the adapters classify provider errors rather than assuming every request will succeed.

## Automated verification

Tests use deterministic HTTP mocks, not live network calls. The suite covers:

- OpenAlex and Crossref field normalization.
- DOI normalization and cross-provider deduplication.
- Reuse of already persisted source records.
- Metadata-only searching without persistence.
- Rate limiting, outages, redirects, and malformed responses.
- Response size limits and malformed source rows.
- Partial and total provider failure status.
- Search endpoint validation and result contract.
- Source provenance retained on a saved record.
- Migration and re-indexing of schema-v1 source records to schema v2.

## Acceptance criteria

- [x] Current code commit passed Ruff and backend tests on Python 3.12 and 3.13.
- [x] Current code commit passed frontend TypeScript checks, tests, and production build.
- [x] Both provider adapters validate normalized results without needing real credentials.
- [x] Partial provider failure retains valid results from another provider.
- [x] Total provider failure is disclosed as unavailable, not as an empty successful search.
- [x] Duplicate DOI results map to one persisted source record.
- [x] Repeated searches reuse existing matching source records.
- [x] Source records preserve provider IDs, query context, connector name, and retrieval time.
- [x] Schema-v1 source rows migrate to schema v2 without losing the original record.
- [x] No full text is downloaded and no scientific claim is marked verified automatically.
- [x] CI results are recorded here.

## Verified CI result

- [Passing GitHub Actions run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40264595989) for code commit `a3d139a56526ad0d512ab568c1dca71cba815b8a`.
- Backend: Ruff passed; 33 tests passed on Python 3.12 and 33 tests passed on Python 3.13.
- Frontend: TypeScript type-check passed, 6 unit tests passed, and the production build completed.
- Tests are deterministic and use mocked provider responses; no live-provider reliability or metadata freshness claim is inferred from them.

The pull-request workflow will also validate the current branch and PR base configuration. Phase approval remains review/integration-gated.

## Not implemented

Phase 3 does not add full-text PDF/HTML ingestion, abstract extraction, systematic-review protocols, ranking learned from researcher feedback, claim-level entailment analysis, retraction feeds beyond metadata returned by OpenAlex, LLM calls, autonomous hypothesis generation, or computation. These belong to later phases and must be developed and tested separately.
