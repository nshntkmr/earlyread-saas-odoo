import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    rollupOptions: {
      // Explicit JS entry point (no index.html needed — Odoo serves the HTML)
      input: 'src/main.jsx',
      output: {
        // Fixed filenames so __manifest__.py never needs updating after builds
        entryFileNames: 'portal.js',
        chunkFileNames: '[name].js',
        assetFileNames: '[name].[ext]',  // → portal.css
      },
    },
  },
  // Dev server: proxies /api/* and /my/* to the running Odoo instance
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8069',
      '/my':  'http://localhost:8069',
      '/web': 'http://localhost:8069',
    },
  },
})
