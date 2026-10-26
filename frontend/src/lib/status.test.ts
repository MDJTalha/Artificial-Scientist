import { describe, expect, it } from 'vitest'

import { getStatusPresentation } from './status'

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
    expect(getStatusPresentation('unavailable').detail).toContain('Start the backend')
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
