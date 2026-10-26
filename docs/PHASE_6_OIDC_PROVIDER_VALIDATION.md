# Phase 6 — Production OIDC Provider Validation and Key-Rotation Evidence

**Status: release gate defined; production provider not yet evidenced.**  
**Applies to:** the protected API's OIDC access-token trust boundary.

This document defines the evidence required before production identity can be accepted. Mocked unit tests prove selected code paths only; they do not establish that a real identity provider issues the expected token, publishes usable signing keys, rotates keys safely, or is configured correctly in the target deployment.

## 1. Provider selection is a required decision

The production identity provider has not been established by this document. The deployment owner must complete and approve the following record before a live test can be considered valid:

| Field | Required evidence |
|---|---|
| Provider and tenant/account | Named provider, tenant/account identifier, and accountable owner |
| Environment | Exact production-like environment used for verification |
| Issuer | Exact expected `iss` value copied from trusted provider metadata; trailing slash and case must match |
| API audience | Exact resource/API audience expected in access tokens |
| Discovery metadata | HTTPS discovery URL and archived, timestamped metadata response |
| JWKS endpoint | HTTPS `jwks_uri` from trusted discovery metadata; archive response headers and sanitized key metadata |
| Token type | Provider documentation confirming that the token presented is an access token for this API, not an ID token |
| Signing policy | Provider-supported signing algorithm and key type; current implementation accepts RS256 only |
| Key owner and rotation policy | Provider's published rotation/overlap policy, notification channel, and internal owner |
| Clock policy | Runtime clock synchronization and alerting evidence; validator currently uses zero clock leeway |
| Change approval | Reviewer, date, ticket/change reference, and approval outcome |

Do not copy client secrets, private keys, bearer tokens, refresh tokens, or other credentials into this document, tickets, test logs, or CI artifacts. Store secret values only in the approved secret manager and record secret identifiers/versions, not values.

## 2. Configuration and trust requirements

The current validator is configured with:

- `ARTIFICIAL_SCIENTIST_OIDC_ISSUER`: exact expected issuer.
- `ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE`: exact API audience.
- `ARTIFICIAL_SCIENTIST_OIDC_JWKS_URL`: HTTPS JWKS URL.

All values must be supplied in the target environment. Partial configuration must fail closed; the legacy shared API key must not bypass OIDC when OIDC is configured. The validator currently accepts RS256 only and requires `sub`, `iss`, `aud`, `iat`, and `exp`. Confirm that the selected provider's actual access tokens meet these assumptions before enabling traffic.

Additional deployment verification:

- The issuer and audience are sourced from the provider's trusted configuration, not request headers, query parameters, or untrusted token fields.
- Discovery metadata and JWKS are fetched over verified HTTPS; TLS certificate validation remains enabled.
- JWKS URL, issuer, and audience are reviewed and pinned through deployment configuration change control.
- Network egress from the API to the discovery/JWKS endpoint is explicit and monitored.
- Provider/API outage behavior is tested and fails closed; no stale or unknown key may be treated as trusted merely to preserve availability.
- Production-like tests exercise the same dependency versions and configuration loading path as the deployed service.
- Logs and CI artifacts contain no raw tokens, authorization headers, or secret material.

## 3. Key-rotation verification procedure

Run this procedure against the selected provider's production-like tenant, with a change window and named operator. Do not manually substitute arbitrary keys into production.

1. **Baseline:** capture the UTC timestamp, deployed commit SHA, dependency lock/version evidence, configured issuer/audience/JWKS URL (redacting sensitive query values if any), provider metadata version/ETag where available, and sanitized JWKS key metadata. Record each public key's `kid`, `kty`, `use`, `alg` if present, and fingerprint; never record private key material.
2. **Old-key positive test:** obtain a short-lived, provider-issued access token signed with the currently active key. Verify the API accepts it only for the configured issuer and audience and only while claims are valid. Do not store the token in the evidence package.
3. **Unknown-key negative test:** submit a safely controlled test token whose `kid` is not published by the provider. Verify authentication is rejected and no protected data is returned. Capture only status, sanitized error category, correlation ID, and timestamp.
4. **Rotation overlap:** follow the provider's documented rotation process in a non-production tenant or provider-supported test environment. Verify a token signed with the newly published key is accepted after JWKS refresh, and the old key behaves according to the provider's documented overlap period.
5. **Retired-key test:** after the documented retirement and cache/overlap interval, verify a token signed only by the retired key is rejected. If the provider retains old keys in JWKS, record the expected overlap semantics and verify rejection once the key is no longer trusted/usable.
6. **Cache and refresh behavior:** verify the actual `PyJWKClient`/JWKS cache behavior used by the installed PyJWT version. Confirm a new `kid` triggers the expected refresh, refresh failure does not authorize unknown keys, and the system recovers after the JWKS endpoint returns. Do not infer these outcomes from mocked tests alone.
7. **Outage behavior:** simulate an unavailable or malformed JWKS response in a controlled environment. Verify authentication fails closed, response details do not leak provider/network internals, and operational alerts fire.
8. **Repeatability:** repeat the rotation test after a fresh process start and after a normal deployment restart, so success does not depend on an accidental warm cache.
9. **Evidence review:** have a reviewer other than the operator compare results with the provider's documented rotation policy and sign the evidence record.

If the provider does not offer a safe way to exercise rotation, document the limitation and obtain an approved alternative evidence plan from the security owner. Do not claim rotation verified based only on provider marketing documentation or a local mock.

## 4. Required evidence package

Store the evidence in the approved restricted project/security evidence location. Link the location here; do not paste secrets or raw tokens into Git.

- [ ] Completed provider-selection record from section 1.
- [ ] Provider documentation/version and documented token + key-rotation semantics.
- [ ] Sanitized discovery metadata and JWKS snapshots from before, during, and after rotation.
- [ ] UTC timestamps, environment, deployment commit SHA, test run identifiers, and operator/reviewer identities.
- [ ] Results for old-key acceptance, new-key acceptance, unknown-key rejection, retired-key rejection, JWKS outage/failure, and restart/cache behavior.
- [ ] API status codes and sanitized correlation IDs for each scenario.
- [ ] Proof that wrong issuer, wrong audience, expired token, missing required claims, and unsupported algorithm are rejected in the deployed configuration.
- [ ] Evidence that partial OIDC configuration and legacy API-key fallback fail closed.
- [ ] Monitoring/alert evidence for JWKS failures and authentication-denial anomalies.
- [ ] Independent security review approval and documented exceptions.
- [ ] Approved evidence location/link: **not yet recorded**.
- [ ] Provider owner, reviewer, completion date, and sign-off: **not yet recorded**.

## 5. Pass/fail criteria

**Pass only when all of the following are true:**

- The provider is explicitly selected and the provider-specific token format matches the implementation.
- Issuer, audience, JWKS endpoint, algorithm, and claim requirements are verified against real provider-issued access tokens.
- Rotation evidence demonstrates the expected new-key acceptance, unknown/retired-key rejection, refresh behavior, and fail-closed outage behavior.
- Tests are run against the target production-like configuration and exact deployed commit.
- Evidence is reviewed and signed by an independent reviewer.
- No credential material is included in source control or the evidence package.

**Automatic fail / release block:**

- Provider, issuer, or audience is unknown or not approved.
- Only mocked tests or documentation review is available for rotation.
- Unknown keys or invalid tokens are accepted.
- Key refresh failure results in fail-open authentication.
- ID tokens are accepted as API access tokens without an explicitly approved and technically enforced design.
- Provider algorithm or token claims are incompatible with the configured validator.
- Production configuration, monitoring, evidence, or independent sign-off is missing.

## 6. Current implementation limitations to verify

The current validator uses PyJWT's `PyJWKClient` with a five-second timeout and JWKS-set caching. The exact cache lifetime, refresh-on-unknown-`kid` behavior, and installed-version behavior must be tested against the dependency version actually deployed. This document does not assert that those live behaviors have been verified.

The code's generic RS256/issuer/audience/claim checks do not implement a provider-specific login flow or establish provider tenancy. Provider-specific token semantics, access-token type, key rotation, deployment secrets, and operational monitoring remain separate acceptance requirements.

## 7. Release status

**Production OIDC acceptance: BLOCKED / NOT VERIFIED.**

This checklist defines the acceptance bar; it is not evidence that the provider has been selected or that rotation has been performed. Keep production multi-tenant exposure blocked until the evidence package is complete and independently approved.
