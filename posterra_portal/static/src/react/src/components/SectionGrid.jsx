import { useMemo } from 'react'
import { useFilters } from '../state/FilterContext'
import Section from './Section'

/**
 * SectionGrid — renders Section components filtered by placement.
 *
 * Two instances are used in App.jsx:
 *   <SectionGrid placement="page-level" ... />   — between FilterBar and TabBar
 *   <SectionGrid placement="tab-level" ... />     — between TabBar and WidgetGrid
 *
 * Page-level sections have no tab_key (empty string).
 * Tab-level sections have a tab_key and show only when that tab is active.
 */
export default function SectionGrid({ placement, initialSections, apiBase }) {
  const { currentTabKey } = useFilters()

  const sections = useMemo(() => {
    const all = Object.values(initialSections || {})
    const isPageLevel = placement === 'page-level'

    return all
      .filter(sec => {
        const hasTab = sec.tab_key && sec.tab_key !== ''
        if (isPageLevel) return !hasTab
        // Tab-level: show only sections matching the active tab
        return hasTab && sec.tab_key === currentTabKey
      })
      .sort((a, b) => (a.sequence || 0) - (b.sequence || 0))
  }, [initialSections, placement, currentTabKey])

  if (sections.length === 0) return null

  return (
    <div className="pv-overview-sections">
      {sections.map(sec => (
        <Section key={sec.id} config={sec} apiBase={apiBase} />
      ))}
    </div>
  )
}
