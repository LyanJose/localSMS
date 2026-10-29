import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Le build est écrit directement dans le paquet Python pour que PyInstaller l'embarque.
export default defineConfig({
  plugins: [react()],
  base: './',
  build: { outDir: '../backend/localsms/web', emptyOutDir: true },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8765',
      '/ws': { target: 'ws://127.0.0.1:8765', ws: true },
    },
  },
})
