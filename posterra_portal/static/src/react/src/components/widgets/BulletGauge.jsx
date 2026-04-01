import React from 'react'

/**
 * BulletGauge
 *
 * Horizontal (or vertical) progress bar with colored range zones and a target marker.
 * Supports multi-row: when data.multi=true, renders stacked bullet rows.
 *
 * Single-row data shape:
 * {
 *   gauge_variant: 'bullet',
 *   value, formatted_value, target, min, max, ranges, label,
 *   orientation, bar_height, threshold_text, target_label,
 * }
 *
 * Multi-row data shape:
 * {
 *   gauge_variant: 'bullet', multi: true,
 *   items: [{ label, value, formatted_value, target, target_label }],
 *   min, max, ranges, bar_height, orientation, threshold_text,
 * }
 */

/* ── Single bullet row ─────────────────────────────────────────── */

function BulletRow({ label, value, formatted_value, target, target_label,
                     min, max, ranges, bar_height, labelStyle, valueStyle }) {
  const range_val = max - min || 1
  const valuePct = Math.max(0, Math.min(100, ((value - min) / range_val) * 100))
  const targetPct = target != null
    ? Math.max(0, Math.min(100, ((target - min) / range_val) * 100))
    : null

  return (
    <div>
      {/* Label + value */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        marginBottom: 4,
      }}>
        <span style={{ fontWeight: 600, fontSize: 13, color: '#1f2937', ...labelStyle }}>{label}</span>
        <span style={{ fontWeight: 700, fontSize: 16, color: '#0d9488', ...valueStyle }}>{formatted_value}</span>
      </div>

      {/* Bar */}
      <div style={{ position: 'relative', width: '100%', height: bar_height + 10 }}>
        {/* Range zones background */}
        <div style={{
          position: 'absolute', top: 0, left: 0,
          width: '100%', height: bar_height + 10,
          borderRadius: 3, overflow: 'hidden',
          display: 'flex',
        }}>
          {ranges.map((r, i) => {
            const prevTo = i > 0 ? ranges[i - 1].to : min
            const segPct = ((r.to - prevTo) / range_val) * 100
            return (
              <div key={i} style={{
                width: `${segPct}%`,
                backgroundColor: r.color || '#e5e7eb',
                opacity: 0.25,
              }} />
            )
          })}
        </div>

        {/* Actual value bar */}
        <div style={{
          position: 'absolute', left: 0, top: 3,
          width: `${valuePct}%`, height: bar_height,
          borderRadius: 2,
          backgroundColor: '#0d9488',
          transition: 'width 0.5s ease',
        }} />

        {/* Target marker */}
        {targetPct != null && (
          <div style={{
            position: 'absolute',
            left: `${targetPct}%`,
            top: 0,
            height: bar_height + 10,
            width: 2,
            backgroundColor: '#1f2937',
          }} />
        )}
      </div>

      {/* Target label (right-aligned under bar) */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        marginTop: 2,
      }}>
        <span style={{ fontSize: 10, color: '#9ca3af' }}>
          {formatted_value}
        </span>
        {target_label && (
          <span style={{ fontSize: 10, color: '#6b7280' }}>{target_label}</span>
        )}
      </div>
    </div>
  )
}


/* ── Main component ────────────────────────────────────────────── */

export default function BulletGauge({ data = {}, height }) {
  const {
    label_font_weight,
    label_color,
    value_font_weight,
    value_color,
  } = data

  const labelStyle = {
    ...(label_font_weight && { fontWeight: label_font_weight }),
    ...(label_color && { color: label_color }),
  }
  const valueStyle = {
    ...(value_font_weight && { fontWeight: value_font_weight }),
    ...(value_color && { color: value_color }),
  }

  // ── Multi-row mode ──────────────────────────────────────────
  if (data.multi && data.items) {
    const { items, min = 0, max = 100, ranges = [], bar_height = 12, threshold_text = '' } = data
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        padding: '12px 16px',
        height: height || 'auto',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        overflow: 'auto',
      }}>
        {items.map((item, i) => (
          <BulletRow
            key={i}
            label={item.label}
            value={item.value}
            formatted_value={item.formatted_value}
            target={item.target}
            target_label={item.target_label}
            min={min}
            max={max}
            ranges={ranges}
            bar_height={bar_height}
            labelStyle={labelStyle}
            valueStyle={valueStyle}
          />
        ))}
        {/* Shared threshold text at bottom */}
        {threshold_text && (
          <div style={{ fontSize: 11, color: '#9ca3af', borderTop: '1px solid #f3f4f6', paddingTop: 6 }}>
            {threshold_text}
          </div>
        )}
      </div>
    )
  }

  // ── Single-row mode (backward compatible) ───────────────────
  const {
    value = 0,
    formatted_value = '',
    target,
    min = 0,
    max = 100,
    ranges = [],
    label = '',
    orientation = 'horizontal',
    bar_height = 12,
    threshold_text = '',
    target_label = '',
  } = data

  const range_val = max - min || 1
  const pct = ((value - min) / range_val) * 100
  const valuePct = Math.max(0, Math.min(100, pct))
  const targetPct = target != null ? Math.max(0, Math.min(100, ((target - min) / range_val) * 100)) : null

  const isVertical = orientation === 'vertical'

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      padding: '12px 16px',
      height: height || 'auto',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    }}>
      {/* Title + value row */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        marginBottom: 8,
      }}>
        <span style={{ fontWeight: 600, fontSize: 14, color: '#1f2937', ...labelStyle }}>{label}</span>
        <span style={{ fontWeight: 700, fontSize: 18, color: '#0d9488', ...valueStyle }}>{formatted_value}</span>
      </div>

      {/* Bullet bar */}
      <div style={{
        position: 'relative',
        width: '100%',
        height: isVertical ? (height ? height - 80 : 120) : (bar_height + 12),
        ...(isVertical ? { display: 'flex', flexDirection: 'column-reverse' } : {}),
      }}>
        {/* Range zones background */}
        <div style={{
          position: isVertical ? 'relative' : 'absolute',
          top: 0, left: 0,
          width: isVertical ? bar_height + 12 : '100%',
          height: isVertical ? '100%' : bar_height + 12,
          borderRadius: 4, overflow: 'hidden',
          display: 'flex',
          flexDirection: isVertical ? 'column-reverse' : 'row',
        }}>
          {ranges.map((r, i) => {
            const prevTo = i > 0 ? ranges[i - 1].to : min
            const segPct = ((r.to - prevTo) / range_val) * 100
            return (
              <div key={i} style={{
                [isVertical ? 'height' : 'width']: `${segPct}%`,
                backgroundColor: r.color || '#e5e7eb',
                opacity: 0.25,
              }} />
            )
          })}
        </div>

        {/* Actual value bar */}
        <div style={{
          position: 'absolute',
          [isVertical ? 'bottom' : 'left']: 0,
          [isVertical ? 'left' : 'top']: isVertical ? 3 : 3,
          [isVertical ? 'height' : 'width']: `${valuePct}%`,
          [isVertical ? 'width' : 'height']: bar_height,
          borderRadius: 3,
          backgroundColor: '#0d9488',
          transition: 'width 0.6s ease, height 0.6s ease',
        }} />

        {/* Target marker */}
        {targetPct != null && (
          <div style={{
            position: 'absolute',
            [isVertical ? 'bottom' : 'left']: `${targetPct}%`,
            [isVertical ? 'left' : 'top']: 0,
            [isVertical ? 'width' : 'height']: bar_height + 12,
            [isVertical ? 'height' : 'width']: 2,
            backgroundColor: '#374151',
          }}>
            <span style={{
              position: 'absolute',
              [isVertical ? 'left' : 'top']: isVertical ? bar_height + 16 : -16,
              fontSize: 10,
              color: '#374151',
              whiteSpace: 'nowrap',
            }}>
              {target}%
            </span>
          </div>
        )}
      </div>

      {/* Threshold text + target label */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
        {threshold_text && <span style={{ fontSize: 11, color: '#9ca3af' }}>{threshold_text}</span>}
        {target_label && <span style={{ fontSize: 11, color: '#6b7280', fontStyle: 'italic' }}>{target_label}</span>}
      </div>

      {/* Min/Max labels */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
        <span style={{ fontSize: 10, color: '#9ca3af' }}>{min}%</span>
        <span style={{ fontSize: 10, color: '#9ca3af' }}>{max}%</span>
      </div>
    </div>
  )
}
