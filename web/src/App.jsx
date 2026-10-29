import React, { useCallback, useEffect, useState } from 'react'
import { api, ApiError, clearToken, getToken } from './api.js'
import { LiveProvider, useLiveEvents, useLiveStatus } from './live.jsx'
import Login from './components/Login.jsx'
import Conversations from './components/Conversations.jsx'
import Search from './components/Search.jsx'
import Phone from './components/Phone.jsx'
import Settings from './components/Settings.jsx'
import { Icon } from './components/Icon.jsx'
import { fmtAgo } from './format.js'

const NAV = [
  { id: 'conversations', label: 'Conversations', icon: 'chat' },
  { id: 'search', label: 'Recherche', icon: 'search' },
  { id: 'phone', label: 'Téléphone', icon: 'phone' },
  { id: 'settings', label: 'Réglages', icon: 'gear' },
]

function PhoneStatus({ devices, live }) {
  const [, tick] = useState(0)
  useEffect(() => { const t = setInterval(() => tick((n) => n + 1), 15000); return () => clearInterval(t) }, [])
  const best = devices.find((d) => d.online) || devices[0]
  let cls = 'off'
  let text = 'Aucun téléphone associé'
  if (best) {
    cls = best.online ? 'on' : 'off'
    const bat = best.battery != null ? ` · ${best.battery} %${best.charging ? ' ⚡' : ''}` : ''
    text = best.online
      ? `${best.name} connecté${bat}${best.pending ? ` · ${best.pending} en attente` : ''}`
      : `${best.name} hors ligne · vu ${fmtAgo(best.last_seen_at)}`
  }
  return (
    <div className="statusbar" role="status">
      <span className={`dot ${cls}`} aria-hidden />
      <span className="status-text">{text}</span>
      {best?.transport && best.online && <span className="chip">{best.transport === 'usb' ? 'USB' : 'Wi-Fi'}</span>}
      <span className={`live ${live ? 'ok' : ''}`} title={live ? 'Temps réel actif' : 'Reconnexion au temps réel…'}>
        {live ? 'Temps réel' : 'Reconnexion…'}
      </span>
    </div>
  )
}

function Shell({ onLogout }) {
  const [view, setView] = useState('conversations')
  const [thread, setThread] = useState(null)
  const [devices, setDevices] = useState([])
  const [sync, setSync] = useState(null)
  const live = useLiveStatus()

  const loadDevices = useCallback(async () => {
    try { setDevices((await api('/devices')).items) } catch (e) { if (e instanceof ApiError && e.status === 401) onLogout() }
  }, [onLogout])

  useEffect(() => { loadDevices(); const t = setInterval(loadDevices, 30000); return () => clearInterval(t) }, [loadDevices])

  useLiveEvents((e) => {
    if (e.type === 'device_status') {
      setDevices((cur) => (cur.some((d) => d.id === e.device.id) ? cur.map((d) => (d.id === e.device.id ? e.device : d)) : [e.device, ...cur]))
    } else if (e.type === 'device_removed') {
      setDevices((cur) => cur.filter((d) => d.id !== e.device_id))
    } else if (e.type === 'connected') {
      loadDevices()
    } else if (e.type === 'sync_progress') {
      setSync(e.remaining ? e : null)
      if (!e.remaining) loadDevices()
    }
  })

  const openThread = (key) => { setThread(key); setView('conversations') }

  return (
    <div className="shell">
      <nav className="rail" aria-label="Navigation principale">
        <div className="brand" title="LocalSMS"><Icon name="logo" /></div>
        {NAV.map((n) => (
          <button key={n.id} className={`navbtn ${view === n.id ? 'active' : ''}`} onClick={() => setView(n.id)} aria-current={view === n.id ? 'page' : undefined}>
            <Icon name={n.icon} /><span>{n.label}</span>
          </button>
        ))}
      </nav>
      <div className="main">
        <PhoneStatus devices={devices} live={live} />
        {sync && (
          <div className="syncbar" role="status">
            Synchronisation en cours… il reste {sync.remaining.toLocaleString('fr-FR')} message(s) à recevoir.
          </div>
        )}
        <div className="content">
          {view === 'conversations' && <Conversations selected={thread} onSelect={setThread} />}
          {view === 'search' && <Search onOpenThread={openThread} />}
          {view === 'phone' && <Phone devices={devices} reload={loadDevices} />}
          {view === 'settings' && <Settings onLogout={onLogout} />}
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const [state, setState] = useState(getToken() ? 'checking' : 'login')
  const [error, setError] = useState('')

  const check = useCallback(async () => {
    try {
      await api('/stats')
      setState('ok')
      setError('')
    } catch (e) {
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
        clearToken()
        setError(e.status === 403 ? e.message : 'Jeton invalide ou expiré.')
        setState('login')
      } else {
        setError(e.message)
        setState('down')
      }
    }
  }, [])

  useEffect(() => { if (state === 'checking') check() }, [state, check])

  if (state === 'checking') return <div className="splash">Connexion à LocalSMS…</div>
  if (state === 'down') {
    return (
      <div className="splash">
        <p>{error}</p>
        <button className="btn" onClick={() => setState('checking')}>Réessayer</button>
      </div>
    )
  }
  if (state === 'login') return <Login error={error} onDone={() => setState('checking')} />
  return (
    <LiveProvider enabled>
      <Shell onLogout={() => { clearToken(); setError(''); setState('login') }} />
    </LiveProvider>
  )
}
