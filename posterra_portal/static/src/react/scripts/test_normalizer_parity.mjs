// Golden-fixture parity: the grid-utils JS normalizer must produce the SAME
// canonical object as the Python normalizer for every fixture.
// Run from repo root (after generating fixtures):
//   python dashboard_builder/schemas/generate_golden_fixtures.py
//   node posterra_portal/static/src/react/scripts/test_normalizer_parity.mjs
// Structural comparison (assert.deepStrictEqual), never byte comparison.

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import assert from 'node:assert/strict'
import test from 'node:test'

import {
  normalizeAttributeGrid, normalizeMetricList,
} from '../../shared/grid-utils/configNormalizer.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const fixturePath = path.resolve(
  here, '../../../../..',
  'dashboard_builder/schemas/golden_fixtures/normalization.v1.json')
const fixtures = JSON.parse(readFileSync(fixturePath, 'utf-8'))

assert.ok(fixtures.length >= 8, 'fixture file looks truncated')

for (const fx of fixtures) {
  test(`normalizer parity: ${fx.name}`, () => {
    const actual = fx.widget === 'attribute_grid'
      ? normalizeAttributeGrid(fx.input)
      : normalizeMetricList(fx.input)
    assert.deepStrictEqual(actual, fx.canonical)
  })
}
