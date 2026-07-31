/**
 * ScopeDropdown — section-level scoping selector.
 *
 * Renders as a styled <select> in the section header (where the static
 * action_label badge used to be).  Changing the value triggers onScopeChange
 * without affecting the main filter bar.
 */
export default function ScopeDropdown({ label, options, value, onChange }) {
  if (!options || options.length === 0) return null

  return (
    <div className="pv-scope-dropdown">
      {label && <span className="pv-scope-label">{label}:</span>}
      <select
        className="pv-scope-select"
        value={value}
        onChange={e => onChange(e.target.value)}
      >
        <option value="">All</option>
        {options.map(opt => (
          <option key={opt.value} value={opt.value}>
            {opt.label || opt.value}
          </option>
        ))}
      </select>
    </div>
  )
}
