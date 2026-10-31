# Vercel Frontend Deployment

## Scope

Vercel is the deployment target for the ASDS React/Vite frontend. The FastAPI backend, persistent database, OIDC/JWKS integration, and laboratory sandbox remain separate production services unless independently validated for a compatible hosting model.

Vercel's current documentation supports Vite deployments from source and recommends configuring the application root, build command, and output directory for monorepos. See the official Vercel deployment documentation before the first production deployment.

## Repository configuration

The frontend contains `frontend/vercel.json` with:

- framework: Vite
- install command: `npm install --no-audit --no-fund`
- build command: `npm run build`
- output directory: `dist`
- baseline browser security headers

When importing the repository into Vercel, set the **Root Directory** to `frontend`.

## Required production environment variable

The frontend reads:

`VITE_API_BASE_URL`

Example:

`VITE_API_BASE_URL=https://api.<production-domain>`

Do not put private credentials, OIDC client secrets, database credentials, signing keys, or sandbox credentials in `VITE_*` variables. Vite exposes `VITE_*` values to browser code.

The development example remains:

`VITE_API_BASE_URL=http://127.0.0.1:8000`

Production must use the real HTTPS API origin.

## Deployment procedure

1. Verify the release branch CI is green.
2. Review the exact commit intended for deployment.
3. Import `MDJTalha/Artificial-Scientist` into Vercel.
4. Set Root Directory to `frontend`.
5. Confirm Vite is detected.
6. Configure `VITE_API_BASE_URL` separately for Preview and Production.
7. Deploy a Preview first.
8. Verify the frontend build and browser console.
9. Verify API connectivity over HTTPS.
10. Validate authentication, authorization, tenant isolation and release-gate behavior against the actual backend.
11. Only after acceptance, promote the intended release to Production.

## Production boundary

A successful Vercel deployment proves frontend deployment/build correctness only. It does not certify:

- the backend;
- the database;
- the laboratory sandbox;
- the production operating system;
- the OIDC provider;
- backup/restore;
- independent security review;
- scientific validity.

Those remain separate release evidence gates.

## Rollback

Keep the previous known-good Vercel deployment available until production smoke tests and release evidence have been accepted. If the new deployment fails acceptance, roll back to the last verified deployment and investigate before retrying.

## Done-when

The Vercel work is complete only when:

- Preview deployment succeeds;
- Production build succeeds;
- production API URL is configured without exposing secrets;
- browser security headers are present;
- frontend-to-API health check succeeds;
- authentication is verified;
- critical UI workflows pass;
- backend/sandbox external gates remain correctly represented in the release evidence matrix;
- the deployed commit is recorded in release evidence.
