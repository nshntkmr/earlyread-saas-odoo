import { useRef, useEffect } from 'react'
import { useFilters } from '../state/FilterContext'

/**
 * Relocates server-rendered page sections from a hidden QWeb container
 * into React's component tree.
 *
 * Two instances are used in App.jsx:
 *   <SectionHost sourceId="sections-source" />
 *
 * Sections with no data-tab-key (page-level) are placed between
 * FilterBar and TabBar.  Sections with a data-tab-key (tab-level)
 * are placed between TabBar and WidgetGrid, shown only when the
 * matching tab is active.
 *
 * Props:
 *   placement — "page-level" or "tab-level"
 */
export default function SectionHost({ placement }) {
  const containerRef = useRef(null)
  const { currentTabKey } = useFilters()

  // On mount: relocate matching .pv-section elements from the hidden source
  useEffect(() => {
    const source = document.getElementById('sections-source')
    const container = containerRef.current
    if (!source || !container) return

    const isPageLevel = placement === 'page-level'
    const sections = source.querySelectorAll('.pv-section')
    sections.forEach(el => {
      const tabKey = el.dataset.tabKey || ''
      // page-level = sections with no tab assignment
      // tab-level  = sections with a tab assignment
      if (isPageLevel ? !tabKey : !!tabKey) {
        container.appendChild(el)
      }
    })
  }, [placement])

  // Show/hide tab-level sections based on active tab
  useEffect(() => {
    if (placement !== 'tab-level') return
    const container = containerRef.current
    if (!container) return

    const sections = container.querySelectorAll('.pv-section')
    sections.forEach(el => {
      const tabKey = el.dataset.tabKey || ''
      el.style.display = tabKey === currentTabKey ? '' : 'none'
    })
  }, [currentTabKey, placement])

  return <div ref={containerRef} className="pv-overview-sections" />
}
