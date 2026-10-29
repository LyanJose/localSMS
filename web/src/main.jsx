import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import { captureTokenFromHash } from './api.js'
import './styles.css'

captureTokenFromHash()
createRoot(document.getElementById('root')).render(<App />)
