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
  plugins: [
    react({
      // Include the shared grid-utils package for JSX transformation.
      // Without this, Vite's React plugin only transforms .jsx files within
      // the project root — shared package files at ../shared/ would be skipped.
      include: ['src/**/*.jsx', /grid-utils\/.*\.jsx$/],
    }),
    odooSafeImports(),
  ],
  // Prevent Vite from caching @posterra/grid-utils (file: symlink).
  // Without this, Vite may use a stale pre-bundled version that's missing
  // newly added renderers (CompositeRenderer, DualValueRenderer, etc.).
  optimizeDeps: {
    exclude: ['@posterra/grid-utils'],
  },
  // Base path for chunk imports — ensures dynamic import() resolves to the
  // correct Odoo static file URL, not relative to the page URL.
  base: '/posterra_portal/static/src/react/dist/',
  build: {
    outDir: 'dist',
    rollupOptions: {
      // Explicit JS entry point (no index.html needed — Odoo serves the HTML)
      input: 'src/main.jsx',
      output: {
        // ESM format: enables real code splitting via dynamic import().
        // Heavy libraries (MapLibre ~600KB) are split into separate chunks
        // and only downloaded on pages that use them.
        //
        // Previously IIFE to avoid Odoo's AMD resolver, but portal.js is
        // loaded via <script type="module"> in the template — NOT through
        // web.assets_frontend — so Odoo's bundler never processes it.
        // The odooSafeImports plugin still mangles AG Grid string-literals
        // as extra safety.
        format: 'es',
        // Fixed entry filename so the template <script> tag never needs updating.
        // Chunk files get content-hashed names for cache busting.
        entryFileNames: 'portal.js',
        chunkFileNames: 'chunks/[name]-[hash].js',
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
