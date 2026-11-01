import { describe, expect, it } from 'vitest'

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
