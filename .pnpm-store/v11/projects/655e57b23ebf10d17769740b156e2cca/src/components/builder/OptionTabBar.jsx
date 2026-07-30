import React from 'react'

/**
 * OptionTabBar — renders toggle option tabs at the top of builder steps.
 *
 * Shown in Steps 2-5 when widget has scope options configured.
 * Each tab represents one toggle option (e.g., Hospitals, Physicians, All).
 * Clicking a tab switches which option's config is being edited.
 */
export default function OptionTabBar({ options, activeIdx, onSelect }) {
  if (!options || options.length === 0) return null

  return (
    <div className="wb-option-tabs">
      {options.map((opt, idx) => (
        <button
          key={idx}
          className={`wb-option-tab${idx === activeIdx ? ' active' : ''}`}
          onClick={() => onSelect(idx)}
          type="button"
        >
          {opt.icon && <i className={`fa ${opt.icon} me-1`} />}
          {opt.label || `Option ${idx + 1}`}
        </button>
      ))}
    </div>
  )
}
