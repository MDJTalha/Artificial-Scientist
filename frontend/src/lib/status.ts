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
        detail: 'Contacting the local API.',
      }
    case 'connected':
      return {
        label: 'API connected',
        detail: 'The API health endpoint responded successfully.',
      }
    case 'unavailable':
      return {
        label: 'API unavailable',
        detail: 'Start the backend and retry the connection check.',
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
