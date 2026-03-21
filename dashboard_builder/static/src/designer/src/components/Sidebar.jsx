import React from 'react'

const NAV_ITEMS = [
  { key: 'library',   label: 'Widget Library', icon: 'fa-th-large' },
  { key: 'create',    label: 'Create Widget',  icon: 'fa-plus-circle' },
  { key: 'templates', label: 'Templates',      icon: 'fa-clone' },
]

/**
 * Sidebar — Left navigation for the Dashboard Designer.
 */
export default function Sidebar({ currentView, onNavigate, userName }) {
  return (
    <aside className="dd-sidebar">
      <div className="dd-sidebar-brand">
        <i className="fa fa-dashboard dd-brand-icon" />
        <span className="dd-brand-text">Dashboard Designer</span>
      </div>

      <nav className="dd-sidebar-nav">
        {NAV_ITEMS.map(item => (
          <button
            key={item.key}
            type="button"
            className={`dd-nav-item ${currentView === item.key ? 'dd-nav-item--active' : ''}`}
            onClick={() => onNavigate(item.key)}
          >
            <i className={`fa ${item.icon} dd-nav-icon`} />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="dd-sidebar-footer">
        <div className="dd-user-badge">
          <i className="fa fa-user-circle" />
          <span>{userName}</span>
        </div>
        <a href="/web" className="dd-back-link">
          <i className="fa fa-arrow-left" /> Back to Odoo
        </a>
      </div>
    </aside>
  )
}
