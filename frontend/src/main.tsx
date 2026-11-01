import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Auth0Provider } from '@auth0/auth0-react'

import App from './App'
import './styles.css'

const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error('The application root element was not found.')
}

const auth0Domain = (import.meta.env.VITE_AUTH0_DOMAIN ?? '').trim()
const auth0ClientId = (import.meta.env.VITE_AUTH0_CLIENT_ID ?? '').trim()
const auth0Audience = (import.meta.env.VITE_AUTH0_AUDIENCE ?? '').trim()

function Root() {
  if (!auth0Domain || !auth0ClientId) {
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <div className="eyebrow">ASDS · AUTHENTICATION SETUP</div>
          <h1>Auth0 configuration required</h1>
          <p>Set VITE_AUTH0_DOMAIN and VITE_AUTH0_CLIENT_ID in frontend/.env.local, then restart the Vite development server.</p>
        </section>
      </main>
    )
  }

  return (
    <Auth0Provider
      domain={auth0Domain}
      clientId={auth0ClientId}
      authorizationParams={{
        redirect_uri: `${window.location.origin}/`,
        ...(auth0Audience ? { audience: auth0Audience } : {}),
      }}
    >
      <App />
    </Auth0Provider>
  )
}

createRoot(rootElement).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
