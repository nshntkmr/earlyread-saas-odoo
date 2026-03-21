import React from 'react'
import { useFilters } from '../state/FilterContext'

/**
 * TabBar
 *
 * Renders Bootstrap nav-tabs from config.tabs.
 * Tab switching updates currentTabKey in FilterContext (no page reload).
 */
export default function TabBar() {
  const { config, currentTabKey, setCurrentTabKey } = useFilters()
  const tabs = config.tabs || []

  if (tabs.length === 0) return null

  return (
    <div className="pv-tab-bar">
      <ul className="nav nav-tabs pv-tabs" role="tablist">
        {tabs.map(tab => {
          const isActive = tab.key === currentTabKey || (!currentTabKey && tab === tabs[0])
          return (
            <li key={tab.id} className="nav-item" role="presentation">
              <button
                type="button"
                className={`nav-link pv-tab-link${isActive ? ' active' : ''}`}
                role="tab"
                aria-selected={isActive}
                onClick={() => setCurrentTabKey(tab.key)}
              >
                {tab.name}
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
