import React, { useCallback, useEffect, useState } from 'react'
import { api, setToken } from '../api.js'
import { fmtBytes, fmtDateTime } from '../format.js'

async function waitRestart() {
  const url = '/api/v1/health'
  const up = async () => { try { return (await fetch(url, { cache: 'no-store' })).ok } catch { return false } }
  for (let i = 0; i < 20 && (await up()); i++) await new Promise((r) => setTimeout(r, 300)) // attend l'arrêt
  for (let i = 0; i < 60; i++) { if (await up()) { window.location.reload(); return } await new Promise((r) => setTimeout(r, 500)) }
}

export default function Settings({ onLogout }) {
  const [s, setS] = useState(null)
  const [info, setInfo] = useState(null)
  const [stats, setStats] = useState(null)
  const [msg, setMsg] = useState('')
  const [confirm, setConfirm] = useState('')
  const [adbPath, setAdbPath] = useState('')

  const load = useCallback(async () => {
    try {
      const [a, b, c] = await Promise.all([api('/settings'), api('/system/info'), api('/stats')])
      setS(a); setInfo(b); setStats(c); setAdbPath(a.adb_path)
    } catch (e) { setMsg(e.message) }
  }, [])
  useEffect(() => { load() }, [load])

  const save = async (patch) => {
    try { setS(await api('/settings', { method: 'PUT', body: patch })); setMsg('') } catch (e) { setMsg(e.message) }
  }
  const run = async (fn) => { try { await fn() } catch (e) { setMsg(e.message) } }

  if (!s) return <div className="page"><p className="muted">{msg || 'Chargement…'}</p></div>

  return (
    <div className="page">
      <h1>Réglages</h1>
      {msg && <p className="error" role="alert">{msg}</p>}

      <div className="card">
        <h2>Réseau</h2>
        <label className="check big">
          <input type="checkbox" checked={s.lan_mode} onChange={(e) => save({ lan_mode: e.target.checked })} />
          <span><strong>Autoriser le téléphone via le Wi-Fi local</strong><br />
            <span className="muted">Le serveur écoute sur le réseau local, mais refuse toute adresse non privée. Le trafic n’est pas chiffré : à n’utiliser que sur un réseau de confiance (pas de Wi-Fi public).</span></span>
        </label>
        <label className="check big">
          <input type="checkbox" checked={s.lan_admin} disabled={!s.lan_mode} onChange={(e) => save({ lan_admin: e.target.checked })} />
          <span><strong>Autoriser aussi cette interface depuis le réseau local</strong><br />
            <span className="muted">Déconseillé. Par défaut, seule la machine locale peut administrer LocalSMS.</span></span>
        </label>
        <p className="muted small">Mode actif : {s.effective.lan_mode ? 'réseau local' : 'ce PC uniquement'} · port {s.effective.port}{info?.local_ips?.length ? ` · adresses : ${info.local_ips.join(', ')}` : ''}</p>
        {s.restart_required && (
          <div className="note">Un redémarrage est nécessaire pour appliquer ce changement.{' '}
            <button className="btn primary" onClick={() => run(async () => { await api('/system/restart', { method: 'POST' }); waitRestart() })}>Redémarrer maintenant</button>
          </div>
        )}
      </div>

      <div className="card">
        <h2>ADB</h2>
        <div className="field">
          <label htmlFor="adb">Chemin de adb (laisser vide pour la détection automatique)</label>
          <div className="row">
            <input id="adb" value={adbPath} onChange={(e) => setAdbPath(e.target.value)} placeholder="C:\platform-tools\adb.exe" />
            <button className="btn" onClick={() => save({ adb_path: adbPath })}>Enregistrer</button>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Données</h2>
        {stats && <p>{stats.message_count.toLocaleString('fr-FR')} SMS · {stats.conversation_count.toLocaleString('fr-FR')} conversations · base de {fmtBytes(stats.db_size_bytes)}{stats.first_date_ms ? ` · du ${fmtDateTime(stats.first_date_ms)} au ${fmtDateTime(stats.last_date_ms)}` : ''}</p>}
        <p className="muted small">Dossier : <code>{info?.data_dir}</code></p>
        <div className="danger-zone">
          <label htmlFor="purge">Supprimer tous les SMS du PC (le téléphone n’est pas modifié) — tapez <code>SUPPRIMER</code></label>
          <div className="row">
            <input id="purge" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="off" />
            <button className="btn danger" disabled={confirm !== 'SUPPRIMER'} onClick={() => run(async () => { const r = await api('/data/purge', { method: 'POST', body: { confirm } }); setConfirm(''); setMsg(`${r.deleted} message(s) supprimé(s).`); load() })}>Supprimer</button>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Sécurité et application</h2>
        <div className="row">
          <button className="btn" onClick={() => run(async () => { if (!window.confirm('Régénérer le jeton d’administration ?')) return; const r = await api('/auth/rotate-admin-token', { method: 'POST' }); setToken(r.token); setMsg('Jeton régénéré.') })}>Régénérer le jeton d’administration</button>
          <button className="btn" onClick={onLogout}>Se déconnecter de l’interface</button>
          <a className="btn" href="/docs" target="_blank" rel="noreferrer">Documentation de l’API</a>
          <button className="btn danger" disabled={!info?.can_shutdown} onClick={() => run(async () => { if (!window.confirm('Arrêter LocalSMS ? La synchronisation s’interrompra jusqu’au prochain lancement.')) return; await api('/system/shutdown', { method: 'POST' }); setMsg('LocalSMS est arrêté. Vous pouvez fermer cet onglet.') })}>Quitter LocalSMS</button>
        </div>
        <p className="muted small">Version {info?.version}</p>
      </div>
    </div>
  )
}
