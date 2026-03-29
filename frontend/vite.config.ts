import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  base: './',
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    proxy: {
      // Proxy les appels API vers le backend Python pendant le dev
      '/login': 'http://127.0.0.1:8000',
      '/status': 'http://127.0.0.1:8000',
      '/get_local_data': 'http://127.0.0.1:8000',
      '/volume': 'http://127.0.0.1:8000',
      '/coaching': 'http://127.0.0.1:8000',
      '/game': 'http://127.0.0.1:8000',
      '/tts': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
