import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, createApiClient, setApiCredentials } from './api'

describe('ASDS API client', () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => {
    setApiCredentials(null)
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('fails closed when no API origin is configured', async () => {
    const client = createApiClient(null)

    await expect(client.get('/api/v1/health')).rejects.toMatchObject({
      status: 0,
      message: 'The ASDS API URL is not configured for this environment.',
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('rejects external or protocol-relative paths', async () => {
    const client = createApiClient('https://api.example.test')

    await expect(client.get('//attacker.example/path')).rejects.toBeInstanceOf(ApiError)
    await expect(client.get('https://attacker.example/path')).rejects.toBeInstanceOf(ApiError)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('returns typed JSON from successful responses', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    const client = createApiClient('https://api.example.test')

    await expect(client.get<{ status: string }>('/api/v1/health')).resolves.toEqual({
      status: 'ok',
    })
    expect(fetchMock).toHaveBeenCalledWith(
      'https://api.example.test/api/v1/health',
      expect.objectContaining({
        method: 'GET',
        credentials: 'omit',
        cache: 'no-store',
        redirect: 'error',
      }),
    )
  })

  it('serializes JSON POST bodies and sets the content type', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ accepted: true }), {
        status: 201,
        headers: { 'content-type': 'application/json' },
      }),
    )
    const client = createApiClient('https://api.example.test')
    const body = { record_type: 'research_task', title: 'A bounded task' }

    await expect(client.post('/api/v1/records', body)).resolves.toEqual({ accepted: true })
    expect(fetchMock).toHaveBeenCalledWith(
      'https://api.example.test/api/v1/records',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(body),
        headers: expect.any(Headers),
      }),
    )
    const requestInit = fetchMock.mock.calls[0]?.[1]
    expect(new Headers(requestInit?.headers).get('Content-Type')).toBe('application/json')
  })

  it('preserves a safe API error detail', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'OIDC authentication is not fully configured.' }), {
        status: 503,
        headers: { 'content-type': 'application/json' },
      }),
    )
    const client = createApiClient('https://api.example.test')

    await expect(client.get('/api/v1/records')).rejects.toMatchObject({
      status: 503,
      message: 'OIDC authentication is not fully configured.',
    })
  })

  it('does not accept successful non-JSON responses as JSON data', async () => {
    fetchMock.mockResolvedValue(
      new Response('image bytes', { status: 200, headers: { 'content-type': 'image/png' } }),
    )
    const client = createApiClient('https://api.example.test')

    await expect(client.get('/api/v1/math/plot')).rejects.toMatchObject({
      status: 200,
      message: 'The API returned an empty or non-JSON response.',
    })
  })

  it('returns a PNG blob from the guarded binary endpoint', async () => {
    const imageBytes = new Blob(['png image bytes'], { type: 'image/png' })
    fetchMock.mockResolvedValue(
      new Response(imageBytes, {
        status: 200,
        headers: { 'content-type': 'image/png' },
      }),
    )
    const client = createApiClient('https://api.example.test')
    const result = await client.postBlob('/api/v1/math/plot', {
      expression: 'sin(x)',
      variable: 'x',
      lower: -2,
      upper: 2,
    })

    expect(result.type).toBe('image/png')
    expect(await result.text()).toBe('png image bytes')
    expect(fetchMock).toHaveBeenCalledWith(
      'https://api.example.test/api/v1/math/plot',
      expect.objectContaining({
        method: 'POST',
        credentials: 'omit',
        redirect: 'error',
      }),
    )
  })

  it('rejects a successful response that is not a PNG image', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    const client = createApiClient('https://api.example.test')

    await expect(client.postBlob('/api/v1/math/plot', {})).rejects.toMatchObject({
      status: 200,
      message: 'The API did not return the expected PNG image.',
    })
  })


  it('downloads a ZIP artifact only when the expected content type matches', async () => {
    const archive = new Blob(['zip bytes'], { type: 'application/zip' })
    fetchMock.mockResolvedValue(
      new Response(archive, { status: 200, headers: { 'content-type': 'application/zip' } }),
    )
    const client = createApiClient('https://api.example.test')

    const result = await client.getBlob('/api/v1/lab/runs/123/export', 'application/zip')
    expect(result.type).toBe('application/zip')
    expect(await result.text()).toBe('zip bytes')
    expect(fetchMock).toHaveBeenCalledWith(
      'https://api.example.test/api/v1/lab/runs/123/export',
      expect.objectContaining({
        method: 'GET',
        credentials: 'omit',
        cache: 'no-store',
        redirect: 'error',
      }),
    )
  })

  it('rejects a binary download with the wrong media type', async () => {
    fetchMock.mockResolvedValue(
      new Response('not a zip', { status: 200, headers: { 'content-type': 'text/plain' } }),
    )
    const client = createApiClient('https://api.example.test')

    await expect(client.getBlob('/api/v1/lab/runs/123/export', 'application/zip')).rejects.toMatchObject({
      status: 200,
      message: 'The API did not return the expected application/zip content type.',
    })
  })


  it('attaches the in-memory bearer token and explicitly selected tenant', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    setApiCredentials({ accessToken: 'signed-access-token', tenantId: 'tenant-123' })
    const client = createApiClient('https://api.example.test')

    await client.get('/api/v1/records')

    const request = fetchMock.mock.calls[0]?.[1]
    const headers = new Headers(request?.headers)
    expect(headers.get('Authorization')).toBe('Bearer signed-access-token')
    expect(headers.get('X-Tenant-ID')).toBe('tenant-123')
  })

  it('can validate an OIDC session before a tenant is selected', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ memberships: [] }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    setApiCredentials({ accessToken: 'signed-access-token', tenantId: null })
    const client = createApiClient('https://api.example.test')

    await client.get('/api/v1/auth/session')

    const headers = new Headers(fetchMock.mock.calls[0]?.[1]?.headers)
    expect(headers.get('Authorization')).toBe('Bearer signed-access-token')
    expect(headers.has('X-Tenant-ID')).toBe(false)
  })

  it('does not allow per-request headers to override the active identity', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    setApiCredentials({ accessToken: 'trusted-token', tenantId: 'trusted-tenant' })
    const client = createApiClient('https://api.example.test')

    await client.get('/api/v1/records', {
      headers: {
        Authorization: 'Bearer attacker-token',
        'X-Tenant-ID': 'attacker-tenant',
      },
    })

    const headers = new Headers(fetchMock.mock.calls[0]?.[1]?.headers)
    expect(headers.get('Authorization')).toBe('Bearer trusted-token')
    expect(headers.get('X-Tenant-ID')).toBe('trusted-tenant')
  })

})