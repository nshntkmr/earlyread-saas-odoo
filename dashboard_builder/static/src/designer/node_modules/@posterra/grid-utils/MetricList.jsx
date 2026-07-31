// MetricList — body-only renderer for the metric_list widget.
// Shared by portal AND designer preview. Card chrome is the host's job.
//
// Consumes the pure-formatter payload verbatim:
//   { type, items[], legend{mode,entries}, detail_label, progress{show,height,
//     track_color}, neutral, empty, empty_text, error }
// Every item: { key, label, raw_value, formatted_value, progress_fraction,
//   direction, detail, icon, status|null, out_of_range?, thresholds? }
//
// Accessibility: the bar carries role="progressbar" with aria-valuenow from
// the raw fraction; status is conveyed by TEXT (badge label) as well as
// color; direction feeds assistive text ("lower is better").

import React from 'react'
import './widgetCards.css'

const DIRECTION_TEXT = {
  lower_is_better: 'lower is better',
  higher_is_better: 'higher is better',
}

function Badge({ status, neutral }) {
  const s = status || neutral
  if (!s || !s.label) return null
  return (
    <span
      className="pvml-badge"
      style={{ color: s.color, background: s.background }}
    >
      <span className="pvml-badge-dot" style={{ background: s.color }} aria-hidden="true" />
      {s.label}
    </span>
  )
}

function Bar({ item, progress, statusColor }) {
  if (!progress.show || item.progress_fraction === null
      || item.progress_fraction === undefined) return null
  const pct = Math.max(0, Math.min(100, item.progress_fraction * 100))
  const dirText = DIRECTION_TEXT[item.direction]
  return (
    <div
      className="pvml-track"
      style={{ height: progress.height, background: progress.track_color }}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct)}
      aria-label={`${item.label}: ${item.formatted_value}${dirText ? `, ${dirText}` : ''}`}
    >
      <div
        className="pvml-fill"
        style={{ width: `${pct}%`, background: statusColor }}
      />
    </div>
  )
}

export default function MetricList({ data }) {
  if (!data) return null
  if (data.error) return null // host renders the standard error chip
  if (data.empty) {
    return <div className="pvml-empty text-muted">{data.empty_text || ''}</div>
  }

  const progress = data.progress || { show: true, height: 10, track_color: '#eef2f7' }
  const neutral = data.neutral || {}
  const legend = data.legend || { mode: 'hidden', entries: [] }

  return (
    <div className="pvml-host">
      {(data.items || []).map((item, i) => {
        const statusColor = (item.status && item.status.color) || neutral.color || '#6b7280'
        return (
          <div className="pvml-item" key={item.key || i}>
            <div className="pvml-row">
              <span className="pvml-label">
                {item.icon && item.icon.fa_class && (
                  <i className={`fa ${item.icon.fa_class} pvml-item-icon`} aria-hidden="true" />
                )}
                {item.label}
              </span>
              <span className="pvml-right">
                <Badge status={item.status} neutral={null} />
                <span className="pvml-value" style={{ color: statusColor }}>
                  {item.formatted_value}
                </span>
              </span>
            </div>
            <Bar item={item} progress={progress} statusColor={statusColor} />
            {item.out_of_range && (
              <div className="pvml-oor text-muted">value outside configured scale</div>
            )}
            {item.detail && (
              <div className="pvml-detail">
                {data.detail_label ? (
                  <span className="pvml-detail-label">{data.detail_label}: </span>
                ) : null}
                <span className="pvml-detail-text">{item.detail}</span>
              </div>
            )}
            {legend.mode === 'per_metric' && item.thresholds && item.thresholds.length > 0 && (
              <div className="pvml-thresholds">
                {item.thresholds.map((t) => (
                  <span key={t.key} className="pvml-legend-entry">
                    <span className="pvml-badge-dot" style={{ background: t.color }} aria-hidden="true" />
                    {t.label}{t.text ? ` · ${t.text}` : ''}
                  </span>
                ))}
              </div>
            )}
          </div>
        )
      })}
      {(legend.mode === 'numeric' || legend.mode === 'semantic')
        && legend.entries && legend.entries.length > 0 && (
        <div className="pvml-legend">
          {legend.entries.map((e) => (
            <span key={e.key} className="pvml-legend-entry">
              <span className="pvml-badge-dot" style={{ background: e.color }} aria-hidden="true" />
              {e.label}{legend.mode === 'numeric' && e.text ? ` · ${e.text}` : ''}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
