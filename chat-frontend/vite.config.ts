import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    {
      name: 'health-check',
      configureServer(server) {
        server.middlewares.use('/health', (req, res) => {
          res.statusCode = 200
          res.end('healthy')
        })
      }
    }
  ],
  server: {
    port: 5174
  },
  define: {
    'import.meta.env.VITE_BACKEND_PORT': process.env.BACKEND_PORT || 5000
  }
})
