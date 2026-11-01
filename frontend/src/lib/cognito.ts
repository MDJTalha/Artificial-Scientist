import { setApiAccessToken } from './api';

type CognitoTokenResponse = {
  access_token?: string;
  token_type?: string;
  expires_in?: number;
  error?: string;
  error_description?: string;
};

const env = import.meta.env;
const domain = (env.VITE_COGNITO_DOMAIN ?? '').trim().replace(/\/+$/, '');
const clientId = (env.VITE_COGNITO_CLIENT_ID ?? '').trim();
const redirectUri = (env.VITE_COGNITO_REDIRECT_URI ?? '').trim() || `${window.location.origin}/auth/callback`;
const logoutUri = (env.VITE_COGNITO_LOGOUT_URI ?? '').trim() || window.location.origin;
const scopes = (env.VITE_COGNITO_SCOPES ?? 'openid email profile asds-api/access').trim();

export const cognitoConfigured = Boolean(domain && clientId && redirectUri.startsWith('https://') && logoutUri.startsWith('https://'));

function base64Url(bytes: Uint8Array): string {
  let binary = '';
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function randomToken(size = 32): string {
  return base64Url(crypto.getRandomValues(new Uint8Array(size)));
}

async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
  return base64Url(new Uint8Array(digest));
}

export async function beginCognitoLogin(): Promise<void> {
  if (!cognitoConfigured) throw new Error('Cognito frontend configuration is incomplete. Set the VITE_COGNITO_* variables.');
  const state = randomToken();
  const verifier = randomToken(48);
  sessionStorage.setItem('asds.cognito.state', state);
  sessionStorage.setItem('asds.cognito.verifier', verifier);
  const challenge = await sha256(verifier);
  const url = new URL(`${domain}/oauth2/authorize`);
  url.search = new URLSearchParams({
    client_id: clientId,
    response_type: 'code',
    scope: scopes,
    redirect_uri: redirectUri,
    state,
    code_challenge_method: 'S256',
    code_challenge: challenge,
  }).toString();
  window.location.assign(url.toString());
}

export async function completeCognitoCallback(): Promise<boolean> {
  const current = new URL(window.location.href);
  const code = current.searchParams.get('code');
  const providerError = current.searchParams.get('error');
  if (providerError) {
    const description = current.searchParams.get('error_description') ?? providerError;
    window.history.replaceState({}, document.title, current.pathname);
    throw new Error(`Cognito sign-in failed: ${description}`);
  }
  if (!code) return false;

  const expectedState = sessionStorage.getItem('asds.cognito.state');
  const verifier = sessionStorage.getItem('asds.cognito.verifier');
  const receivedState = current.searchParams.get('state');
  sessionStorage.removeItem('asds.cognito.state');
  sessionStorage.removeItem('asds.cognito.verifier');
  if (!expectedState || !verifier || !receivedState || receivedState !== expectedState) {
    window.history.replaceState({}, document.title, current.pathname);
    throw new Error('Cognito sign-in state validation failed. Please sign in again.');
  }

  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: clientId,
    code,
    redirect_uri: redirectUri,
    code_verifier: verifier,
  });
  const response = await fetch(`${domain}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded', Accept: 'application/json' },
    body,
    credentials: 'omit',
  });
  const result = await response.json() as CognitoTokenResponse;
  window.history.replaceState({}, document.title, current.pathname);
  if (!response.ok || !result.access_token || result.token_type?.toLowerCase() !== 'bearer') {
    throw new Error(result.error_description ?? result.error ?? 'Cognito token exchange failed.');
  }
  setApiAccessToken(result.access_token);
  return true;
}

export function signOutCognito(): void {
  setApiAccessToken(null);
  const url = new URL(`${domain}/logout`);
  url.search = new URLSearchParams({
    client_id: clientId,
    logout_uri: logoutUri,
  }).toString();
  window.location.assign(url.toString());
}
