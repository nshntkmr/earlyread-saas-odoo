import React from 'react'
import { CELL_RENDERERS } from './renderers'
import { VALUE_FORMATTERS } from './formatters'

/**
 * TanStack Table adapters for @posterra/grid-utils renderers.
 *
 * AG Grid renderers receive:   params = { value, data, colDef: { cellRendererParams } }
 * TanStack cell functions get:  info  = { getValue(), row, column, table }
 *
 * This module bridges the gap so ALL existing renderers work in TanStack
 * without rewriting their internals.
 */

/**
 * Wrap an AG Grid cell renderer for use as a TanStack `cell` function.
 *
 * @param {Function|React.Component} Renderer — AG Grid renderer component
 * @returns {Function} — TanStack cell render function
 */
export function adaptRenderer(Renderer) {
  return function TanStackCellAdapter(info) {
    const params = {
      value: info.getValue(),
      data: info.row.original,
      colDef: {
        cellRendererParams: info.column.columnDef.meta?.rendererParams || {},
        field: info.column.columnDef.accessorKey,
      },
    }
    return <Renderer {...params} />
  }
}

/**
 * Wrap an AG Grid value formatter for use as a TanStack `cell` function
 * that formats + renders as a plain span.
 *
 * @param {Function} formatter — AG Grid value formatter function
 * @returns {Function} — TanStack cell render function
 */
export function adaptFormatter(formatter) {
  return function TanStackFormatterAdapter(info) {
    const value = info.getValue()
    if (value === null || value === undefined || value === '') return null
    const params = {
      value,
      data: info.row.original,
      colDef: info.column.columnDef,
    }
    const formatted = formatter(params)
    return <span>{formatted}</span>
  }
}

/**
 * Pre-built adapted renderers — ready to use in TanStack column definitions.
 * Keys match the CELL_RENDERERS registry from renderers.jsx.
 *
 * Usage in resolveTanStackColumns:
 *   import { TANSTACK_RENDERERS } from './tanstackAdapters'
 *   column.cell = TANSTACK_RENDERERS[colDef.cellRenderer]
 */
export const TANSTACK_RENDERERS = Object.fromEntries(
  Object.entries(CELL_RENDERERS).map(([key, Renderer]) => [
    key,
    adaptRenderer(Renderer),
  ])
)

/**
 * Pre-built adapted formatters.
 *
 * Usage: column.cell = TANSTACK_FORMATTERS[colDef.valueFormatter]
 */
export const TANSTACK_FORMATTERS = Object.fromEntries(
  Object.entries(VALUE_FORMATTERS || {}).map(([key, fn]) => [
    key,
    adaptFormatter(fn),
  ])
)
