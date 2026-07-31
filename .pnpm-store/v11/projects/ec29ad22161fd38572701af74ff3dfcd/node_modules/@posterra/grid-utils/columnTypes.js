import { VALUE_FORMATTERS } from './formatters'

// ── Custom column types (pre-bundle common settings) ────────────────────────
// Registered in AG Grid via columnTypes prop. Admin selects these from
// the Column Type dropdown in TableColumnSettings.jsx.

export const CUSTOM_COLUMN_TYPES = {
  numericColumn: {
    filter: 'agNumberColumnFilter',
    cellStyle: { textAlign: 'right' },
  },
  currency: {
    width: 110,
    cellStyle: { textAlign: 'right' },
    filter: 'agNumberColumnFilter',
    valueFormatter: VALUE_FORMATTERS.currency,
  },
  percentage: {
    width: 100,
    cellStyle: { textAlign: 'right' },
    filter: 'agNumberColumnFilter',
    valueFormatter: VALUE_FORMATTERS.percentage,
  },
}

// ── Smart defaults by schema column data_type ───────────────────────────────
// Used by TableConfigurator when admin adds a column — auto-sets width,
// alignment, formatter, and filter based on the column's data type.

export const TYPE_DEFAULTS = {
  text:    { type: null,            width: 200, align: 'left',  formatter: null,         filter: 'agTextColumnFilter' },
  numeric: { type: 'numericColumn', width: 110, align: 'right', formatter: 'number',     filter: 'agNumberColumnFilter' },
  integer: { type: 'numericColumn', width: 100, align: 'right', formatter: 'number',     filter: 'agNumberColumnFilter' },
  float:   { type: 'numericColumn', width: 110, align: 'right', formatter: 'decimal',    filter: 'agNumberColumnFilter' },
  date:    { type: null,            width: 120, align: 'left',  formatter: 'date',       filter: 'agDateColumnFilter' },
  boolean: { type: null,            width: 80,  align: 'center', formatter: null,         filter: null },
}
