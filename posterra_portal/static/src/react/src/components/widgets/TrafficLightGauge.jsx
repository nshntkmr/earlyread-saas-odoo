import React from 'react'

/**
 * TrafficLightGauge
 *
 * Three circles (red/amber/green) with the active one highlighted.
 * Shows value, status badge, and threshold text.
 *
 * Expected data shape:
 * {
 *   gauge_variant: 'traffic_light_rag',
 *   value: 78.4,
 *   formatted_value: '78.4%',
 *   rag_status: 'green' | 'amber' | 'red',
 *   badge_text: 'On target',
 *   threshold_text: 'G: ≥85 | A: 70-85 | R: <70',
 *   label: 'Timely access (IP)',
 * }
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

export default function TrafficLightGauge({ data = {}, height }) {
  const {
    value = 0,
    formatted_value = '',
    rag_status = 'green',
    badge_text = '',
    threshold_text = '',
    label = '',
    label_font_weight,
    label_color,
    value_font_weight,
    value_color,
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
