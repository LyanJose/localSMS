const dtf = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })
const timef = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' })
const dayf = new Intl.DateTimeFormat('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
const shortf = new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: '2-digit', year: '2-digit' })

export const fmtDateTime = (ms) => (ms ? dtf.format(new Date(ms)) : '—')
export const fmtTime = (ms) => timef.format(new Date(ms))
export const fmtDay = (ms) => dayf.format(new Date(ms))
export const dayKey = (ms) => {
  const d = new Date(ms)
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
}

/** Heure si aujourd'hui, « hier », sinon date courte. */
export function fmtListDate(ms) {
  const d = new Date(ms)
  const now = new Date()
  if (dayKey(ms) === dayKey(now.getTime())) return timef.format(d)
  const y = new Date(now); y.setDate(now.getDate() - 1)
  if (dayKey(ms) === dayKey(y.getTime())) return 'Hier'
  return shortf.format(d)
}

export function fmtAgo(ms) {
  if (!ms) return 'jamais'
  const s = Math.max(0, Math.round((Date.now() - ms) / 1000))
  if (s < 10) return 'à l’instant'
  if (s < 60) return `il y a ${s} s`
  const m = Math.round(s / 60)
  if (m < 60) return `il y a ${m} min`
  const h = Math.round(m / 60)
  if (h < 48) return `il y a ${h} h`
  return `il y a ${Math.round(h / 24)} j`
}

export const displayName = (c) => c.contact_name || c.address
export const initials = (c) => {
  const n = displayName(c).trim()
  if (/^[+\d\s().-]+$/.test(n)) return '#'
  return n.split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase()
}
export const fmtBytes = (n) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} Mo` : `${Math.max(1, Math.round(n / 1024))} Ko`)

export function dateInputToMs(value, endOfDay) {
  if (!value) return undefined
  const d = new Date(`${value}T${endOfDay ? '23:59:59.999' : '00:00:00'}`)
  return Number.isNaN(d.getTime()) ? undefined : d.getTime()
}
