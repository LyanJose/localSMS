import React from 'react'

const P = {
  logo: 'M5 6h22a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H15l-6 5v-5H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z',
  chat: 'M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1h-8l-4 3.5V17H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z',
  search: 'M10.5 3a7.5 7.5 0 1 0 4.6 13.4l4.5 4.5 1.4-1.4-4.5-4.5A7.5 7.5 0 0 0 10.5 3zm0 2a5.5 5.5 0 1 1 0 11 5.5 5.5 0 0 1 0-11z',
  phone: 'M8 2h8a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2zm0 3v12h8V5H8zm4 14.2a1 1 0 1 0 0 2 1 1 0 0 0 0-2z',
  gear: 'M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7zm8.4 5.2-.1-1.4 1.9-1.5-1.9-3.3-2.3.9a7 7 0 0 0-1.2-.7l-.4-2.4h-3.8l-.4 2.4c-.4.2-.8.4-1.2.7l-2.3-.9-1.9 3.3 1.9 1.5a7 7 0 0 0 0 1.4l-1.9 1.5 1.9 3.3 2.3-.9c.4.3.8.5 1.2.7l.4 2.4h3.8l.4-2.4c.4-.2.8-.4 1.2-.7l2.3.9 1.9-3.3z',
  back: 'M15 5l-7 7 7 7',
}

export function Icon({ name, size = 22 }) {
  const stroke = name === 'back'
  return (
    <svg width={size} height={size} viewBox={name === 'logo' ? '0 0 32 32' : '0 0 24 24'} aria-hidden="true"
      fill={stroke ? 'none' : 'currentColor'} stroke={stroke ? 'currentColor' : 'none'} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d={P[name]} />
    </svg>
  )
}
