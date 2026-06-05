import React from 'react'
import { resolveChildWidget } from './childRegistry'

/**
 * Composite widget — renders 1..N child blocks inside one card using
 * a 12-column CSS Grid. Each child is dispatched through resolveChildWidget
 * to its existing per-chart-type renderer. The server has already
 * normalized each child's data shape (e.g. echart_json → echart_option)
 * so child renderers receive exactly what they'd receive standalone.
 *
 * Data shape (from dashboard.widget._build_composite_data):
 *   {
 *     type: 'composite',
 *     children: [
 *       {
 *         id, chart_type, title,
 *         col_start, col_span, row_start, row_span, min_height_px,
 *         data: <native shape for that chart_type>
 *       }, ...
 *     ]
 *   }
 */
export default function CompositeWidget({ data }) {
  const children = data?.children || []
  if (!children.length) {
    return <div className="pv-composite-empty">No composite items configured</div>
  }
  return (
    <div className="pv-composite-grid">
      {children.map(child => {
        const Child = resolveChildWidget(child.chart_type)
        const style = {
          gridColumn: `${child.col_start} / span ${child.col_span}`,
          ...(child.row_start
            ? { gridRow: `${child.row_start} / span ${child.row_span}` }
            : { gridRow: `span ${child.row_span}` }),
        }
        if (!Child) {
          return (
            <div
              key={child.id}
              className="pv-composite-item pv-composite-item--unsupported"
              style={style}
            >
              <div className="pv-composite-unsupported">
                Unsupported child chart_type: <code>{child.chart_type}</code>
              </div>
            </div>
          )
        }
        const minHeight = child.min_height_px || 240
        return (
          <div
            key={child.id}
            className={`pv-composite-item pv-composite-item--${child.chart_type}`}
            style={style}
          >
            {child.title && <div className="pv-composite-item-title">{child.title}</div>}
            <div className="pv-composite-item-body" style={{ minHeight }}>
              <Child
                data={child.data}
                height={minHeight}
                name={child.title || ''}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
