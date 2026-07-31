import React from 'react'

/**
 * PercentileGauge
 *
 * Horizontal bar showing percentile position (0-100) with quartile markers.
 * Shows ordinal number, subtitle, quartile badge, and actual value.
 *
 * Expected data shape:
 * {
 *   gauge_variant: 'percentile_rank',
 *   percentile: 83,
 *   ordinal_text: '83rd',
 *   subtitle: 'Total admits this period',
 *   quartile_label: 'Top quartile',
 *   quartile_color: '#16a34a',
 *   actual_value: '468',
 *   actual_label: 'Volume leader',
 *   show_quartile_markers: true,
 *   label: 'Admits volume',
 * }
 */

const QUARTILE_BADGE_BG = {
  '#16a34a': '#f0fdf4',   // green
  '#2563eb': '#eff6ff',   // blue
  '#d97706': '#fffbeb',   // amber
  '#dc2626': '#fef2f2',   // red
}

export default function PercentileGauge({ data = {}, height }) {
  const {
    percentile = 0,
    ordinal_text = '',
    subtitle = '',
    quartile_label = '',
    quartile_color = '#16a34a',
    actual_value = '',
    actual_label = '',
    show_quartile_markers = true,
    label = '',
    label_font_weight,
    label_color,
    value_font_weight,
    value_color,
  } = data

  const pct = Math.max(0, Math.min(100, percentile))

  // Gradient colors for the bar: green → yellow → orange → red (right to left for percentile)
  const barGradient = 'linear-gradient(to right, #10b981, #34d399, #fbbf24, #f59e0b, #ef4444)'
  // Filled portion shows the gradient up to the percentile
  const filledGradient = `linear-gradient(to right, #10b981, ${percentile > 50 ? '#34d399' : '#fbbf24'}, ${quartile_color})`

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      padding: '14px 16px',
      height: height || 'auto',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    }}>
      {/* Header: label + quartile badge */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 6,
      }}>
        <span style={{ fontSize: 13, fontWeight: label_font_weight || 600, color: label_color || '#1f2937' }}>
          {label}
        </span>
        {quartile_label && (
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 4,
            fontSize: 10,
            fontWeight: 600,
            backgroundColor: QUARTILE_BADGE_BG[quartile_color] || '#f3f4f6',
            color: quartile_color,
            whiteSpace: 'nowrap',
          }}>
            {quartile_label}
          </span>
        )}
      </div>

      {/* Large ordinal number */}
      <div style={{
        fontSize: 32,
        fontWeight: value_font_weight || 700,
        color: value_color || quartile_color,
        lineHeight: 1.1,
        marginBottom: 2,
      }}>
        {ordinal_text}
      </div>

      {/* Subtitle */}
      {subtitle && (
        <div style={{
          fontSize: 12,
          color: '#6b7280',
          marginBottom: 10,
        }}>
          {subtitle}
        </div>
      )}

      {/* Progress bar */}
      <div style={{
        position: 'relative',
        width: '100%',
        height: 8,
        borderRadius: 4,
        backgroundColor: '#e5e7eb',
        overflow: 'visible',
        marginBottom: show_quartile_markers ? 20 : 8,
      }}>
        {/* Filled portion */}
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          height: '100%',
          width: `${pct}%`,
          borderRadius: 4,
          background: filledGradient,
          transition: 'width 0.6s ease',
        }} />

        {/* Position marker */}
        <div style={{
          position: 'absolute',
          left: `${pct}%`,
          top: -3,
          width: 4,
          height: 14,
          borderRadius: 2,
          backgroundColor: '#1f2937',
          transform: 'translateX(-2px)',
          zIndex: 2,
        }} />

        {/* Quartile markers */}
        {show_quartile_markers && [25, 50, 75].map(q => (
          <React.Fragment key={q}>
            <div style={{
              position: 'absolute',
              left: `${q}%`,
              top: 10,
              width: 1,
              height: 8,
              backgroundColor: '#9ca3af',
              transform: 'translateX(-0.5px)',
            }} />
            <span style={{
              position: 'absolute',
              left: `${q}%`,
              top: 20,
              fontSize: 9,
              color: '#9ca3af',
              transform: 'translateX(-50%)',
              whiteSpace: 'nowrap',
            }}>
              {q}th
            </span>
          </React.Fragment>
        ))}

        {/* 0th and 100th labels */}
        {show_quartile_markers && (
          <>
            <span style={{
              position: 'absolute',
              left: 0,
              top: 20,
              fontSize: 9,
              color: '#9ca3af',
            }}>
              0th
            </span>
            <span style={{
              position: 'absolute',
              right: 0,
              top: 20,
              fontSize: 9,
              color: '#9ca3af',
            }}>
              100th
            </span>
          </>
        )}
      </div>

      {/* Bottom: actual label + value */}
      {(actual_label || actual_value) && (
        <div style={{
          fontSize: 11,
          color: '#6b7280',
          marginTop: 4,
        }}>
          {actual_label}{actual_label && actual_value ? ' \u2014 ' : ''}
          {actual_value && (
            <span style={{ fontWeight: 600, color: '#374151' }}>
              actual: {actual_value}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
