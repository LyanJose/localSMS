import React, { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { useLiveEvents } from '../live.jsx'
import { displayName, fmtListDate, initials } from '../format.js'
import Thread from './Thread.jsx'

const PAGE = 30

function mergeFresh(fresh, old) {
  const seen = new Set(fresh.map((c) => c.thread_key))
  return [...fresh, ...old.filter((c) => !seen.has(c.thread_key))].sort((a, b) => b.last_date_ms - a.last_date_ms)
}

export default function Conversations({ selected, onSelect }) {
  const [q, setQ] = useState('')
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const qRef = useRef('')

  const load = useCallback(async (query, p, replace) => {
    setLoading(true)
    try {
      const r = await api('/conversations', { params: { q: query, page: p, page_size: PAGE } })
      if (qRef.current !== query) return
      setTotal(r.total)
      setItems((cur) => (replace ? r.items : mergeFresh(r.items, cur)))
      setError('')
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }, [])

  useEffect(() => {
    qRef.current = q
    setPage(1)
    const t = setTimeout(() => load(q, 1, true), q ? 300 : 0)
    return () => clearTimeout(t)
  }, [q, load])

  const reloadSoon = useRef(null)
  useLiveEvents((e) => {
    if (e.type === 'sms_new' || e.type === 'purged' || e.type === 'connected') {
      clearTimeout(reloadSoon.current)
      reloadSoon.current = setTimeout(() => load(qRef.current, 1, e.type === 'purged'), 400)
    }
  })

  const more = () => { const n = page + 1; setPage(n); load(q, n, false) }

  return (
    <div className={`split ${selected ? 'has-thread' : ''}`}>
      <section className="listpane" aria-label="Liste des conversations">
        <div className="searchbox">
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filtrer par numéro ou nom" aria-label="Filtrer les conversations" />
        </div>
        {error && <p className="error pad">{error}</p>}
        <ul className="convs">
          {items.map((c) => (
            <li key={c.thread_key}>
              <button className={`conv ${selected === c.thread_key ? 'active' : ''}`} onClick={() => onSelect(c.thread_key)}>
                <span className="avatar" aria-hidden>{initials(c)}</span>
                <span className="conv-body">
                  <span className="conv-top">
                    <strong className="conv-name">{displayName(c)}</strong>
                    <time>{fmtListDate(c.last_date_ms)}</time>
                  </span>
                  <span className="conv-preview">{c.last_direction === 'out' ? 'Vous : ' : ''}{c.last_body}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
        {!loading && items.length === 0 && (
          <p className="empty pad">{q ? 'Aucune conversation ne correspond.' : 'Aucun SMS pour le moment. Associez un téléphone dans l’onglet « Téléphone ».'}</p>
        )}
        {items.length < total && (
          <button className="btn ghost wide" onClick={more} disabled={loading}>
            {loading ? 'Chargement…' : `Afficher plus (${items.length}/${total})`}
          </button>
        )}
      </section>
      <section className="threadpane" aria-label="Messages">
        {selected ? <Thread key={selected} threadKey={selected} onBack={() => onSelect(null)} /> : (
          <div className="empty center">Sélectionnez une conversation.</div>
        )}
      </section>
    </div>
  )
}
