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
