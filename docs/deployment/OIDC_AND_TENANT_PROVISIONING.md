# OIDC and Tenant Provisioning

## Trust model

ASDS uses a public browser client with OIDC Authorization Code + PKCE (S256). It does not use a client secret in the browser, does not request offline refresh tokens, and keeps access tokens in JavaScript memory only. A reload requires a new login. Local sign-out clears the ASDS browser session; the identity provider may retain its own SSO session.

The browser validates the ID-token signature using the issuer's JWKS and validates issuer, audience, expiry, issue time and nonce. The browser then calls GET /api/v1/auth/session with the access token. The API independently validates the RS256 access token against the configured issuer, API audience and JWKS URI.

The API resolves the trusted issuer/subject pair to a stable opaque principal. It returns active memberships from the server-side directory. The browser must select one of those memberships; every protected API request then carries the bearer token and selected tenant ID. The API independently checks that the principal belongs to the tenant and has the role required for that action.

Tenant IDs, role names, reviewer labels and authorization decisions supplied by the browser are never accepted as proof of identity or membership.

## Required frontend configuration

Set these build-time variables in Vercel or the selected frontend host:

| Variable | Meaning |
|---|---|
| VITE_API_BASE_URL | HTTPS URL of the separately deployed ASDS API |
| VITE_OIDC_ISSUER | Exact issuer identifier from the provider discovery document |
| VITE_OIDC_CLIENT_ID | Public SPA client ID; no client secret |
| VITE_OIDC_REDIRECT_URI | Exact registered HTTPS callback URL |
| VITE_OIDC_SCOPES | Space-separated scopes; include openid and any provider-specific API scope |
| VITE_OIDC_RESOURCE | Optional RFC 8707 API resource identifier |

The OIDC provider must allow Authorization Code with PKCE (S256) for a public browser client, the exact redirect URI, token-endpoint CORS from the frontend origin, and a signed ID token using RS256. If the API requires a provider-specific audience/resource request, configure VITE_OIDC_RESOURCE or the provider's documented API scope.

## Required backend configuration

Set runtime variables only on the API host:

- ARTIFICIAL_SCIENTIST_ENV=production
- ARTIFICIAL_SCIENTIST_ALLOWED_ORIGINS=https://<frontend-host>
- ARTIFICIAL_SCIENTIST_OIDC_ISSUER=<exact issuer>
- ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE=<API access-token audience>
- ARTIFICIAL_SCIENTIST_OIDC_JWKS_URL=<HTTPS JWKS URI>
- ARTIFICIAL_SCIENTIST_DB_PATH=<durable database path>

Use the exact issuer identifier, including its trailing slash if the provider publishes one. The ID-token audience is the SPA client ID; the access-token audience must equal ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE. Confirm the provider issues JWT access tokens signed with RS256, not opaque access tokens.

## Operator bootstrap

The first login creates a principal record but grants no tenant membership. The trusted operator must run backend/scripts/provision_tenant.py using the same database path as the API. The tool prompts for the OIDC subject with hidden input and creates a tenant-scoped role assignment. It does not create a global superadmin role and it does not expose an API for self-service privilege escalation.

Revoke membership using a reviewed operator procedure; never grant the first login tenant-admin access automatically.

## Required validation before enabling real users

1. Register the exact callback URI and verify discovery issuer equality.
2. Test valid/expired tokens, wrong issuer/audience, invalid ID-token signature, nonce mismatch, wrong state, unknown signing key and JWKS rotation.
3. Test a valid access token with no tenant membership; the API must return an authenticated session with an empty membership list.
4. Provision a user into two tenants with different roles and confirm the UI requires an explicit tenant choice.
5. Attempt to change the tenant header to another tenant without membership; protected API access must fail.
6. Test membership revocation and confirm the next API request is denied.
7. Verify an auditor cannot write, a viewer cannot mutate, and a researcher cannot administer tenant membership.
8. Confirm that the browser stores no access token, ID token, refresh token or client secret in localStorage/sessionStorage, browser URLs, logs or analytics.
9. Verify expiry clears the in-memory browser session and requires re-authentication.
10. Record the identity provider, client ID, API audience, JWKS key ID, test timestamps and sanitized outcomes without retaining tokens.

This implementation supplies the provider-neutral application flow and server-side membership lookup. It is not evidence that an actual provider has been configured, its CORS settings are correct, users have been provisioned, or the complete live OIDC protocol has been accepted.
