import { afterEach, describe, expect, it, vi } from 'vitest'

import { resolveOidcConfiguration } from './oidc'

describe('OIDC browser configuration', () => {
  const productionOrigin = 'https://research.example.test'

  it('requires an issuer, public client ID and redirect URI', () => {
    expect(() => resolveOidcConfiguration({}, true, productionOrigin)).toThrow(
      /VITE_OIDC_ISSUER/,
    )
  })

  it('accepts a same-origin HTTPS public-client configuration', () => {
    const config = resolveOidcConfiguration(
      {
        issuer: 'https://identity.example.test/tenant-a/',
        clientId: 'asds-spa',
        redirectUri: productionOrigin + '/',
        scopes: 'openid profile email',
      },
      true,
      productionOrigin,
    )
    expect(config.issuer).toBe('https://identity.example.test/tenant-a/')
    expect(config.clientId).toBe('asds-spa')
    expect(config.scopes).toEqual(['openid', 'profile', 'email'])
  })

  it('rejects HTTP identity providers in production', () => {
    expect(() =>
      resolveOidcConfiguration(
        {
          issuer: 'http://identity.example.test',
          clientId: 'asds-spa',
          redirectUri: productionOrigin + '/',
        },
        true,
        productionOrigin,
      ),
    ).toThrow(/HTTPS/)
  })

  it('rejects redirect URIs on a different production origin', () => {
    expect(() =>
      resolveOidcConfiguration(
        {
          issuer: 'https://identity.example.test',
          clientId: 'asds-spa',
          redirectUri: 'https://attacker.example/callback',
        },
        true,
        productionOrigin,
      ),
    ).toThrow(/current application origin/)
  })

  it('allows loopback HTTP issuer and callback only in local development', () => {
    const config = resolveOidcConfiguration(
      {
        issuer: 'http://127.0.0.1:9000',
        clientId: 'asds-dev-spa',
        redirectUri: 'http://127.0.0.1:5173/',
      },
      false,
    )
    expect(config.production).toBe(false)
  })

  it('requires the openid scope and rejects excessive scope lists', () => {
    expect(() =>
      resolveOidcConfiguration(
        {
          issuer: 'https://identity.example.test',
          clientId: 'asds-spa',
          redirectUri: productionOrigin + '/',
          scopes: 'profile email',
        },
        true,
        productionOrigin,
      ),
    ).toThrow(/include openid/)
  })

  it('rejects redirect URIs containing a query or fragment', () => {
    expect(() =>
      resolveOidcConfiguration(
        {
          issuer: 'https://identity.example.test',
          clientId: 'asds-spa',
          redirectUri: productionOrigin + '/?return=unsafe',
        },
        true,
        productionOrigin,
      ),
    ).toThrow(/query or fragment/)
  })
})


describe('OIDC Authorization Code + PKCE callback', () => {
  function encode(value: string | Uint8Array): string {
    const bytes = typeof value === 'string' ? new TextEncoder().encode(value) : value
    let binary = ''
    for (const byte of bytes) binary += String.fromCharCode(byte)
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
  }

  function storage() {
    const values = new Map<string, string>()
    return {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
      clear: () => values.clear(),
    }
  }

  it('uses PKCE, checks state and verifies the RS256 ID-token signature', async () => {
    const signingKeys = await crypto.subtle.generateKey(
      {
        name: 'RSASSA-PKCS1-v1_5',
        modulusLength: 2048,
        publicExponent: new Uint8Array([1, 0, 1]),
        hash: 'SHA-256',
      },
      true,
      ['sign', 'verify'],
    )
    const publicJwk = await crypto.subtle.exportKey('jwk', signingKeys.publicKey)
    const jwk = {
      ...publicJwk,
      kid: 'asds-test-key',
      alg: 'RS256',
      use: 'sig',
    }
    const config = resolveOidcConfiguration(
      {
        issuer: 'https://identity.example.test/',
        clientId: 'asds-spa',
        redirectUri: 'https://research.example.test/',
      },
      true,
      'https://research.example.test',
    )
    const store = storage()
    const assign = vi.fn()
    const fetchMock = vi.fn<typeof fetch>()
    vi.stubGlobal('sessionStorage', store)
    vi.stubGlobal('window', { location: { assign } })
    vi.stubGlobal('fetch', fetchMock)

    const discovery = {
      issuer: config.issuer,
      authorization_endpoint: 'https://identity.example.test/authorize',
      token_endpoint: 'https://identity.example.test/token',
      jwks_uri: 'https://identity.example.test/jwks',
    }
    fetchMock
      .mockResolvedValueOnce(
        new Response(JSON.stringify(discovery), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      )

    const { beginOidcLogin, completeOidcCallback } = await import('./oidc')
    await beginOidcLogin(config)
    expect(assign).toHaveBeenCalledTimes(1)
    const authorizationUrl = new URL(assign.mock.calls[0]?.[0] as string)
    expect(authorizationUrl.searchParams.get('response_type')).toBe('code')
    expect(authorizationUrl.searchParams.get('code_challenge_method')).toBe('S256')
    expect(authorizationUrl.searchParams.get('code_challenge')).toBeTruthy()
    const pending = JSON.parse(store.getItem('asds.oidc.pending.v1') ?? '{}') as {
      nonce: string
      state: string
      verifier: string
    }
    expect(pending.verifier.length).toBeGreaterThanOrEqual(64)

    const now = Math.floor(Date.now() / 1000)
    const header = encode(JSON.stringify({ alg: 'RS256', kid: 'asds-test-key', typ: 'JWT' }))
    const payload = encode(JSON.stringify({
      iss: config.issuer,
      sub: 'scientist-01',
      aud: config.clientId,
      exp: now + 300,
      iat: now,
      nonce: pending.nonce,
    }))
    const signedData = header + '.' + payload
    const signature = await crypto.subtle.sign(
      'RSASSA-PKCS1-v1_5',
      signingKeys.privateKey,
      new TextEncoder().encode(signedData),
    )
    const idToken = signedData + '.' + encode(new Uint8Array(signature))

    fetchMock
      .mockResolvedValueOnce(
        new Response(JSON.stringify(discovery), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({
          access_token: 'api-signed-access-token',
          token_type: 'Bearer',
          expires_in: 300,
          id_token: idToken,
        }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ keys: [jwk] }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      )

    const result = await completeOidcCallback(
      '?code=one-time-code&state=' + encodeURIComponent(pending.state),
      config,
    )
    expect(result?.accessToken).toBe('api-signed-access-token')
    expect(result?.expiresAt).toBeGreaterThan(Date.now())
    expect(store.getItem('asds.oidc.pending.v1')).toBeNull()
    expect(fetchMock.mock.calls[2]?.[1]?.body).toContain('code_verifier=')
  })

  it('rejects a callback with mismatched state before exchanging the code', async () => {
    const config = resolveOidcConfiguration(
      {
        issuer: 'https://identity.example.test/',
        clientId: 'asds-spa',
        redirectUri: 'https://research.example.test/',
      },
      true,
      'https://research.example.test',
    )
    const store = storage()
    store.setItem('asds.oidc.pending.v1', JSON.stringify({
      state: 'trusted-state',
      nonce: 'trusted-nonce',
      verifier: 'a'.repeat(64),
      issuer: config.issuer,
      clientId: config.clientId,
      redirectUri: config.redirectUri,
      createdAt: Date.now(),
    }))
    const fetchMock = vi.fn<typeof fetch>()
    vi.stubGlobal('sessionStorage', store)
    vi.stubGlobal('fetch', fetchMock)
    const { completeOidcCallback } = await import('./oidc')

    await expect(
      completeOidcCallback('?code=attacker-code&state=attacker-state', config),
    ).rejects.toThrow(/state is missing, expired or does not match/)
    expect(fetchMock).not.toHaveBeenCalled()
    expect(store.getItem('asds.oidc.pending.v1')).toBeNull()
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})
