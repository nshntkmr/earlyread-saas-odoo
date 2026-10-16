// Parity: the PDF's Attribute Grid placement (posterra_portal/services/pdf_export/placement.py)
// and the shared grid-utils placement.js must put every field in the SAME
// column. The shared fixture posterra_portal/tests/fixtures/pdf_placement.json
// is asserted here against the real effectiveColumns / resolvePlacement and by
// the Python suite (tag posterra_pdf_export) against the print copy.
// Run from repo root:
//   node --test posterra_portal/static/src/react/scripts/test_pdf_placement_parity.mjs

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import assert from 'node:assert/strict'
import test from 'node:test'

import { effectiveColumns, resolvePlacement } from '../../shared/grid-utils/placement.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const fixturePath = path.resolve(here, '../../../..', 'tests/fixtures/pdf_placement.json')
const { cases } = JSON.parse(readFileSync(fixturePath, 'utf-8'))

assert.ok(cases.length >= 8, 'fixture file looks truncated')

for (const c of cases) {
  test(`pdf placement parity: ${c.name}`, () => {
    const cols = effectiveColumns(c.width, c.configured)
    assert.equal(cols, c.expected_columns)
    assert.deepEqual(resolvePlacement(c.items, cols).map(i => i.resolved), c.expected)
  })
}
