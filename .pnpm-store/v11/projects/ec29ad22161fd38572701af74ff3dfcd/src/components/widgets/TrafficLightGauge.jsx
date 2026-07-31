import React from 'react'

/**
 * TrafficLightGauge
 *
 * Single-row: Three circles (red/amber/green) with the active one highlighted.
 * Multi-row:  List of metrics, each with a colored circle, value, and status text.
 *
 * Single-row data shape:
 * { gauge_variant, value, formatted_value, rag_status, badge_text, threshold_text, label }
 *
 * Multi-row data shape:
 * { gauge_variant, multi: true, items: [{ label, value, formatted_value, rag_status, status_text }] }
 */

const RAG_COLORS = {
  red:   { active: '#ef4444', bg: '#fecaca', border: '#ef4444' },
  amber: { active: '#f59e0b', bg: '#fde68a', border: '#f59e0b' },
  green: { active: '#10b981', bg: '#bbf7d0', border: '#10b981' },
}

const BADGE_BG = {
  red:   { bg: '#fef2f2', text: '#dc2626' },
  amber: { bg: '#fffbeb', text: '#d97706' },
  green: { bg: '#f0fdf4', text: '#16a34a' },
}


/* ── Multi-row: single metric line ─────────────────────────────── */

function RagRow({ label, formatted_value, rag_status, status_text, labelStyle, valueStyle }) {
  const colors = RAG_COLORS[rag_status] || RAG_COLORS.green
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '6px 0',
    }}>
      {/* RAG circle */}
      <div style={{
        width: 14,
        height: 14,
        borderRadius: '50%',
        backgroundColor: colors.active,
        flexShrink: 0,
      }} />

      {/* Metric name */}
      <span style={{
        fontWeight: 600,
        fontSize: 13,
        color: '#1f2937',
        minWidth: 120,
        ...labelStyle,
      }}>
        {label}
      </span>

      {/* Value */}
      <span style={{
        fontWeight: 600,
        fontSize: 13,
        color: '#374151',
        minWidth: 50,
        ...valueStyle,
      }}>
        {formatted_value}
      </span>

      {/* Status text */}
      {status_text && (
        <span style={{
          fontSize: 12,
          color: '#6b7280',
          marginLeft: 'auto',
        }}>
          {status_text}
        </span>
      )}
    </div>
  )
}


/* ── Main component ────────────────────────────────────────────── */

export default function TrafficLightGauge({ data = {}, height }) {
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
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        padding: '8px 16px',
        height: height || 'auto',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        overflow: 'auto',
      }}>
        {data.items.map((item, i) => (
          <RagRow
            key={i}
            label={item.label}
            formatted_value={item.formatted_value}
            rag_status={item.rag_status}
            status_text={item.status_text}
            labelStyle={labelStyle}
            valueStyle={valueStyle}
          />
        ))}
      </div>
    )
  }

  // ── Single-row mode (backward compatible) ───────────────────
  const {
    value = 0,
    formatted_value = '',
    rag_status = 'green',
    badge_text = '',
    threshold_text = '',
    label = '',
  } = data

  const circleOrder = ['red', 'amber', 'green']

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '16px 12px',
      height: height || 'auto',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    }}>
      {/* Label */}
      {label && (
        <div style={{
          fontSize: 13,
          fontWeight: label_font_weight || 600,
          color: label_color || '#1f2937',
          marginBottom: 12,
          textAlign: 'center',
        }}>
          {label}
        </div>
      )}

      {/* Three circles */}
      <div style={{
        display: 'flex',
        gap: 10,
        alignItems: 'center',
        marginBottom: 10,
      }}>
        {circleOrder.map(status => {
          const isActive = status === rag_status
          const colors = RAG_COLORS[status]
          return (
            <div
              key={status}
              style={{
                width: isActive ? 32 : 24,
                height: isActive ? 32 : 24,
                borderRadius: '50%',
                backgroundColor: isActive ? colors.active : colors.bg,
                border: `2px solid ${isActive ? colors.border : 'transparent'}`,
                transition: 'all 0.3s ease',
                opacity: isActive ? 1 : 0.5,
                boxShadow: isActive ? `0 0 8px ${colors.active}40` : 'none',
              }}
            />
          )
        })}
      </div>

      {/* Value */}
      <div style={{
        fontSize: 28,
        fontWeight: value_font_weight || 700,
        color: value_color || RAG_COLORS[rag_status]?.active || '#1f2937',
        lineHeight: 1.2,
        marginBottom: 6,
      }}>
        {formatted_value}
      </div>

      {/* Badge */}
      {badge_text && (
        <div style={{
          display: 'inline-block',
          padding: '3px 10px',
          borderRadius: 12,
          fontSize: 11,
          fontWeight: 600,
          backgroundColor: BADGE_BG[rag_status]?.bg || '#f3f4f6',
          color: BADGE_BG[rag_status]?.text || '#374151',
          marginBottom: 8,
        }}>
          {badge_text}
        </div>
      )}

      {/* Threshold text */}
      {threshold_text && (
        <div style={{
          fontSize: 10,
          color: '#9ca3af',
          textAlign: 'center',
          marginTop: 4,
        }}>
          {threshold_text}
        </div>
      )}
    </div>
  )
}
