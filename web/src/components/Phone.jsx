import React, { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { fmtAgo, fmtDateTime } from '../format.js'

function Pairing() {
  const [data, setData] = useState(null)
  const [left, setLeft] = useState(0)
  const [error, setError] = useState('')

  const create = async () => {
    try { const r = await api('/pairing/code', { method: 'POST' }); setData(r); setLeft(r.expires_in_s); setError('') }
    catch (e) { setError(e.message) }
  }
  useEffect(() => {
    if (!left) return undefined
    const t = setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000)
    return () => clearInterval(t)
  }, [data, left > 0]) // eslint-disable-line react-hooks/exhaustive-deps

  const expired = data && left <= 0
  return (
    <div className="card">
      <h2>Associer un téléphone</h2>
      <ol className="steps">
        <li>Installez l’application LocalSMS sur le téléphone et accordez l’accès aux SMS.</li>
        <li>Générez un code ci-dessous (valable 10 minutes, usage unique).</li>
        <li>Dans l’application, saisissez l’adresse du serveur et le code.</li>
      </ol>
      <button className="btn primary" onClick={create}>Générer un code</button>
      {error && <p className="error">{error}</p>}
      {data && (
        <div className="pairbox">
          <div className={`code ${expired ? 'expired' : ''}`} aria-live="polite">{data.display}</div>
          <p className="muted">{expired ? 'Code expiré — générez-en un nouveau.' : `Expire dans ${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}`}</p>
          <p><strong>Adresse du serveur à saisir :</strong></p>
          <ul className="urls">
            <li><code>{data.urls.usb}</code> <span className="muted">— liaison USB (adb reverse)</span></li>
            {data.urls.wifi.map((u) => <li key={u}><code>{u}</code> <span className="muted">— Wi-Fi local</span></li>)}
          </ul>
          {!data.lan_mode && <p className="note">Le mode réseau local est désactivé : seule la liaison USB fonctionne. Activez-le dans « Réglages » pour utiliser le Wi-Fi.</p>}
        </div>
      )}
    </div>
  )
}

function Usb() {
  const [st, setSt] = useState(null)
  const [msg, setMsg] = useState('')
  const [auto, setAuto] = useState(false)
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    setBusy(true)
    try { setSt(await api('/adb/status')); setAuto((await api('/settings')).adb_auto_reverse) } catch (e) { setMsg(e.message) } finally { setBusy(false) }
  }, [])
  useEffect(() => { refresh() }, [refresh])

  const reverse = async () => {
    try { const r = await api('/adb/reverse', { method: 'POST', body: {} }); setMsg(`Liaison USB activée sur ${r.results.filter((x) => x.ok).length} téléphone(s). Utilisez l’adresse http://127.0.0.1:${r.port} dans l’application.`) }
    catch (e) { setMsg(e.message) }
  }
  const toggleAuto = async (v) => { setAuto(v); try { await api('/settings', { method: 'PUT', body: { adb_auto_reverse: v } }) } catch (e) { setMsg(e.message) } }

  return (
    <div className="card">
      <h2>Liaison USB (optionnelle, via ADB)</h2>
      <p className="muted">Fonctionne sans Wi-Fi et sans ouvrir le serveur au réseau : le téléphone joint le PC par le câble.</p>
      {st && !st.available && <p className="note">{st.error}</p>}
      {st?.error && st.available && <p className="note">{st.error}</p>}
      {st?.available && (
        <ul className="plain">
          {st.devices.length === 0 && <li className="muted">Aucun téléphone détecté. Activez le « débogage USB » puis branchez-le.</li>}
          {st.devices.map((d) => (
            <li key={d.serial}><code>{d.serial}</code> {d.model && `(${d.model})`} — {d.state === 'device' ? 'autorisé' : d.state === 'unauthorized' ? 'à autoriser sur le téléphone' : d.state}</li>
          ))}
        </ul>
      )}
      <div className="row">
        <button className="btn" onClick={refresh} disabled={busy}>Détecter</button>
        <button className="btn primary" onClick={reverse} disabled={!st?.available}>Activer la liaison USB</button>
        <label className="check"><input type="checkbox" checked={auto} onChange={(e) => toggleAuto(e.target.checked)} /> Activer automatiquement à chaque branchement</label>
      </div>
      {msg && <p className="muted" role="status">{msg}</p>}
    </div>
  )
}

export default function Phone({ devices, reload }) {
  const remove = async (d) => {
    if (!window.confirm(`Révoquer « ${d.name} » ? Ses SMS déjà synchronisés sont conservés.`)) return
    try { await api(`/devices/${encodeURIComponent(d.id)}`, { method: 'DELETE' }); reload() } catch (e) { window.alert(e.message) }
  }
  return (
    <div className="page">
      <h1>Téléphone</h1>
      <div className="card">
        <h2>Appareils associés</h2>
        {devices.length === 0 && <p className="muted">Aucun appareil associé.</p>}
        <ul className="devices">
          {devices.map((d) => (
            <li key={d.id} className="device">
              <span className={`dot ${d.online ? 'on' : 'off'}`} aria-hidden />
              <div className="grow">
                <strong>{d.name}</strong> <span className="chip">{d.online ? 'En ligne' : 'Hors ligne'}</span>
                {d.transport && <span className="chip">{d.transport === 'usb' ? 'USB' : 'Wi-Fi'}</span>}
                <p className="muted small">
                  {d.battery != null && `Batterie ${d.battery} %${d.charging ? ' (en charge)' : ''} · `}
                  {d.message_count.toLocaleString('fr-FR')} SMS · {d.pending ? `${d.pending} en attente · ` : ''}
                  dernière synchro : {d.last_sync_at ? fmtDateTime(d.last_sync_at) : 'jamais'} · vu {fmtAgo(d.last_seen_at)}
                  {d.app_version ? ` · app ${d.app_version}` : ''}
                </p>
              </div>
              <button className="btn danger ghost" onClick={() => remove(d)}>Révoquer</button>
            </li>
          ))}
        </ul>
      </div>
      <Pairing />
      <Usb />
    </div>
  )
}
