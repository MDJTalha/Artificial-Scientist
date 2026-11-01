/**
 * Minimal browser OIDC Authorization Code + PKCE client.
 *
 * The browser is a public client: no client secret, refresh token or access token
 * is persisted. The API independently validates the access-token signature,
 * issuer, audience and tenant membership before protected requests are accepted.
 */

export interface OidcEnvironment {
  issuer?: string
  clientId?: string
  redirectUri?: string
  scopes?: string
}

export interface OidcClientConfiguration {
  issuer: string
  clientId: string
  redirectUri: string
  scopes: string[]
  production: boolean
}

export interface OidcTokenResult {
  accessToken: string
  expiresAt: number
}

interface DiscoveryDocument {
  issuer: string
  authorization_endpoint: string
  token_endpoint: string
  jwks_uri: string
  end_session_endpoint?: string
}

interface PendingAuthorization {
  state: string
  nonce: string
  verifier: string
  issuer: string
  clientId: string
  redirectUri: string
  createdAt: number
}

interface TokenResponse {
  access_token?: unknown
  token_type?: unknown
  expires_in?: unknown
  id_token?: unknown
}

interface JwtHeader {
  alg?: unknown
  kid?: unknown
  typ?: unknown
  crit?: unknown
}

interface JwtClaims {
  iss?: unknown
  aud?: unknown
  azp?: unknown
  exp?: unknown
  iat?: unknown
  nonce?: unknown
  sub?: unknown
}

const PENDING_KEY = "asds.oidc.pending.v1"
const MAX_PENDING_AGE_MS = 10 * 60 * 1000
const MAX_TOKEN_RESPONSE_BYTES = 64 * 1024

function isLoopback(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]"
}

function validateEndpoint(
  value: string,
  production: boolean,
  label: string,
): URL {
  let parsed: URL
  try {
    parsed = new URL(value)
  } catch {
    throw new Error(label + " must be an absolute HTTPS URL.")
  }
  const secure = parsed.protocol === "https:"
  const localDevelopment = !production && parsed.protocol === "http:" && isLoopback(parsed.hostname)
  if (
    (!secure && !localDevelopment) ||
    parsed.username ||
    parsed.password ||
    parsed.hash ||
    parsed.search ||
    !parsed.hostname
  ) {
    throw new Error(label + " must use HTTPS and must not contain credentials, query or fragment.")
  }
  return parsed
}

export function resolveOidcConfiguration(
  environment: OidcEnvironment,
  production: boolean,
  currentOrigin?: string,
): OidcClientConfiguration {
  const issuerValue = environment.issuer?.trim()
  const clientId = environment.clientId?.trim()
  const redirectValue = environment.redirectUri?.trim()
  if (!issuerValue || !clientId || !redirectValue) {
    throw new Error(
      "OIDC is not configured. Set VITE_OIDC_ISSUER, VITE_OIDC_CLIENT_ID and VITE_OIDC_REDIRECT_URI.",
    )
  }
  if (clientId.length > 512 || /[\u0000-\u001f]/.test(clientId)) {
    throw new Error("OIDC client ID is invalid.")
  }
  const issuer = validateEndpoint(issuerValue, production, "OIDC issuer")
  const redirectUri = validateEndpoint(redirectValue, production, "OIDC redirect URI")
  if (redirectUri.search || redirectUri.hash) {
    throw new Error("OIDC redirect URI must not include a query or fragment.")
  }
  if (production && currentOrigin && redirectUri.origin !== currentOrigin) {
    throw new Error("Production OIDC redirect URI must use the current application origin.")
  }
  const scopes = (environment.scopes?.trim() || "openid profile email")
    .split(/\s+/)
    .filter(Boolean)
  if (!scopes.includes("openid") || scopes.length > 20) {
    throw new Error("OIDC scopes must include openid and contain no more than 20 entries.")
  }
  return {
    issuer: issuer.toString(),
    clientId,
    redirectUri: redirectUri.toString(),
    scopes: [...new Set(scopes)],
    production,
  }
}

function encodeBase64Url(bytes: Uint8Array): string {
  let binary = ""
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "")
}

function decodeBase64Url(value: string): Uint8Array {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/")
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4)
  const binary = atob(padded)
  return Uint8Array.from(binary, (character) => character.charCodeAt(0))
}

function decodeJsonSegment<T>(segment: string): T {
  const decoded = new TextDecoder().decode(decodeBase64Url(segment))
  return JSON.parse(decoded) as T
}

function randomValue(length = 32): string {
  const bytes = new Uint8Array(length)
  crypto.getRandomValues(bytes)
  return encodeBase64Url(bytes)
}

async function createCodeChallenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier))
  return encodeBase64Url(new Uint8Array(digest))
}

function discoveryUrl(issuer: string): string {
  return issuer.replace(/\/+$/, "") + "/.well-known/openid-configuration"
}

async function loadDiscovery(config: OidcClientConfiguration): Promise<DiscoveryDocument> {
  const response = await fetch(discoveryUrl(config.issuer), {
    method: "GET",
    headers: { Accept: "application/json" },
    credentials: "omit",
    cache: "no-store",
    redirect: "error",
  })
  if (!response.ok) throw new Error("OIDC discovery failed with HTTP " + response.status + ".")
  const document = (await response.json()) as Partial<DiscoveryDocument>
  if (document.issuer !== config.issuer) {
    throw new Error("OIDC discovery issuer does not match the configured issuer.")
  }
  if (
    typeof document.authorization_endpoint !== "string" ||
    typeof document.token_endpoint !== "string" ||
    typeof document.jwks_uri !== "string"
  ) {
    throw new Error("OIDC discovery document is missing a required endpoint.")
  }
  validateEndpoint(document.authorization_endpoint, config.production, "OIDC authorization endpoint")
  validateEndpoint(document.token_endpoint, config.production, "OIDC token endpoint")
  validateEndpoint(document.jwks_uri, config.production, "OIDC JWKS URI")
  return document as DiscoveryDocument
}

export async function beginOidcLogin(
  config: OidcClientConfiguration,
): Promise<void> {
  const discovery = await loadDiscovery(config)
  const pending: PendingAuthorization = {
    state: randomValue(32),
    nonce: randomValue(32),
    verifier: randomValue(64),
    issuer: config.issuer,
    clientId: config.clientId,
    redirectUri: config.redirectUri,
    createdAt: Date.now(),
  }
  sessionStorage.setItem(PENDING_KEY, JSON.stringify(pending))
  const challenge = await createCodeChallenge(pending.verifier)
  const authorizationUrl = new URL(discovery.authorization_endpoint)
  authorizationUrl.searchParams.set("client_id", config.clientId)
  authorizationUrl.searchParams.set("redirect_uri", config.redirectUri)
  authorizationUrl.searchParams.set("response_type", "code")
  authorizationUrl.searchParams.set("scope", config.scopes.join(" "))
  authorizationUrl.searchParams.set("state", pending.state)
  authorizationUrl.searchParams.set("nonce", pending.nonce)
  authorizationUrl.searchParams.set("code_challenge", challenge)
  authorizationUrl.searchParams.set("code_challenge_method", "S256")
  window.location.assign(authorizationUrl.toString())
}

async function validateIdToken(
  token: string,
  expectedNonce: string,
  config: OidcClientConfiguration,
  jwksUri: string,
): Promise<void> {
  const segments = token.split(".")
  if (segments.length !== 3 || segments.some((segment) => !segment)) {
    throw new Error("OIDC provider returned a malformed ID token.")
  }
  const header = decodeJsonSegment<JwtHeader>(segments[0])
  const claims = decodeJsonSegment<JwtClaims>(segments[1])
  if (
    header.alg !== "RS256" ||
    typeof header.kid !== "string" ||
    header.crit !== undefined
  ) {
    throw new Error("ID token must use an uncritical RS256 signing key.")
  }
  if (
    claims.iss !== config.issuer ||
    typeof claims.sub !== "string" ||
    !claims.sub.trim() ||
    claims.nonce !== expectedNonce ||
    typeof claims.exp !== "number" ||
    claims.exp <= Math.floor(Date.now() / 1000) ||
    typeof claims.iat !== "number" ||
    claims.iat > Math.floor(Date.now() / 1000) + 60
  ) {
    throw new Error("ID token claims failed issuer, subject, nonce or time validation.")
  }
  const audiences = Array.isArray(claims.aud) ? claims.aud : [claims.aud]
  if (!audiences.includes(config.clientId)) {
    throw new Error("ID token audience does not include this OIDC client.")
  }
  if (audiences.length > 1 && claims.azp !== config.clientId) {
    throw new Error("ID token authorized party is invalid.")
  }

  const jwksResponse = await fetch(jwksUri, {
    method: "GET",
    headers: { Accept: "application/json" },
    credentials: "omit",
    cache: "no-store",
    redirect: "error",
  })
  if (!jwksResponse.ok) {
    throw new Error("OIDC signing-key retrieval failed with HTTP " + jwksResponse.status + ".")
  }
  const jwksPayload = (await jwksResponse.json()) as { keys?: unknown }
  if (!Array.isArray(jwksPayload.keys) || jwksPayload.keys.length > 100) {
    throw new Error("OIDC JWKS response is invalid.")
  }
  const jwk = jwksPayload.keys.find((item) => {
    if (typeof item !== "object" || item === null) return false
    const key = item as Record<string, unknown>
    return (
      key.kid === header.kid &&
      key.kty === "RSA" &&
      (key.use === undefined || key.use === "sig") &&
      (key.alg === undefined || key.alg === "RS256")
    )
  }) as JsonWebKey | undefined
  if (!jwk) throw new Error("No matching OIDC signing key was found.")

  const key = await crypto.subtle.importKey(
    "jwk",
    jwk,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"],
  )
  const validSignature = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5",
    key,
    decodeBase64Url(segments[2]),
    new TextEncoder().encode(segments[0] + "." + segments[1]),
  )
  if (!validSignature) throw new Error("ID token signature validation failed.")
}

export async function completeOidcCallback(
  search: string,
  config: OidcClientConfiguration,
): Promise<OidcTokenResult | null> {
  const parameters = new URLSearchParams(search)
  const code = parameters.get("code")
  const state = parameters.get("state")
  const providerError = parameters.get("error")
  if (!code && !providerError) return null
  if (providerError) {
    const safeDescription = parameters.get("error_description")?.slice(0, 300)
    sessionStorage.removeItem(PENDING_KEY)
    throw new Error(
      "OIDC sign-in was not completed: " + providerError +
      (safeDescription ? " — " + safeDescription : ""),
    )
  }
  if (!code || code.length > 4096 || !state || state.length > 512) {
    sessionStorage.removeItem(PENDING_KEY)
    throw new Error("OIDC callback is missing a valid authorization code or state.")
  }

  let pending: PendingAuthorization | null = null
  try {
    const raw = sessionStorage.getItem(PENDING_KEY)
    pending = raw ? (JSON.parse(raw) as PendingAuthorization) : null
  } catch {
    pending = null
  }
  sessionStorage.removeItem(PENDING_KEY)
  if (
    !pending ||
    pending.state !== state ||
    pending.issuer !== config.issuer ||
    pending.clientId !== config.clientId ||
    pending.redirectUri !== config.redirectUri ||
    Date.now() - pending.createdAt > MAX_PENDING_AGE_MS ||
    Date.now() < pending.createdAt
  ) {
    throw new Error("OIDC callback state is missing, expired or does not match this sign-in.")
  }

  const discovery = await loadDiscovery(config)
  const form = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: config.clientId,
    code,
    redirect_uri: config.redirectUri,
    code_verifier: pending.verifier,
  })
  const tokenResponse = await fetch(discovery.token_endpoint, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
    credentials: "omit",
    cache: "no-store",
    redirect: "error",
  })
  const responseText = await tokenResponse.text()
  if (responseText.length > MAX_TOKEN_RESPONSE_BYTES) {
    throw new Error("OIDC token response exceeds the accepted size.")
  }
  let tokenPayload: TokenResponse
  try {
    tokenPayload = JSON.parse(responseText) as TokenResponse
  } catch {
    throw new Error("OIDC token endpoint returned malformed JSON.")
  }
  if (!tokenResponse.ok) {
    throw new Error("OIDC code exchange failed with HTTP " + tokenResponse.status + ".")
  }
  if (
    typeof tokenPayload.access_token !== "string" ||
    !tokenPayload.access_token ||
    tokenPayload.access_token.length > 16_384 ||
    typeof tokenPayload.id_token !== "string" ||
    typeof tokenPayload.expires_in !== "number" ||
    !Number.isFinite(tokenPayload.expires_in) ||
    tokenPayload.expires_in < 30 ||
    tokenPayload.expires_in > 86_400 ||
    typeof tokenPayload.token_type !== "string" ||
    tokenPayload.token_type.toLowerCase() !== "bearer"
  ) {
    throw new Error("OIDC token response is missing a valid access token, ID token or expiry.")
  }

  await validateIdToken(tokenPayload.id_token, pending.nonce, config, discovery.jwks_uri)
  return {
    accessToken: tokenPayload.access_token,
    expiresAt: Date.now() + tokenPayload.expires_in * 1000,
  }
}

export function oidcConfigurationFromVite(
  production: boolean,
  currentOrigin: string,
  currentPath: string,
): OidcClientConfiguration {
  return resolveOidcConfiguration(
    {
      issuer: import.meta.env.VITE_OIDC_ISSUER,
      clientId: import.meta.env.VITE_OIDC_CLIENT_ID,
      redirectUri:
        import.meta.env.VITE_OIDC_REDIRECT_URI ||
        currentOrigin + currentPath,
      scopes: import.meta.env.VITE_OIDC_SCOPES,
    },
    production,
    currentOrigin,
  )
}

export function oidcConfiguredFromVite(): boolean {
  return Boolean(
    import.meta.env.VITE_OIDC_ISSUER?.trim() &&
    import.meta.env.VITE_OIDC_CLIENT_ID?.trim() &&
    (import.meta.env.VITE_OIDC_REDIRECT_URI?.trim() || window.location.origin),
  )
}
