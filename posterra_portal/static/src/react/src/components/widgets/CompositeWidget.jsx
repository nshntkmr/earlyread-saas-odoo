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
 *         content_vertical_align, content_horizontal_align,
 *         data: <native shape for that chart_type>
 *       }, ...
 *     ]
 *   }
 *
 * Content alignment: the body is a column-direction flexbox, so vertical
 * maps to justifyContent and horizontal to alignItems. stretch/stretch
 * (the default) emits NO styles and NO extra DOM — existing composites
 * render exactly as before. Non-stretch children render inside an
 * auto-sized wrapper so content shrinks to natural size (a child's
 * height:100% resolves to auto against an auto-height parent), making
 * the alignment visible. Generic — applies to every child type.
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
        // Normalize missing/invalid values to 'stretch' (defense-in-depth on
        // top of the server-side clamp) — stretch/stretch = today's exact DOM.
        const vAlign = ['top', 'center', 'bottom'].includes(child.content_vertical_align)
          ? child.content_vertical_align : 'stretch'
        const hAlign = ['left', 'center', 'right'].includes(child.content_horizontal_align)
          ? child.content_horizontal_align : 'stretch'
        const hasAlignment = vAlign !== 'stretch' || hAlign !== 'stretch'
        const bodyStyle = { minHeight }
        if (vAlign !== 'stretch') bodyStyle.justifyContent =
          { top: 'flex-start', center: 'center', bottom: 'flex-end' }[vAlign]
        if (hAlign !== 'stretch') bodyStyle.alignItems =
          { left: 'flex-start', center: 'center', right: 'flex-end' }[hAlign]
        return (
          <div
            key={child.id}
            className={`pv-composite-item pv-composite-item--${child.chart_type}`}
            style={style}
          >
            {child.title && <div className="pv-composite-item-title">{child.title}</div>}
            <div className="pv-composite-item-body" style={bodyStyle}>
              {hasAlignment ? (
                <div style={{ flex: '0 0 auto', maxWidth: '100%' }}>
                  <Child
                    data={child.data}
                    height={minHeight}
                    name={child.title || ''}
                  />
                </div>
              ) : (
                <Child
                  data={child.data}
                  height={minHeight}
                  name={child.title || ''}
                />
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
