import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Relative Verweise im Buendel: Home Assistant blendet das Add-on unter einem
// Pfad mit Sitzungskennung ein, der bei jedem Aufruf ein anderer ist. Absolute
// Pfade wuerden dort ins Leere zeigen.
export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5174,
    // Im Entwicklungsbetrieb dieselbe Herkunft wie in Produktion, damit kein
    // CORS noetig ist. Ziel ist das lokal laufende Add-on.
    proxy: {
      '/ask': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/models': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/status': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
