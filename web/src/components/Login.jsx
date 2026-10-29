import React, { useState } from 'react'
import { api, ApiError, setToken, clearToken } from '../api.js'
import { Icon } from './Icon.jsx'

export default function Login({ error, onDone }) {
  const [value, setValue] = useState('')
  const [err, setErr] = useState(error)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setToken(value.trim())
    try {
      await api('/stats')
      onDone()
    } catch (ex) {
      clearToken()
      setErr(ex instanceof ApiError ? ex.message : 'Erreur inattendue.')
    } finally { setBusy(false) }
  }

  return (
    <div className="login">
      <form className="card login-card" onSubmit={submit}>
        <div className="brand big"><Icon name="logo" size={34} /></div>
        <h1>LocalSMS</h1>
        <p className="muted">
          L’interface s’ouvre normalement toute seule via le lanceur. Sinon, collez ici le jeton
          d’administration (fichier <code>admin_token</code> du dossier de données).
        </p>
        <label htmlFor="tok">Jeton d’administration</label>
        <input id="tok" type="password" autoComplete="off" value={value} onChange={(e) => setValue(e.target.value)} placeholder="lsa_…" required />
        {err && <p className="error" role="alert">{err}</p>}
        <button className="btn primary" disabled={busy || !value.trim()}>{busy ? 'Vérification…' : 'Se connecter'}</button>
      </form>
    </div>
  )
}
