import React from 'react'

/**
 * BulletGauge
 *
 * Horizontal (or vertical) progress bar with colored range zones and a target marker.
 *
 * Expected data shape:
 * {
 *   gauge_variant: 'bullet',
 *   value: 78.4,
 *   formatted_value: '78.4%',
 *   target: 85,
 *   min: 0, max: 100,
 *   ranges: [{ to, color, label }],
 *   label: 'Timely access rate (IP referrals)',
 *   orientation: 'horizontal',
 *   bar_height: 12,
 *   threshold_text: 'Poor <70 | At risk 70-85 | On target >85',
 *   target_label: 'Target: ≥85%',
 * }
 */
export default function BulletGauge({ data = {}, height }) {
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
        <span style={{ fontWeight: 600, fontSize: 14, color: '#1f2937' }}>{label}</span>
        <span style={{ fontWeight: 700, fontSize: 18, color: '#0d9488' }}>{formatted_value}</span>
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
          top: 0,
          left: 0,
          width: isVertical ? bar_height + 12 : '100%',
          height: isVertical ? '100%' : bar_height + 12,
          borderRadius: 4,
          overflow: 'hidden',
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
            borderLeft: isVertical ? 'none' : '1px dashed #374151',
            borderBottom: isVertical ? '1px dashed #374151' : 'none',
          }}>
            {/* Target percentage label */}
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
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        marginTop: 6,
      }}>
        {threshold_text && (
          <span style={{ fontSize: 11, color: '#9ca3af' }}>{threshold_text}</span>
        )}
        {target_label && (
          <span style={{ fontSize: 11, color: '#6b7280', fontStyle: 'italic' }}>{target_label}</span>
        )}
      </div>

      {/* Min/Max labels */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        marginTop: 2,
      }}>
        <span style={{ fontSize: 10, color: '#9ca3af' }}>{min}%</span>
        <span style={{ fontSize: 10, color: '#9ca3af' }}>{max}%</span>
      </div>
    </div>
  )
}
