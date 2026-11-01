# Auth0 setup for the ASDS frontend

The ASDS frontend is a client-rendered React/Vite application. Authentication is handled in the browser with the official `@auth0/auth0-react` SDK and Auth0 Universal Login. No OAuth/OIDC protocol flow is implemented by ASDS itself, and no client secret belongs in this SPA.

## Local development

1. From the repository root, enter `frontend`.
2. Create `.env.local` from `.env.example`.
3. Confirm these values in `.env.local`:

   ```dotenv
   VITE_AUTH0_DOMAIN=asds-artificial-scientist.us.auth0.com
   VITE_AUTH0_CLIENT_ID=a0Jm8oh05S1V4hMOg0v2d84MNO56zJX8
   VITE_AUTH0_AUDIENCE=
   ```

4. Install dependencies and start Vite:

   ```bash
   npm install
   npm run dev
   ```

Vite is configured to bind port `5173` and use `strictPort`; it will fail rather than silently choosing another port. Open `http://localhost:5173`.

## Auth0 SPA application settings

For local development, the application must allow this exact origin:

- Allowed Callback URLs: `http://localhost:5173/`
- Allowed Logout URLs: `http://localhost:5173/`
- Allowed Web Origins: `http://localhost:5173` (origins do not include a path or trailing slash)

The SDK uses the current browser origin plus `/` for the callback and logout return URL, matching the configured trailing slash. Add each hosted HTTPS origin separately before enabling login on Vercel; do not assume a preview deployment origin is covered by the localhost entry.

## Backend API access is a separate configuration

The SPA can authenticate users through Universal Login without an API audience. To obtain a JWT access token intended for the ASDS FastAPI backend, first create/confirm an Auth0 API in the tenant and set `VITE_AUTH0_AUDIENCE` to that API's exact Identifier. The frontend requests an access token for that audience through `getAccessTokenSilently` from the Auth0 SDK.

Do not set an arbitrary audience or assume that an Auth0 login token is accepted by the backend. The backend must independently validate the Auth0 issuer, API audience, signature/JWKS and required permissions. Its existing Cognito-specific OIDC settings must be migrated and tested before protected backend features are considered integrated. Leave the audience blank until the Auth0 API Identifier is confirmed.

## Security notes

- The Client ID and Auth0 domain are public SPA configuration values.
- Never add an Auth0 Client Secret, Management API token, or other server credential to `VITE_*` variables.
- Do not commit `.env.local`; only the example template belongs in Git.
- This Vite app is client-rendered, not server-side rendered. Browser-only `window.location.origin` is therefore evaluated in the client entry point.
