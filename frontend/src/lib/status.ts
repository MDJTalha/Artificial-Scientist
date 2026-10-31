export type ServiceStatus = 'checking' | 'connected' | 'unavailable'

export interface StatusPresentation {
  label: string
  detail: string
}

export function getStatusPresentation(status: ServiceStatus): StatusPresentation {
  switch (status) {
    case 'checking':
      return {
        label: 'Checking connection',
        detail: 'Checking the configured API endpoint.',
      }
    case 'connected':
      return {
        label: 'API connected',
        detail: 'The API health endpoint responded successfully.',
      }
    case 'unavailable':
      return {
        label: 'API unavailable',
        detail: 'The configured API endpoint is missing or did not respond.',
      }
  }
}


export interface HealthPayload {
  status: 'ok'
  service: string
  version: string
}

export function isHealthyResponse(payload: unknown): payload is HealthPayload {
  if (typeof payload !== 'object' || payload === null) return false

  const record = payload as Record<string, unknown>
  return (
    record.status === 'ok' &&
    typeof record.service === 'string' &&
    typeof record.version === 'string'
  )
}


export interface ApiBaseUrlConfiguration {
  baseUrl: string | null
  error: string | null
}

/**
 * Resolve the browser API origin without allowing production to silently
 * fall back to a developer machine or an insecure HTTP endpoint.
 */
export function resolveApiBaseUrl(
  value: string | undefined,
  isProduction: boolean,
): ApiBaseUrlConfiguration {
  const candidate = value?.trim() || (isProduction ? '' : 'http://127.0.0.1:8000')

  if (!candidate) {
    return {
      baseUrl: null,
      error: 'VITE_API_BASE_URL must be configured for production.',
    }
  }

  let parsed: URL
  try {
    parsed = new URL(candidate)
  } catch {
    return {
      baseUrl: null,
      error: 'VITE_API_BASE_URL must be an absolute HTTP(S) URL.',
    }
  }

  if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') {
    return {
      baseUrl: null,
      error: 'VITE_API_BASE_URL must use HTTP or HTTPS.',
    }
  }

  if (parsed.username || parsed.password) {
    return {
      baseUrl: null,
      error: 'VITE_API_BASE_URL must not contain URL credentials.',
    }
  }

  if (isProduction && parsed.protocol !== 'https:') {
    return {
      baseUrl: null,
      error: 'The production API endpoint must use HTTPS.',
    }
  }

  const localHosts = new Set(['localhost', '127.0.0.1', '0.0.0.0', '::1', '[::1]'])
  if (isProduction && localHosts.has(parsed.hostname.toLowerCase())) {
    return {
      baseUrl: null,
      error: 'The production API endpoint must not use localhost or a loopback address.',
    }
  }

  return {
    baseUrl: candidate.replace(/\/+$/, ''),
    error: null,
  }
}
