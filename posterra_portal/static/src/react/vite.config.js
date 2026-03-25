import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Rollup plugin: neutralize AG Grid's string-literal module references so
 * Odoo's web.assets_frontend bundler doesn't mistake them for real dependencies.
 *
 * AG Grid v35 embeds developer help messages containing literal module names:
 *   import { ModuleRegistry } from 'ag-grid-community';
 *   import { AgChartsEnterpriseModule } from 'ag-charts-enterprise';
 *
 * Odoo's bundler scans for quoted module names and tries to resolve them as
 * AMD dependencies. Two-layer fix:
 *   1. Prefix lines starting with "import " (prevents ^import regex)
 *   2. Replace hyphenated module names with underscored variants
 *      (ag-grid-community → ag_grid_community) so Odoo can't match them
 */
function odooSafeImports() {
  return {
    name: 'odoo-safe-imports',
    renderChunk(code) {
      // Layer 1: prefix string-literal import lines
      code = code.replace(/\nimport /g, '\n import ')
      // Layer 2: mangle module name strings (hyphens → underscores)
      // We only use ag-grid-community, but AG Grid Community's own error
      // messages reference ag-grid-enterprise and ag-charts-enterprise
      // in developer help text. All three must be neutralized.
      code = code.replaceAll('ag-grid-community', 'ag_grid_community')
      code = code.replaceAll('ag-grid-enterprise', 'ag_grid_enterprise')
      code = code.replaceAll('ag-charts-enterprise', 'ag_charts_enterprise')
      return code
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
