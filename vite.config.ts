import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // 0.0.0.0 — dev-сервер слушает все интерфейсы и доступен с телефона
    // по локальной сети (Network: http://192.168.0.111:5173).
    host: '0.0.0.0',
  },
})
