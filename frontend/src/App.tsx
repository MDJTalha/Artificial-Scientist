import { useEffect, useState } from 'react'

import ResearchWorkspace from './components/ResearchWorkspace'
import { apiClient, apiConfiguration } from './lib/api'
import { getStatusPresentation, isHealthyResponse, type ServiceStatus } from './lib/status'

export default function App() {
  const [status, setStatus] = useState<ServiceStatus>('checking')
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    async function checkApi() {
      setStatus('checking')

      if (!apiConfiguration.baseUrl) {
        setStatus('unavailable')
        return
      }

      try {
        const payload = await apiClient.get<unknown>('/api/v1/health', {
          signal: controller.signal,
        })

        if (!isHealthyResponse(payload)) {
          throw new Error('The API did not report a healthy status.')
        }

        setStatus('connected')
      } catch {
        if (!controller.signal.aborted) setStatus('unavailable')
      }
    }

    void checkApi()
    return () => controller.abort()
  }, [retryKey])

  // Keep the status text centralized with the same wording used throughout the app.
  const presentation = getStatusPresentation(status)

  return (
    <div data-api-status={status} data-api-detail={presentation.detail}>
      <ResearchWorkspace
        apiStatus={status}
        onRetry={() => setRetryKey((current) => current + 1)}
      />
    </div>
  )
}
