/**
 * ComparisonBar — presentational component for KPI cards with progress bars.
 *
 * Renders the same HTML structure as the former QWeb comparison_bar template,
 * using identical CSS classes so existing styles apply unchanged.
 */
export default function ComparisonBar({ data }) {
  const cards = data?.cards || []
  if (cards.length === 0) return null

  return (
    <div className="pv-si-cards">
      {cards.map((card, i) => (
        <div
          key={i}
          className={`pv-si-card${card.status_class === 'strong' ? ' pv-si-card-active' : ''}`}
        >
          <div className="pv-si-card-header">
            <span className="pv-si-card-label">{card.label}</span>
            {card.status && (
              <span className={`pv-si-badge pv-si-badge-${card.status_class || 'neutral'}`}>
                {card.status}
              </span>
            )}
          </div>
          <div className="pv-si-stat">
            <span className="pv-si-value">{card.value}</span>
            {card.sublabel && (
              <span className="pv-si-sublabel">{card.sublabel}</span>
            )}
          </div>
          <div className="pv-si-bar-track">
            <div
              className={`pv-si-bar-fill ${card.bar_color || 'pv-bar-blue'}`}
              style={{ width: `${card.bar_pct || 0}%` }}
            />
          </div>
          {card.desc && <div className="pv-si-desc">{card.desc}</div>}
        </div>
      ))}
    </div>
  )
}
