import React from 'react'

/**
 * KeyTakeaways — chart_type: "key_takeaways"
 *
 * A multi-row narrative list: each SQL row becomes one takeaway with a
 * severity-derived icon and color. All text comes from the admin's SQL —
 * nothing about the business narrative is hardcoded here.
 *
 * Expected data shape (built by dashboard.widget._build_key_takeaways_data):
 * {
 *   type: "key_takeaways",
 *   items: [
 *     { text: "Professional spend is the largest driver…",
 *       severity: "warning",
 *       icon_class: "fa fa-exclamation-circle",
 *       status_css: "status-warning" },
 *     ...
 *   ]
 * }
 *
 * The list body scrolls internally (CSS) so the widget fits inside a configured
 * equal-height card beside another widget without expanding past it.
 */
export default function KeyTakeaways({ data = {} }) {
  const items = Array.isArray(data.items) ? data.items : []

  if (!items.length) {
    return <div className="pv-takeaways-empty">No takeaways available.</div>
  }

  return (
    <ul className="pv-takeaways-list">
      {items.map((it, i) => {
        const sev = it.severity || 'neutral'
        return (
          <li key={i} className={`pv-takeaway-item ${it.status_css || 'status-neutral'}`}>
            <span className="pv-takeaway-badge" aria-hidden="true">
              <i className={it.icon_class || 'fa fa-circle-o'} />
            </span>
            {/* Severity is conveyed by icon + color (both aria-hidden) — expose
                it to assistive tech so color is never the only indicator. */}
            <span className="pv-sr-only">{`${sev} severity:`}</span>
            <span className="pv-takeaway-text">{it.text}</span>
          </li>
        )
      })}
    </ul>
  )
}
