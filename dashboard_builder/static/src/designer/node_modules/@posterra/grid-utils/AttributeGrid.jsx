// AttributeGrid — body-only renderer for the attribute_grid widget.
// Shared by portal AND designer preview (one implementation, identical UI).
// Card chrome (title/header/footnote) is the HOST's job — this renders the
// widget body only, so nested cards are impossible.
//
// Consumes the pure-formatter payload verbatim:
//   { type, data_shape, columns, density, leading_visual, items[], empty,
//     empty_text, error }
// Placement is resolved here through the shared placement.js function against
// the REAL container width (ResizeObserver) — the same math the designer
// preview runs, at 8/4/2/1 responsive steps.

import React, { useEffect, useRef, useState } from 'react'
import { effectiveColumns, resolvePlacement } from './placement'
import './widgetCards.css'

function Icon({ icon, style }) {
  if (!icon || !icon.fa_class) return null
  return (
    <span
      className="pvag-icon"
      style={style ? { color: style.foreground, background: style.background } : undefined}
      aria-hidden="true"
    >
      <i className={`fa ${icon.fa_class}`} />
    </span>
  )
}

function Value({ item }) {
  const cls = `pvag-value${item.emphasis === 'strong' ? ' pvag-value--strong' : ''}${item.is_null ? ' pvag-value--null' : ''}`
  if (item.link && item.link.href) {
    return (
      <a
        className={cls}
        href={item.link.href}
        target={item.link.new_tab ? '_blank' : undefined}
        rel={item.link.rel || undefined}
      >
        {item.value}
      </a>
    )
  }
  return <span className={cls}>{item.value}</span>
}

function LeadingVisual({ lv }) {
  if (!lv) return null
  return (
    <div
      className="pvag-leading"
      style={{ color: lv.foreground, background: lv.background }}
      aria-hidden="true"
    >
      {lv.mode === 'icon' && lv.icon
        ? <i className={`fa ${lv.icon.fa_class}`} />
        : <span className="pvag-leading-initials">{lv.text || ''}</span>}
    </div>
  )
}

export default function AttributeGrid({ data }) {
  const hostRef = useRef(null)
  const [width, setWidth] = useState(0)

  useEffect(() => {
    const el = hostRef.current
    if (!el || typeof ResizeObserver === 'undefined') return undefined
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) setWidth(e.contentRect.width)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  if (!data) return null
  if (data.error) {
    // Host renders data.error in its own error chip; render nothing extra.
    return null
  }
  if (data.empty) {
    return <div className="pvag-empty text-muted">{data.empty_text || ''}</div>
  }

  const cols = effectiveColumns(width, data.columns || 1)
  const items = resolvePlacement(data.items || [], cols)
  const dense = data.density === 'compact'

  return (
    <div ref={hostRef} className={`pvag-host${dense ? ' pvag-host--compact' : ''}`}>
      {data.leading_visual && <LeadingVisual lv={data.leading_visual} />}
      <div
        className="pvag-grid"
        style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
      >
        {items.map((item) => (
          <React.Fragment key={item.key}>
            {item.divider_before && (
              <div className="pvag-divider" style={{ gridColumn: `1 / span ${cols}` }} />
            )}
            <div
              className={`pvag-item pvag-item--${item.layout || 'stacked'}`}
              style={{
                gridColumn: `${item.resolved.col} / span ${item.resolved.span}`,
              }}
            >
              <Icon icon={item.icon} style={item.style} />
              <div className="pvag-item-body">
                <div className="pvag-label">{item.label}</div>
                <Value item={item} />
                {item.secondary_value && (
                  <div className="pvag-secondary text-muted">{item.secondary_value}</div>
                )}
              </div>
            </div>
          </React.Fragment>
        ))}
      </div>
    </div>
  )
}
