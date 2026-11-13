import React from 'react'

const DEFAULT_LANES = [
  { key: 'new_alignments', label: 'New Alignments', color: '#14b8a6', y: 92, width: 26, badgeW: 70, badgeH: 30 },
  { key: 'still_active', label: 'Still Active', color: '#60a5fa', y: 198, width: 70, badgeW: 78, badgeH: 104 },
  { key: 'recaptured', label: 'Re-captured', color: '#8b5cf6', y: 302, width: 18, badgeW: 62, badgeH: 28 },
  { key: 'disaligned', label: 'Disaligned', color: '#ef4444', y: 358, width: 22, badgeW: 66, badgeH: 28 },
]

// Month columns are spread over a fixed band (FIRST_X..DEFAULT_LAST_X) while
// they fit. Each column needs MIN_STEP units: room for the widest value box
// (Still Active, 78) plus a visible ribbon, and for a month label (~65) plus
// the "->" arrow (~21) between two labels. Up to 8 months fit the band
// (685 / 7 = 98 per column), so those charts are drawn exactly as before.
// From 9 months on the canvas grows instead of squeezing the columns, the
// chart may shrink down to MIN_SCALE of its drawn size to fit the card, and
// below that the card scrolls sideways.
const VIEW_WIDTH = 1180
const FIRST_X = 285
const DEFAULT_LAST_X = 970
const MIN_STEP = 92
const MIN_SCALE = 0.85

// The right-hand lane labels start at lastX + 78 + 32 and are 15px bold
// (~7 units per character, measured). The widened canvas fills the card
// exactly, so it must end after the longest label (admins can rename lanes,
// e.g. "Ineligible➔Eligible") or that label is clipped at the card edge.
const rightLegendSpace = (laneLabels) => {
  const longest = Math.max(0, ...laneLabels.map(l => String(l || '').length))
  return Math.max(VIEW_WIDTH - DEFAULT_LAST_X, Math.ceil(78 + 32 + longest * 7.2 + 10))
}

const memberFlowLayout = (monthCount, laneLabels) => {
  const fitStep = monthCount > 1 ? (DEFAULT_LAST_X - FIRST_X) / (monthCount - 1) : 0
  if (monthCount <= 1 || fitStep >= MIN_STEP) {
    return { step: fitStep, lastX: DEFAULT_LAST_X, viewWidth: VIEW_WIDTH, widened: false }
  }
  const lastX = FIRST_X + MIN_STEP * (monthCount - 1)
  return { step: MIN_STEP, lastX, viewWidth: lastX + rightLegendSpace(laneLabels), widened: true }
}

const formatNumber = (value) => {
  const n = Number(value || 0)
  return Number.isFinite(n) ? new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(n) : '0'
}

const normalizeMonths = (data) => {
  const months = Array.isArray(data?.months) ? data.months : []
  return months
    .map((m, idx) => ({
      ...m,
      key: m.key || m.label || String(idx),
      label: m.label || m.Date || m.month_label || m.month || String(m.key || ''),
    }))
    .filter(m => m.label)
}

export default function MemberFlowTimeline({ data, height = 520 }) {
  const months = normalizeMonths(data)
  const labels = data?.labels || {}
  const lanes = DEFAULT_LANES.map(lane => ({
    ...lane,
    label: labels[lane.key] || lane.label,
  }))
  const chartHeight = Math.max(Number(height) || 520, 420)

  if (!months.length) {
    return (
      <div
        style={{
          minHeight: chartHeight,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#64748b',
          fontSize: 14,
        }}
      >
        No member flow data.
      </div>
    )
  }

  const { step, lastX, viewWidth, widened } = memberFlowLayout(months.length, lanes.map(l => l.label))
  const viewHeight = 430
  const startX = 30
  const startY = 176
  const startW = 150
  const startH = 94
  const firstX = FIRST_X
  const columnXs = months.map((_, idx) => firstX + idx * step)
  // Below this width the chart would shrink past MIN_SCALE, so the wrapper
  // (overflowX: auto) scrolls instead. 900 = the historical floor.
  const svgMinWidth = widened ? Math.round(viewWidth * MIN_SCALE) : 900
  const start = data?.start || {}
  const footer = data?.footer || 'Members must have a qualifying claim in the past 12 months to remain eligible.'
  const startTitle = String(start.label || 'Starting Aligned Members')
  const startLines = /aligned members/i.test(startTitle)
    ? ['Starting', 'Aligned Members']
    : [startTitle, '']

  const pathBetween = (x1, y1, x2, y2) => {
    const dx = Math.max((x2 - x1) * 0.45, 40)
    return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`
  }

  return (
    <div style={{ height: chartHeight, width: '100%', overflowX: 'auto', overflowY: 'hidden' }}>
      <svg
        viewBox={`0 0 ${viewWidth} ${viewHeight}`}
        width="100%"
        height="100%"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Monthly member flow"
        style={{ minWidth: svgMinWidth, display: 'block' }}
      >
        <defs>
          <filter id="member-flow-shadow" x="-15%" y="-15%" width="130%" height="130%">
            <feDropShadow dx="0" dy="2" stdDeviation="2" floodColor="#0f172a" floodOpacity="0.12" />
          </filter>
        </defs>

        <g transform="translate(230 24)">
          {lanes.map((lane, idx) => (
            <g key={lane.key} transform={`translate(${idx * 210} 0)`}>
              <rect x="0" y="0" width="18" height="18" rx="3" fill={lane.color} opacity="0.9" />
              <text x="28" y="14" fill="#1f2937" fontSize="14" fontWeight="600">{lane.label}</text>
            </g>
          ))}
        </g>

        {months.map((month, idx) => (
          <g key={`month-label-${month.key}`} transform={`translate(${columnXs[idx]} 74)`}>
            <text textAnchor="middle" fill="#334155" fontSize="14" fontWeight="700">{month.label}</text>
            {idx < months.length - 1 && (
              <text x={step / 2} y="2" textAnchor="middle" fill="#94a3b8" fontSize="18" fontWeight="700">-></text>
            )}
          </g>
        ))}

        <rect
          x={startX}
          y={startY}
          width={startW}
          height={startH}
          rx="6"
          fill="#9ee6d6"
          stroke="#78d6c2"
          filter="url(#member-flow-shadow)"
        />
        <text x={startX + startW / 2} y={startY + 28} textAnchor="middle" fill="#0f172a" fontSize="14" fontWeight="700">
          {startLines[0]}
        </text>
        {startLines[1] && (
          <text x={startX + startW / 2} y={startY + 48} textAnchor="middle" fill="#0f172a" fontSize="14" fontWeight="700">
            {startLines[1]}
          </text>
        )}
        <text x={startX + startW / 2} y={startY + 68} textAnchor="middle" fill="#0f172a" fontSize="13">
          {start.period || months[0].label}
        </text>
        <text x={startX + startW / 2} y={startY + 86} textAnchor="middle" fill="#0f172a" fontSize="14" fontWeight="700">
          {formatNumber(start.value)}
        </text>

        {lanes.map((lane) => (
          <g key={`ribbons-${lane.key}`}>
            <path
              d={pathBetween(startX + startW, startY + startH / 2, columnXs[0] - lane.badgeW / 2, lane.y)}
              fill="none"
              stroke={lane.color}
              strokeWidth={lane.width}
              strokeLinecap="round"
              opacity="0.18"
            />
            {months.slice(0, -1).map((month, idx) => (
              <path
                key={`${lane.key}-${month.key}`}
                d={pathBetween(columnXs[idx] + lane.badgeW / 2, lane.y, columnXs[idx + 1] - lane.badgeW / 2, lane.y)}
                fill="none"
                stroke={lane.color}
                strokeWidth={lane.width}
                strokeLinecap="round"
                opacity={lane.key === 'still_active' ? '0.16' : '0.22'}
              />
            ))}
          </g>
        ))}

        {months.map((month, idx) => {
          const x = columnXs[idx]
          return (
            <g key={`month-values-${month.key}`}>
              {lanes.map((lane) => {
                const isStill = lane.key === 'still_active'
                const y = lane.y
                return (
                  <g key={`${month.key}-${lane.key}`}>
                    <rect
                      x={x - lane.badgeW / 2}
                      y={y - lane.badgeH / 2}
                      width={lane.badgeW}
                      height={lane.badgeH}
                      rx={isStill ? 8 : 5}
                      fill={lane.color}
                      opacity={isStill ? '0.72' : '0.82'}
                      filter="url(#member-flow-shadow)"
                    />
                    <text
                      x={x}
                      y={y + 5}
                      textAnchor="middle"
                      fill={isStill ? '#0f172a' : '#ffffff'}
                      fontSize={isStill ? '15' : '14'}
                      fontWeight="700"
                    >
                      {formatNumber(month[lane.key])}
                    </text>
                  </g>
                )
              })}
            </g>
          )
        })}

        <g transform={`translate(${lastX + 78} 0)`}>
          {lanes.map(lane => (
            <g key={`right-${lane.key}`}>
              <path d={`M 0 ${lane.y} L 24 ${lane.y}`} stroke={lane.color} strokeWidth="3" strokeLinecap="round" />
              <text x="32" y={lane.y + 5} fill={lane.color} fontSize="15" fontWeight="700">{lane.label}</text>
            </g>
          ))}
        </g>

        <text x={viewWidth / 2} y="414" textAnchor="middle" fill="#64748b" fontSize="14">
          {footer}
        </text>
      </svg>
    </div>
  )
}
