import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { getToken } from './api.js'

const LiveContext = createContext({ connected: false, subscribe: () => () => {} })

/** WebSocket temps réel avec authentification par premier message et reconnexion automatique. */
export function LiveProvider({ enabled, children }) {
  const [connected, setConnected] = useState(false)
  const listeners = useRef(new Set())

  const subscribe = useCallback((fn) => {
    listeners.current.add(fn)
    return () => listeners.current.delete(fn)
  }, [])

  useEffect(() => {
    if (!enabled) return undefined
    let ws
    let timer
    let ping
    let attempt = 0
    let stopped = false

    const open = () => {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${window.location.host}/ws`)
      ws.onopen = () => ws.send(JSON.stringify({ type: 'auth', token: getToken() }))
      ws.onmessage = (e) => {
        if (e.data === 'pong') return
        let msg
        try { msg = JSON.parse(e.data) } catch { return }
        if (msg.type === 'ready') {
          attempt = 0
          setConnected(true)
          listeners.current.forEach((fn) => fn({ type: 'connected' }))
          return
        }
        listeners.current.forEach((fn) => fn(msg))
      }
      ws.onclose = () => {
        setConnected(false)
        clearInterval(ping)
        if (stopped) return
        attempt += 1
        timer = setTimeout(open, Math.min(1000 * 2 ** attempt, 15000))
      }
      ws.onerror = () => ws.close()
      ping = setInterval(() => { if (ws.readyState === 1) ws.send('ping') }, 25000)
    }
    open()
    return () => {
      stopped = true
      clearTimeout(timer)
      clearInterval(ping)
      ws?.close()
    }
  }, [enabled])

  return <LiveContext.Provider value={{ connected, subscribe }}>{children}</LiveContext.Provider>
}

export const useLiveStatus = () => useContext(LiveContext).connected

/** Abonne `handler` aux événements du serveur (toujours la dernière version du handler). */
export function useLiveEvents(handler) {
  const { subscribe } = useContext(LiveContext)
  const ref = useRef(handler)
  ref.current = handler
  useEffect(() => subscribe((e) => ref.current(e)), [subscribe])
}
