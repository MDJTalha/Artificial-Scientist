import { resolveApiBaseUrl } from './status'

export interface ApiRequestOptions {
  signal?: AbortSignal
  headers?: HeadersInit
}

export class ApiError extends Error {
  readonly status: number
  readonly detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export interface ApiClient {
  get<T>(path: string, options?: ApiRequestOptions): Promise<T>
  post<T>(path: string, body: unknown, options?: ApiRequestOptions): Promise<T>
  postBlob(path: string, body: unknown, options?: ApiRequestOptions): Promise<Blob>
}

/**
 * Create a typed JSON and binary client for the ASDS API.
 *
 * Credentials are intentionally omitted. Production authentication must be supplied
 * by a reviewed OIDC session adapter; the browser must never embed a shared API key.
 */
export function createApiClient(baseUrl: string | null): ApiClient {
  async function request<T>(
    method: 'GET' | 'POST',
    path: string,
    body?: unknown,
    options: ApiRequestOptions = {},
  ): Promise<T> {
    if (!baseUrl) {
      throw new ApiError(0, 'The ASDS API URL is not configured for this environment.')
    }

    if (!path.startsWith('/') || path.startsWith('//')) {
      throw new ApiError(0, 'API paths must be same-origin relative paths.')
    }

    const headers = new Headers(options.headers)
    headers.set('Accept', 'application/json')
    if (body !== undefined) headers.set('Content-Type', 'application/json')

    let response: Response
    try {
      response = await fetch(baseUrl + path, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: options.signal,
        credentials: 'omit',
        cache: 'no-store',
        redirect: 'error',
      })
    } catch (error) {
      if (options.signal?.aborted) throw error
      throw new ApiError(
        0,
        error instanceof Error
          ? 'The API could not be reached: ' + error.message
          : 'The API could not be reached.',
      )
    }

    const contentType = response.headers.get('content-type') ?? ''
    let payload: unknown = null
    if (response.status !== 204 && contentType.toLowerCase().includes('application/json')) {
      try {
        payload = await response.json()
      } catch {
        throw new ApiError(response.status, 'The API returned malformed JSON.')
      }
    }

    if (!response.ok) {
      const detail =
        typeof payload === 'object' &&
        payload !== null &&
        'detail' in payload &&
        typeof (payload as { detail?: unknown }).detail === 'string'
          ? (payload as { detail: string }).detail
          : 'The API request failed with HTTP ' + response.status + '.'
      throw new ApiError(response.status, detail)
    }

    if (payload === null) {
      throw new ApiError(response.status, 'The API returned an empty or non-JSON response.')
    }

    return payload as T
  }

  async function requestBlob(
    path: string,
    body: unknown,
    options: ApiRequestOptions = {},
  ): Promise<Blob> {
    if (!baseUrl) {
      throw new ApiError(0, 'The ASDS API URL is not configured for this environment.')
    }
    if (!path.startsWith('/') || path.startsWith('//')) {
      throw new ApiError(0, 'API paths must be same-origin relative paths.')
    }

    const headers = new Headers(options.headers)
    headers.set('Accept', 'image/png')
    headers.set('Content-Type', 'application/json')

    let response: Response
    try {
      response = await fetch(baseUrl + path, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
        signal: options.signal,
        credentials: 'omit',
        cache: 'no-store',
        redirect: 'error',
      })
    } catch (error) {
      if (options.signal?.aborted) throw error
      throw new ApiError(0, 'The API could not be reached.')
    }

    if (!response.ok) {
      let detail = 'The API request failed with HTTP ' + response.status + '.'
      if ((response.headers.get('content-type') ?? '').toLowerCase().includes('application/json')) {
        try {
          const payload: unknown = await response.json()
          if (
            typeof payload === 'object' &&
            payload !== null &&
            'detail' in payload &&
            typeof (payload as { detail?: unknown }).detail === 'string'
          ) {
            detail = (payload as { detail: string }).detail
          }
        } catch {
          throw new ApiError(response.status, 'The API returned malformed error JSON.')
        }
      }
      throw new ApiError(response.status, detail)
    }

    if (!(response.headers.get('content-type') ?? '').toLowerCase().includes('image/png')) {
      throw new ApiError(response.status, 'The API did not return the expected PNG image.')
    }
    return response.blob()
  }

  return {
    get: <T>(path: string, options?: ApiRequestOptions) =>
      request<T>('GET', path, undefined, options),
    post: <T>(path: string, body: unknown, options?: ApiRequestOptions) =>
      request<T>('POST', path, body, options),
    postBlob: (path: string, body: unknown, options?: ApiRequestOptions) =>
      requestBlob(path, body, options),
  }
}

export const apiConfiguration = resolveApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL,
  import.meta.env.PROD,
)

export const apiClient = createApiClient(apiConfiguration.baseUrl)
