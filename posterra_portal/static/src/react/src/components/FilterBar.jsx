import React, { useState, useCallback, useMemo } from 'react'
import { useFilters } from '../state/FilterContext'
import { apiFetch } from '../api/client'
import { cascadeMultiUrl, cascadeUrl, filtersResolveUrl } from '../api/endpoints'
import MultiSelectDropdown from './MultiSelectDropdown'
import SearchableSelect from './SearchableSelect'

/**
 * FilterBar
 *
 * Renders one dropdown per active page filter + Apply button.
 *
 * Supports multi-directional filter dependencies via the filter_dependencies
 * graph from the page config.  When a filter changes, all targets in the
 * dependency graph are refreshed.  Infinite loops are prevented by a
 * "visited set" pattern — each cascade wave tracks which filter IDs have
 * already been processed and skips them on revisit.
 *
 * Falls back to legacy depends_on_field_name cascade when no
 * filter_dependencies are configured.
 */
export default function FilterBar() {
  const { config, pendingValues, setPendingFilter, applyFilters, accessToken, refreshToken, apiBase } = useFilters()
  const { filters = [], filter_dependencies = [] } = config

  // Dynamic options for cascaded filters (filter.id → [{value, label}])
  const [dynamicOptions, setDynamicOptions] = useState({})

  // ── Build dependency graph lookup maps ──────────────────────────────────
  const { sourceToTargets, targetToSources, filtersById, useNewDeps } = useMemo(() => {
    const s2t = new Map()  // sourceId → [{targetId, targetParam, propagation, resets_target}]
    const t2s = new Map()  // targetId → [{sourceId, sourceParam}]
    const byId = new Map()

    for (const f of filters) {
      byId.set(f.id, f)
    }

    const hasNewDeps = filter_dependencies.length > 0

    for (const dep of filter_dependencies) {
      // sourceToTargets — resolve targetParam with fallback to filter's param_name
      const tgtFilter = byId.get(dep.target_filter_id)
      if (!s2t.has(dep.source_filter_id)) s2t.set(dep.source_filter_id, [])
      s2t.get(dep.source_filter_id).push({
        targetId: dep.target_filter_id,
        targetParam: dep.target_param
          || (tgtFilter && (tgtFilter.param_name || tgtFilter.field_name))
          || '',
        propagation: dep.propagation,
        resets_target: dep.resets_target,
      })
      // targetToSources — resolve sourceParam with fallback to filter's param_name
      if (!t2s.has(dep.target_filter_id)) t2s.set(dep.target_filter_id, [])
      const srcFilter = byId.get(dep.source_filter_id)
      t2s.get(dep.target_filter_id).push({
        sourceId: dep.source_filter_id,
        sourceParam: dep.source_param
          || (srcFilter && (srcFilter.param_name || srcFilter.field_name))
          || '',
      })
    }

    return { sourceToTargets: s2t, targetToSources: t2s, filtersById: byId, useNewDeps: hasNewDeps }
  }, [filters, filter_dependencies])

  // ── Pending values ref for reading latest values during async cascade ──
  // We use a ref to avoid stale closures in the recursive cascade.
  const pendingRef = React.useRef(pendingValues)
  pendingRef.current = pendingValues

  // ── Legacy: recursively reset all descendant filters ───────────────────
  const resetDescendantsLegacy = useCallback((parentParamName) => {
    const descendants = filters.filter(f =>
      f.depends_on_field_name === parentParamName
    )
    for (const desc of descendants) {
      const descParam = desc.param_name || desc.field_name
      setPendingFilter(descParam, '')
      setDynamicOptions(prev => ({ ...prev, [desc.id]: [] }))
      resetDescendantsLegacy(descParam)
    }
  }, [filters, setPendingFilter])

  // ── Legacy cascade handler ─────────────────────────────────────────────
  const handleLegacyCascade = useCallback(async (filter, newValue) => {
    const paramKey = filter.param_name || filter.field_name
    setPendingFilter(paramKey, newValue)

    const childFilters = filters.filter(f => f.depends_on_field_name === paramKey)
    for (const child of childFilters) {
      const childParam = child.param_name || child.field_name
      try {
        const url = cascadeUrl(apiBase, child.id, newValue)
        const data = await apiFetch(url, accessToken, {}, refreshToken)
        setDynamicOptions(prev => ({ ...prev, [child.id]: data.options || [] }))
        setPendingFilter(childParam, '')
        resetDescendantsLegacy(childParam)
      } catch (err) {
        console.warn('Cascade fetch failed for filter', child.id, err)
      }
    }
  }, [filters, setPendingFilter, apiBase, accessToken, refreshToken, resetDescendantsLegacy])

  // ── New graph-based cascade handler ────────────────────────────────────
  // Uses a mutable `valuesSnapshot` to track all values set during this
  // cascade wave.  This avoids reading stale React state (setPendingFilter
  // is async) when building constraints for deeply nested cascades.
  //
  // Two-phase processing: first fetch options for ALL direct targets of the
  // source filter, THEN recurse into each target's children.  This prevents
  // a recursive branch from consuming visited-set slots before sibling
  // targets (including reverse/bidirectional edges) are processed.
  const handleGraphCascade = useCallback(async (filter, newValue, visitedSet, valuesSnapshot) => {
    const visited = visitedSet || new Set()
    // On first call, snapshot current pending values; on recursion, reuse.
    const snapshot = valuesSnapshot || { ...pendingRef.current }
    const isRoot = !visitedSet

    visited.add(filter.id)

    const paramKey = filter.param_name || filter.field_name
    setPendingFilter(paramKey, newValue)
    snapshot[paramKey] = newValue  // keep snapshot in sync

    const targets = sourceToTargets.get(filter.id) || []

    // Pre-clear ALL reachable filters with resets_target=True, not just
    // direct targets.  In bidirectional/cyclic graphs, a filter reachable
    // through a chain of edges would otherwise contribute stale constraint
    // values (e.g., switching from a CA to TX provider would still see
    // County=LA and City=Burbank when refreshing State's options).
    // This walk runs ONLY on the root call — recursive calls reuse the
    // already-cleared snapshot.
    if (isRoot) {
      const toReset = new Set()
      const seen = new Set([filter.id])
      const stack = [filter.id]
      while (stack.length > 0) {
        const nodeId = stack.pop()
        const edges = sourceToTargets.get(nodeId) || []
        for (const edge of edges) {
          if (seen.has(edge.targetId)) continue
          seen.add(edge.targetId)
          if (edge.resets_target) toReset.add(edge.targetId)
          stack.push(edge.targetId)  // keep walking even if this edge doesn't reset
        }
      }
      for (const resetId of toReset) {
        const tf = filtersById.get(resetId)
        if (tf) {
          const tp = tf.param_name || tf.field_name
          if (tp && snapshot[tp]) {
            console.debug(`[CASCADE]   pre-clear reachable target: ${tp} (was "${snapshot[tp]}")`)
            snapshot[tp] = ''
          }
        }
      }
    }

    if (isRoot) {
      console.debug(`[CASCADE] ▶ START: filter=${filter.name}(id=${filter.id}, param=${paramKey}), value="${newValue}", targets=${targets.length}`)
      console.debug(`[CASCADE]   snapshot:`, { ...snapshot })
    }

    // ── Phase 1: Process all direct targets (fetch options, handle resets) ──
    const processedTargets = []  // [{targetFilter, edge, targetParam}]

    for (const edge of targets) {
      if (visited.has(edge.targetId)) {
        console.debug(`[CASCADE]   ⏭ SKIP target=${edge.targetId} (already visited)`)
        continue  // cycle prevention
      }

      const targetFilter = filtersById.get(edge.targetId)
      if (!targetFilter) {
        console.debug(`[CASCADE]   ⚠ target=${edge.targetId} not found in filtersById`)
        continue
      }

      const targetParam = edge.targetParam || targetFilter.param_name || targetFilter.field_name

      // propagation=optional: skip if target already has an explicit user selection
      if (edge.propagation === 'optional' && snapshot[targetParam] && snapshot[targetParam] !== 'all') {
        console.debug(`[CASCADE]   ⏭ SKIP target=${targetFilter.name} (propagation=optional, has value="${snapshot[targetParam]}")`)
        continue
      }

      visited.add(edge.targetId)

      // Build constraint dict from ALL sources of this target,
      // reading values from the snapshot (not stale React state).
      const sources = targetToSources.get(edge.targetId) || []
      const constraints = {}
      for (const src of sources) {
        // Resolve source param with fallback to the filter's own param_name
        const srcParam = src.sourceParam
          || (filtersById.get(src.sourceId) || {}).param_name
          || (filtersById.get(src.sourceId) || {}).field_name
          || ''
        const val = srcParam ? (snapshot[srcParam] || '') : ''
        if (val && val !== 'all') {
          constraints[src.sourceId] = val
        }
      }

      // Build allValues from snapshot (param_name → value) for full-state scoping
      const allValues = {}
      for (const [p, v] of Object.entries(snapshot)) {
        if (v && v !== 'all') {
          allValues[p] = v
        }
      }

      console.debug(`[CASCADE]   → target=${targetFilter.name}(id=${edge.targetId}), constraints=`, constraints, `, resets=${edge.resets_target}, propagation=${edge.propagation}`)

      // Fetch new options for this target
      let opts = []
      try {
        const url = cascadeMultiUrl(apiBase, edge.targetId, constraints, allValues)
        console.debug(`[CASCADE]     GET ${url}`)
        const data = await apiFetch(url, accessToken, {}, refreshToken)
        opts = data.options || []
        console.debug(`[CASCADE]     ✓ ${opts.length} options returned for target=${targetFilter.name}`)
        setDynamicOptions(prev => ({ ...prev, [edge.targetId]: opts }))
      } catch (err) {
        console.warn('[CASCADE]     ✗ Cascade/multi fetch FAILED for filter', edge.targetId, err)
      }

      // Handle target value based on resets_target
      if (edge.resets_target) {
        let autoVal = ''
        if (opts.length === 1 && !targetFilter.include_all_option) {
          // Exactly 1 option, no "All" → auto-select it
          autoVal = opts[0].value
        } else if (
          targetFilter.is_multiselect &&
          opts.length > 1 &&
          !targetFilter.include_all_option
        ) {
          // Multi-select with 2+ real options, no "All" → select ALL as CSV
          autoVal = opts.map(o => o.value).filter(Boolean).join(',')
        }
        // else: 0 options or has include_all_option → reset to '' (user chooses)
        setPendingFilter(targetParam, autoVal)
        snapshot[targetParam] = autoVal
      } else {
        // Keep current value, but remove it if no longer in refreshed options
        const currentVal = snapshot[targetParam] || ''
        if (currentVal && opts.length > 0) {
          if (targetFilter.is_multiselect && currentVal.includes(',')) {
            // Multi-select: prune individual CSV values not in new options
            const validValues = new Set(opts.map(o => o.value))
            const kept = currentVal.split(',').filter(v => validValues.has(v.trim()))
            const prunedVal = kept.join(',')
            if (prunedVal !== currentVal) {
              setPendingFilter(targetParam, prunedVal)
              snapshot[targetParam] = prunedVal
            }
          } else {
            // Single-select: clear if value not in new options
            const stillValid = opts.some(o => o.value === currentVal)
            if (!stillValid) {
              setPendingFilter(targetParam, '')
              snapshot[targetParam] = ''
            }
          }
        }
      }

      processedTargets.push({ targetFilter, edge, targetParam })
    }

    // ── Phase 2: Recurse into each processed target's children ─────────────
    for (const { targetFilter, edge, targetParam } of processedTargets) {
      const targetCurrentValue = snapshot[targetParam] || ''
      await handleGraphCascade(targetFilter, targetCurrentValue, visited, snapshot)
    }

    if (isRoot) {
      console.debug(`[CASCADE] ◼ END: filter=${filter.name}`)
    }
  }, [sourceToTargets, targetToSources, filtersById, setPendingFilter, apiBase, accessToken, refreshToken])

  // ── Batch cascade handler (single HTTP call) ─────────────────────────
  const handleBatchCascade = useCallback(async (filter, newValue) => {
    const paramKey = filter.param_name || filter.field_name
    setPendingFilter(paramKey, newValue)

    const pageId = config.page?.id
    if (!pageId) {
      console.warn('[CASCADE-BATCH] No page_id in config, falling back to graph cascade')
      await handleGraphCascade(filter, newValue, null, null)
      return
    }

    // Build current_values from pending state
    const currentValues = { ...pendingRef.current, [paramKey]: newValue }

    console.debug(`[CASCADE-BATCH] ▶ START: filter=${filter.name}(id=${filter.id}), value="${newValue}"`)

    try {
      const url = filtersResolveUrl(apiBase)
      const data = await apiFetch(url, accessToken, {
        method: 'POST',
        body: JSON.stringify({
          page_id: pageId,
          changed_filter_id: filter.id,
          changed_value: newValue,
          current_values: currentValues,
        }),
      }, refreshToken)

      const updated = data.updated_filters || {}
      const filterCount = Object.keys(updated).length
      console.debug(`[CASCADE-BATCH] ✓ ${filterCount} filters updated`)

      // Apply all updates in one sweep
      for (const [filterId, info] of Object.entries(updated)) {
        // Update options
        setDynamicOptions(prev => ({
          ...prev,
          [parseInt(filterId, 10)]: info.options || [],
        }))
        // Update value if changed
        if (info.value_changed) {
          setPendingFilter(info.param_name, info.new_value)
        }
      }

      console.debug(`[CASCADE-BATCH] ◼ END: filter=${filter.name}`)
    } catch (err) {
      console.warn('[CASCADE-BATCH] ✗ Batch resolve failed, falling back to graph cascade:', err)
      // Graceful fallback to the per-target cascade
      await handleGraphCascade(filter, newValue, null, null)
    }
  }, [config, setPendingFilter, apiBase, accessToken, refreshToken, handleGraphCascade])

  // ── Unified handler: picks batch → graph → legacy path ────────────────
  const handleFilterChange = useCallback(async (filter, newValue) => {
    if (useNewDeps) {
      await handleBatchCascade(filter, newValue)
    } else {
      await handleLegacyCascade(filter, newValue)
    }
  }, [useNewDeps, handleBatchCascade, handleLegacyCascade])

  // ── Clear All handler ──────────────────────────────────────────────
  const handleClearAll = useCallback(() => {
    filters
      .filter(f => f.is_visible !== false)
      .forEach(f => {
        const key = f.param_name || f.field_name
        if (key) setPendingFilter(key, '')
      })
    // Reset dynamic options so dropdowns fall back to the original
    // unfiltered server options (filter.options from page load).
    setDynamicOptions({})
  }, [filters, setPendingFilter])

  if (!filters.length) return null

  return (
    <div className="pv-ctx-filter-bar">

      {/* ── All visible filters ──────────────────────────────────────── */}
      {filters.filter(f => f.is_visible !== false).map(filter => {
        const options = dynamicOptions[filter.id] ?? filter.options ?? []
        const paramKey = filter.param_name || filter.field_name
        const currentValue = pendingValues[paramKey] || ''

        return (
          <div key={filter.id} className="pv-ctx-filter-group">
            <label className="pv-ctx-filter-label" htmlFor={`ctx-${paramKey}-select`}>
              {filter.name}
            </label>
            {filter.is_multiselect ? (
              <MultiSelectDropdown
                options={options}
                value={currentValue}
                onChange={(csv) => handleFilterChange(filter, csv)}
                searchable={filter.is_searchable}
                placeholder={filter.placeholder || 'All'}
              />
            ) : filter.is_searchable ? (
              <SearchableSelect
                options={options}
                value={currentValue}
                onChange={(val) => handleFilterChange(filter, val)}
                placeholder={filter.placeholder || 'All'}
                includeAllOption={!filter.include_all_option}
              />
            ) : (
              <select
                id={`ctx-${paramKey}-select`}
                className="pv-ctx-select"
                data-filter-id={filter.id}
                data-field-name={paramKey}
                value={currentValue}
                onChange={e => handleFilterChange(filter, e.target.value)}
              >
                {!filter.include_all_option && (
                  <option value="">All</option>
                )}
                {options.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            )}
          </div>
        )
      })}

      {/* ── Clear All + Apply buttons ────────────────────────────────── */}
      <div className="pv-ctx-filter-group pv-ctx-apply-group">
        <button
          type="button"
          className="btn btn-outline-secondary pv-ctx-clear-btn"
          id="ctx-clear-btn"
          onClick={handleClearAll}
        >
          Clear All
        </button>
        <button
          type="button"
          className="btn btn-primary pv-ctx-apply-btn"
          id="ctx-apply-btn"
          onClick={applyFilters}
        >
          Apply
        </button>
      </div>
    </div>
  )
}
