import { describe, expect, it } from 'vitest'

import { getStatusPresentation, resolveApiBaseUrl } from './status'

describe('getStatusPresentation', () => {
  it('describes the initial connection check', () => {
    expect(getStatusPresentation('checking').label).toBe('Checking connection')
  })

  it('reports a successful API connection without overstating readiness', () => {
    expect(getStatusPresentation('connected')).toEqual({
      label: 'API connected',
      detail: 'The API health endpoint responded successfully.',
    })
  })

  it('explains what to do when the backend is unavailable', () => {
    expect(getStatusPresentation('unavailable').detail).toContain('configured API endpoint')
  })
})


describe('isHealthyResponse', () => {
  it('accepts a valid healthy response', async () => {
    const { isHealthyResponse } = await import('./status')
    expect(
      isHealthyResponse({
        status: 'ok',
        service: 'Artificial Scientist',
        version: '0.1.0',
      }),
    ).toBe(true)
  })

  it('rejects a response that reports an unhealthy status', async () => {
    const { isHealthyResponse } = await import('./status')
    expect(
      isHealthyResponse({
        status: 'degraded',
        service: 'Artificial Scientist',
        version: '0.1.0',
      }),
    ).toBe(false)
  })

  it('rejects malformed response payloads', async () => {
    const { isHealthyResponse } = await import('./status')
    expect(isHealthyResponse({ status: 'ok', service: 'Artificial Scientist' })).toBe(false)
    expect(isHealthyResponse(null)).toBe(false)
  })
})


describe('resolveApiBaseUrl', () => {
  it('uses the local development default only outside production', () => {
    expect(resolveApiBaseUrl(undefined, false)).toEqual({
      baseUrl: 'http://127.0.0.1:8000',
      error: null,
    })
  })

  it('fails closed when production has no API endpoint configured', () => {
    expect(resolveApiBaseUrl(undefined, true)).toEqual({
      baseUrl: null,
      error: 'VITE_API_BASE_URL must be configured for production.',
    })
  })

  it.each([
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://0.0.0.0:8000',
    'http://[::1]:8000',
  ])('rejects loopback API endpoints in production: %s', (value) => {
    expect(resolveApiBaseUrl(value, true).baseUrl).toBeNull()
  })

  it('requires HTTPS in production', () => {
    expect(resolveApiBaseUrl('http://api.example.com', true).error).toBe(
      'The production API endpoint must use HTTPS.',
    )
  })

  it('normalizes a valid production API origin', () => {
    expect(resolveApiBaseUrl(' https://api.example.com/// ', true)).toEqual({
      baseUrl: 'https://api.example.com',
      error: null,
    })
  })

  it('rejects credentials embedded in the API URL', () => {
    expect(resolveApiBaseUrl('https://user:secret@api.example.com', true).baseUrl).toBeNull()
  })
})
