import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // Proxy API calls to the local dev server during development
      '/admin': 'http://localhost:8000',
      '/public': 'http://localhost:8000',
    },
  },
  define: {
    // Make env vars available via import.meta.env
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version),
  },
})
