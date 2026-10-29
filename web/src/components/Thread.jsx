import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { useLiveEvents } from '../live.jsx'
import { dayKey, displayName, fmtDay, fmtDateTime, fmtTime } from '../format.js'
import { Icon } from './Icon.jsx'

const LIMIT = 50
const byOrder = (a, b) => a.date_ms - b.date_ms || a.id - b.id

export default function Thread({ threadKey, onBack }) {
  const [info, setInfo] = useState(null)
  const [msgs, setMsgs] = useState([]) // ordre chronologique
  const [cursor, setCursor] = useState(null)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [newCount, setNewCount] = useState(0)
  const box = useRef(null)
  const stick = useRef(true)
  const prevHeight = useRef(0)

  const merge = (cur, add) => {
    const map = new Map(cur.map((m) => [m.id, m]))
    add.forEach((m) => map.set(m.id, m))
    return [...map.values()].sort(byOrder)
  }

  const loadInfo = useCallback(async () => {
    try { setInfo(await api(`/conversations/${encodeURIComponent(threadKey)}`)) } catch { /* conversation vide */ }
  }, [threadKey])

  const loadPage = useCallback(async (before) => {
    setLoading(true)
    try {
      const r = await api(`/conversations/${encodeURIComponent(threadKey)}/messages`, { params: { limit: LIMIT, before } })
      if (before && box.current) prevHeight.current = box.current.scrollHeight
      setMsgs((cur) => merge(cur, r.items))
      setCursor(r.next_cursor)
      setHasMore(r.has_more)
      setError('')
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }, [threadKey])

  useEffect(() => { loadInfo(); loadPage(null) }, [loadInfo, loadPage])

  useLiveEvents((e) => {
    if (e.type === 'sms_new') {
      const mine = e.messages.filter((m) => m.thread_key === threadKey)
      if (mine.length) {
        setMsgs((cur) => merge(cur, mine))
        if (!stick.current) setNewCount((n) => n + mine.length)
        loadInfo()
      }
    } else if (e.type === 'purged') { setMsgs([]); setInfo(null) }
  })

  // Conserve la position : en bas pour les nouveaux messages, stable lors du chargement de l'historique.
  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    if (prevHeight.current) { el.scrollTop = el.scrollHeight - prevHeight.current; prevHeight.current = 0 }
    else if (stick.current) el.scrollTop = el.scrollHeight
  }, [msgs])

  const onScroll = () => {
    const el = box.current
    stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
    if (stick.current) setNewCount(0)
  }

  let lastDay = ''
  return (
    <div className="thread">
      <header className="thread-head">
        <button className="iconbtn only-mobile" onClick={onBack} aria-label="Retour aux conversations"><Icon name="back" /></button>
        <div>
          <h2>{info ? displayName(info) : '…'}</h2>
          {info && <p className="muted small">{info.contact_name ? `${info.address} · ` : ''}{info.message_count.toLocaleString('fr-FR')} message(s) · depuis le {fmtDateTime(info.first_date_ms)}</p>}
        </div>
      </header>
      <div className="msgs" ref={box} onScroll={onScroll}>
        {hasMore && <button className="btn ghost older" onClick={() => loadPage(cursor)} disabled={loading}>{loading ? 'Chargement…' : 'Afficher les messages plus anciens'}</button>}
        {error && <p className="error pad">{error}</p>}
        {msgs.map((m) => {
          const dk = dayKey(m.date_ms)
          const sep = dk !== lastDay
          lastDay = dk
          return (
            <React.Fragment key={m.id}>
              {sep && <div className="daysep"><span>{fmtDay(m.date_ms)}</span></div>}
              <div className={`bubble ${m.direction}`}>
                <p>{m.body}</p>
                <time title={fmtDateTime(m.date_ms)}>{fmtTime(m.date_ms)}</time>
              </div>
            </React.Fragment>
          )
        })}
      </div>
      {newCount > 0 && (
        <button className="newpill" onClick={() => { stick.current = true; box.current.scrollTop = box.current.scrollHeight; setNewCount(0) }}>
          {newCount} nouveau{newCount > 1 ? 'x' : ''} message{newCount > 1 ? 's' : ''}
        </button>
      )}
    </div>
  )
}
