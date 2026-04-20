/**
 * Tremor color-class safelist.
 *
 * Tremor constructs Tailwind class names at runtime via template literals
 * (see node_modules/@tremor/react/dist/lib/utils.js:getColorClassNames),
 * e.g. `stroke-${color}-${shade}`. Tailwind's JIT scanner cannot detect
 * those — it only sees literal strings in source files.
 *
 * This file lists every color utility Tremor may emit at runtime so the
 * JIT keeps them in the generated CSS. It is scanned via the
 * `@source "../**\/*.{js,jsx,ts,tsx}"` directive in tailwind.css and
 * intentionally not imported anywhere — the classes exist only so the
 * scanner can find them.
 */

// Colors Tremor uses for charts, badges, and data viz
const COLORS = [
  'emerald', 'red', 'teal', 'blue', 'indigo', 'violet',
  'amber', 'orange', 'pink', 'cyan', 'slate', 'green',
  'rose', 'gray', 'yellow', 'lime', 'sky', 'purple', 'fuchsia', 'stone', 'zinc', 'neutral',
]

// Shades Tremor touches (50..900 step 100)
const SHADES = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]

// Class prefixes Tremor's getColorClassNames generates
const PREFIXES = ['bg', 'text', 'border', 'ring', 'stroke', 'fill']

// Dark-mode variants Tremor also emits
const MODIFIERS = ['', 'dark:', 'hover:', 'dark:hover:']

// eslint-disable-next-line no-unused-vars
export const TREMOR_SAFELIST = (() => {
  const out = []
  for (const mod of MODIFIERS) {
    for (const prefix of PREFIXES) {
      for (const color of COLORS) {
        for (const shade of SHADES) {
          out.push(`${mod}${prefix}-${color}-${shade}`)
        }
      }
    }
  }
  return out
})()

// Explicit string-literal list — Tailwind's scanner also picks classes
// up from string literals, so we include the most common ones directly.
// This is belt-and-suspenders with the generated list above.
export const TREMOR_LITERAL_SAFELIST = `
  bg-emerald-50 bg-emerald-100 bg-emerald-200 bg-emerald-300 bg-emerald-400 bg-emerald-500 bg-emerald-600 bg-emerald-700 bg-emerald-800 bg-emerald-900
  text-emerald-50 text-emerald-100 text-emerald-200 text-emerald-300 text-emerald-400 text-emerald-500 text-emerald-600 text-emerald-700 text-emerald-800 text-emerald-900
  stroke-emerald-500 fill-emerald-500 border-emerald-500 ring-emerald-500

  bg-red-50 bg-red-100 bg-red-200 bg-red-300 bg-red-400 bg-red-500 bg-red-600 bg-red-700 bg-red-800 bg-red-900
  text-red-50 text-red-100 text-red-200 text-red-300 text-red-400 text-red-500 text-red-600 text-red-700 text-red-800 text-red-900
  stroke-red-500 fill-red-500 border-red-500 ring-red-500

  bg-teal-50 bg-teal-100 bg-teal-200 bg-teal-300 bg-teal-400 bg-teal-500 bg-teal-600 bg-teal-700 bg-teal-800 bg-teal-900
  text-teal-50 text-teal-100 text-teal-200 text-teal-300 text-teal-400 text-teal-500 text-teal-600 text-teal-700 text-teal-800 text-teal-900
  stroke-teal-500 fill-teal-500 border-teal-500 ring-teal-500

  bg-blue-50 bg-blue-100 bg-blue-200 bg-blue-300 bg-blue-400 bg-blue-500 bg-blue-600 bg-blue-700 bg-blue-800 bg-blue-900
  text-blue-50 text-blue-100 text-blue-200 text-blue-300 text-blue-400 text-blue-500 text-blue-600 text-blue-700 text-blue-800 text-blue-900
  stroke-blue-500 fill-blue-500 border-blue-500 ring-blue-500

  bg-indigo-500 text-indigo-500 stroke-indigo-500 fill-indigo-500 border-indigo-500 ring-indigo-500
  bg-violet-500 text-violet-500 stroke-violet-500 fill-violet-500 border-violet-500 ring-violet-500
  bg-amber-500 text-amber-500 stroke-amber-500 fill-amber-500 border-amber-500 ring-amber-500
  bg-orange-500 text-orange-500 stroke-orange-500 fill-orange-500 border-orange-500 ring-orange-500
  bg-pink-500 text-pink-500 stroke-pink-500 fill-pink-500 border-pink-500 ring-pink-500
  bg-cyan-500 text-cyan-500 stroke-cyan-500 fill-cyan-500 border-cyan-500 ring-cyan-500
  bg-slate-500 text-slate-500 stroke-slate-500 fill-slate-500 border-slate-500 ring-slate-500
  bg-green-500 text-green-500 stroke-green-500 fill-green-500 border-green-500 ring-green-500
  bg-rose-500 text-rose-500 stroke-rose-500 fill-rose-500 border-rose-500 ring-rose-500
  bg-gray-500 text-gray-500 stroke-gray-500 fill-gray-500 border-gray-500 ring-gray-500

  dark:stroke-emerald-500 dark:fill-emerald-500 dark:text-emerald-500
  dark:stroke-red-500 dark:fill-red-500 dark:text-red-500
  dark:stroke-teal-500 dark:fill-teal-500 dark:text-teal-500
  dark:stroke-amber-500 dark:fill-amber-500 dark:text-amber-500

  // ── Grid / layout utilities Tremor builds at runtime ─────────────────
  // Tremor's <Grid numItems={N}> emits class="grid grid-cols-${N} ..."
  // and <Col numColSpan={N}> emits "col-span-${N}". Same JIT-blind spot
  // as the colors above. Without these, Bootstrap's global .grid rule
  // (Odoo assets_frontend) wins the cascade and forces a 12-col layout.
  grid grid-cols-1 grid-cols-2 grid-cols-3 grid-cols-4 grid-cols-5 grid-cols-6 grid-cols-12
  col-span-1 col-span-2 col-span-3 col-span-4 col-span-5 col-span-6 col-span-12
  gap-1 gap-2 gap-3 gap-4 gap-5 gap-6 gap-8
  row-span-1 row-span-2 row-span-3 row-span-4
`
