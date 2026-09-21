// Parity: the PDF print mirror (posterra_portal/services/pdf_export/cell_format.py)
// and the portal grid formatters must print the SAME text. The shared fixture
// posterra_portal/tests/fixtures/pdf_cell_format.json is asserted here against
// the real VALUE_FORMATTERS (cases with js=true) and by the Python test suite
// (tag posterra_pdf_export) against the print mirror, so a change on either
// side that alters printed text fails one of the two.
// Run from repo root:
//   node --test posterra_portal/static/src/react/scripts/test_pdf_cell_format_parity.mjs

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import assert from 'node:assert/strict'
import test from 'node:test'

import { VALUE_FORMATTERS } from '../../shared/grid-utils/formatters.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const fixturePath = path.resolve(here, '../../../..', 'tests/fixtures/pdf_cell_format.json')
const { cases } = JSON.parse(readFileSync(fixturePath, 'utf-8'))

const jsCases = cases.filter(c => c.js)
assert.ok(jsCases.length >= 10, 'fixture file looks truncated')

for (const c of jsCases) {
  test(`pdf cell format parity: ${c.name}`, () => {
    const formatter = VALUE_FORMATTERS[c.col.valueFormatter]
    assert.ok(formatter, `unknown formatter ${c.col.valueFormatter}`)
    const out = formatter({ value: c.row[c.col.field], data: c.row, colDef: c.col })
    assert.equal(String(out), c.text)
  })
}
