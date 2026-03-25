import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Rollup plugin: prefix any line starting with "import " inside string
 * literals with a space so Odoo's asset bundler doesn't mistake them for
 * real ESM imports. AG Grid v35 embeds multi-line template strings
 * containing developer help messages like:
 *   import { ModuleRegistry } from 'ag-grid-community';
 * These break across actual newlines in the minified output, and Odoo's
 * regex scanner sees them as top-level imports → module resolution failure.
 */
function odooSafeImports() {
  return {
    name: 'odoo-safe-imports',
    renderChunk(code) {
      // Prefix any line that starts with "import " with a space.
      // Real imports are already gone (IIFE format), so only string-literal
      // ones remain. The leading space prevents Odoo's ^import regex match.
      return code.replace(/\nimport /g, '\n import ')
    },
  }
}

export default defineConfig({
  plugins: [react(), odooSafeImports()],
  build: {
    outDir: 'dist',
    rollupOptions: {
      // Explicit JS entry point (no index.html needed — Odoo serves the HTML)
      input: 'src/main.jsx',
      output: {
        // IIFE format: wraps bundle in (function(){...})() so no import/export
        // statements leak to Odoo's asset bundler. Required because AG Grid's
        // error messages contain string-literal "import" statements that Odoo
        // misinterprets as real ESM imports and tries to resolve as AMD modules.
        format: 'iife',
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
