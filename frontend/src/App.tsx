import { useEffect, useState } from 'react'

import ResearchWorkspace from './components/ResearchWorkspace'
import { apiClient, apiConfiguration, setApiCredentials } from './lib/api'
import {
  beginOidcLogin,
  completeOidcCallback,
  oidcConfiguredFromVite,
  oidcConfigurationFromVite,
  type AuthenticatedSession,
  type AuthenticationStatus,
} from './lib/oidc'
import { getStatusPresentation, isHealthyResponse, type ServiceStatus } from './lib/status'

interface SessionDiscoveryResponse {
  principal_id: string
  issuer: string
  memberships: AuthenticatedSession['memberships']
}

export default function App() {
  const [status, setStatus] = useState<ServiceStatus>('checking')
  const [retryKey, setRetryKey] = useState(0)
  const [authStatus, setAuthStatus] = useState<AuthenticationStatus>(
    oidcConfiguredFromVite() ? 'signed-out' : 'not-configured',
  )
  const [authSession, setAuthSession] = useState<AuthenticatedSession | null>(null)
  const [selectedTenantId, setSelectedTenantId] = useState<string | null>(null)
  const [authError, setAuthError] = useState<string | null>(null)

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

  useEffect(() => {
    const search = window.location.search
    const parameters = new URLSearchParams(search)
    if (!parameters.has('code') && !parameters.has('error')) return

    let active = true
    async function finishLogin() {
      setAuthStatus('processing')
      setAuthError(null)
      try {
        if (!apiConfiguration.baseUrl) {
          throw new Error('Configure VITE_API_BASE_URL before completing sign-in.')
        }
        const configuration = oidcConfigurationFromVite(
          import.meta.env.PROD,
          window.location.origin,
          window.location.pathname,
        )
        const token = await completeOidcCallback(search, configuration)
        if (!token) throw new Error('No OIDC authorization response was returned.')

        // Authenticate against the API before displaying any tenant choice.
        setApiCredentials({ accessToken: token.accessToken, tenantId: null })
        const identity = await apiClient.get<SessionDiscoveryResponse>('/api/v1/auth/session')
        if (!active) return

        setAuthSession({
          ...identity,
          accessToken: token.accessToken,
          expiresAt: token.expiresAt,
        })
        setSelectedTenantId(null)
        setAuthStatus('authenticated')
      } catch (error) {
        setApiCredentials(null)
        if (active) {
          setAuthSession(null)
          setSelectedTenantId(null)
          setAuthStatus('error')
          setAuthError(error instanceof Error ? error.message : 'OIDC sign-in failed.')
        }
      } finally {
        const cleanUrl = new URL(window.location.href)
        cleanUrl.search = ''
        cleanUrl.hash = ''
        window.history.replaceState({}, document.title, cleanUrl.toString())
      }
    }

    void finishLogin()
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!authSession) {
      setApiCredentials(null)
      return
    }
    if (authSession.expiresAt <= Date.now()) {
      setAuthSession(null)
      setSelectedTenantId(null)
      setAuthStatus('signed-out')
      setAuthError('Your OIDC access token expired. Sign in again to continue.')
      setApiCredentials(null)
      return
    }
    setApiCredentials({
      accessToken: authSession.accessToken,
      tenantId: selectedTenantId,
    })
    const expiryTimer = window.setTimeout(() => {
      setAuthSession(null)
      setSelectedTenantId(null)
      setAuthStatus('signed-out')
      setAuthError('Your OIDC access token expired. Sign in again to continue.')
      setApiCredentials(null)
    }, Math.max(0, authSession.expiresAt - Date.now()))
    return () => window.clearTimeout(expiryTimer)
  }, [authSession, selectedTenantId])

  async function signIn() {
    setAuthError(null)
    if (!apiConfiguration.baseUrl) {
      setAuthStatus('error')
      setAuthError('Configure VITE_API_BASE_URL before signing in.')
      return
    }
    try {
      setAuthStatus('processing')
      const configuration = oidcConfigurationFromVite(
        import.meta.env.PROD,
        window.location.origin,
        window.location.pathname,
      )
      await beginOidcLogin(configuration)
    } catch (error) {
      setAuthStatus('error')
      setAuthError(error instanceof Error ? error.message : 'OIDC sign-in could not start.')
    }
  }

  function signOut() {
    setApiCredentials(null)
    setAuthSession(null)
    setSelectedTenantId(null)
    setAuthStatus(oidcConfiguredFromVite() ? 'signed-out' : 'not-configured')
    setAuthError(null)
  }

  function selectTenant(tenantId: string) {
    const allowed = authSession?.memberships.some(
      (membership) => membership.tenant_id === tenantId,
    )
    setSelectedTenantId(allowed ? tenantId : null)
  }

  const presentation = getStatusPresentation(status)

  return (
    <div data-api-status={status} data-api-detail={presentation.detail}>
      <ResearchWorkspace
        apiStatus={status}
        onRetry={() => setRetryKey((current) => current + 1)}
        authStatus={authStatus}
        authSession={authSession}
        selectedTenantId={selectedTenantId}
        authError={authError}
        onSignIn={() => void signIn()}
        onSignOut={signOut}
        onSelectTenant={selectTenant}
      />
    </div>
  )
}
