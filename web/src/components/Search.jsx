import React, { useState } from 'react'
import { api } from '../api.js'
import { dateInputToMs, displayName, fmtDateTime } from '../format.js'

const SIZE = 25

function Highlight({ text, term }) {
  if (!term) return text
  const i = text.toLowerCase().indexOf(term.toLowerCase())
  if (i < 0) return text
  return <>{text.slice(0, i)}<mark>{text.slice(i, i + term.length)}</mark>{text.slice(i + term.length)}</>
}

export default function Search({ onOpenThread }) {
  const [f, setF] = useState({ q: '', direction: '', from: '', to: '' })
  const [res, setRes] = useState(null)
  const [term, setTerm] = useState('')
  const [page, setPage] = useState(1)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const run = async (p, filters = f) => {
    setBusy(true)
    try {
      const r = await api('/messages', {
        params: {
          q: filters.q.trim(), direction: filters.direction,
          date_from: dateInputToMs(filters.from, false), date_to: dateInputToMs(filters.to, true),
          page: p, page_size: SIZE,
        },
      })
      setRes(r); setPage(p); setTerm(filters.q.trim()); setError('')
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const pages = res ? Math.max(1, Math.ceil(res.total / SIZE)) : 1
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  return (
    <div className="page">
      <h1>Recherche</h1>
      <form className="card filters" onSubmit={(e) => { e.preventDefault(); run(1) }}>
        <div className="field grow">
          <label htmlFor="q">Texte, numéro ou nom</label>
          <input id="q" type="search" value={f.q} onChange={set('q')} placeholder="ex. code de vérification, 032 12 345 67…" />
        </div>
        <div className="field">
          <label htmlFor="dir">Sens</label>
          <select id="dir" value={f.direction} onChange={set('direction')}>
            <option value="">Tous</option><option value="in">Reçus</option><option value="out">Envoyés</option>
          </select>
        </div>
        <div className="field"><label htmlFor="from">Du</label><input id="from" type="date" value={f.from} onChange={set('from')} /></div>
        <div className="field"><label htmlFor="to">Au</label><input id="to" type="date" value={f.to} min={f.from || undefined} onChange={set('to')} /></div>
        <button className="btn primary" disabled={busy}>{busy ? 'Recherche…' : 'Rechercher'}</button>
        <button type="button" className="btn ghost" onClick={() => { const z = { q: '', direction: '', from: '', to: '' }; setF(z); setRes(null) }}>Effacer</button>
      </form>
      {error && <p className="error">{error}</p>}
      {res && (
        <>
          <p className="muted">{res.total.toLocaleString('fr-FR')} résultat(s)</p>
          <ul className="results">
            {res.items.map((m) => (
              <li key={m.id}>
                <button className="result" onClick={() => onOpenThread(m.thread_key)}>
                  <span className="result-top">
                    <strong>{displayName(m)}</strong>
                    <span className={`tag ${m.direction}`}>{m.direction === 'in' ? 'Reçu' : 'Envoyé'}</span>
                    <time>{fmtDateTime(m.date_ms)}</time>
                  </span>
                  <span className="result-body"><Highlight text={m.body} term={term} /></span>
                </button>
              </li>
            ))}
          </ul>
          {res.items.length === 0 && <p className="empty">Aucun message trouvé.</p>}
          {pages > 1 && (
            <div className="pager">
              <button className="btn ghost" disabled={page <= 1 || busy} onClick={() => run(page - 1)}>Précédent</button>
              <span>Page {page} / {pages}</span>
              <button className="btn ghost" disabled={page >= pages || busy} onClick={() => run(page + 1)}>Suivant</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
