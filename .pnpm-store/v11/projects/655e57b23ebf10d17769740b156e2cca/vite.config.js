import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    exclude: ['@posterra/grid-utils'],
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      input: 'src/main.jsx',
      output: {
        entryFileNames: 'designer.js',
        chunkFileNames: '[name].js',
        assetFileNames: '[name].[ext]',
      },
    },
  },
  server: {
    port: 3001,
    proxy: {
      '/dashboard/designer/api': 'http://localhost:8069',
      '/web': 'http://localhost:8069',
    },
  },
})
