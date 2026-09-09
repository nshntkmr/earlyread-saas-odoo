import React, { useEffect, useState, useRef, useCallback } from 'react'
import { ComplianceStrip } from '@posterra/grid-utils'
import DrawerChartSection from './DrawerChartSection'
import { formatDrawerChartValue } from './drawerChartOptions'
import ProjectionControls, { monthLabel } from './ProjectionControls'

/**
 * DetailDrawer — generic, config-driven row-detail drawer for table widgets.
 *
 * Controlled component that replicates PageHelpDrawer's shell *pattern*
 * (backdrop, Esc-to-close, scroll-lock, role="dialog", focus) — it does NOT
 * mount PageHelpDrawer. Renders from the SQL-stripped render schema
 * (`schema` = data.detail_drawer). `master_row` sections render instantly from
 * the clicked row; `source:"sql"` sections are loaded in ONE request via
 * `fetchDetail(rowKey)` → { sections: { <id>: { rows: [...] } | { error } } }.
 *
 * Member-360 is one configuration (preset) of this component.
 *
 * Projections ("Mark Projected Compliant"): a `measure_cards` section whose
 * `card.projection` block names a Projection Type gets, from the server
 * overlay, per-row outcomes + capability flags and `projections` /
 * `projection_meta`. The card renders ProjectionControls from those; saves go
 * through `projectionApi.mutate(action, body)` (provided by WidgetGrid), then
 * the drawer refetches itself and calls `onProjectionSaved()` so consumer
 * widgets refresh. While open, the drawer refetches every
 * `projection_meta.poll_seconds` (page visible) so other users' changes and
 * new monthly data show up; typed drafts survive those refreshes.
 */

// Replace {token} with row[token]; missing tokens degrade to '' (never a raw {token}).
function fillTemplate(tpl, row) {
  if (!tpl) return ''
  return tpl.replace(/\{([^}]+)\}/g, (_, k) => {
    const v = row?.[k.trim()]
    return v == null ? '' : String(v)
  })
}

const C = {
  backdrop: { position: 'fixed', inset: 0, background: 'rgba(15,23,42,.5)', zIndex: 400,
    display: 'flex', justifyContent: 'flex-end' },
  drawer: { background: '#fff', width: 560, maxWidth: '100vw', height: '100vh', overflowY: 'auto',
    boxShadow: '-6px 0 30px rgba(0,0,0,.25)' },
  header: { background: 'linear-gradient(135deg, var(--pv-primary-dark,#004d99), var(--pv-primary,#0066cc))',
    color: '#fff', padding: '18px 20px', display: 'flex', alignItems: 'flex-start',
    justifyContent: 'space-between', position: 'sticky', top: 0, zIndex: 10 },
  close: { background: 'rgba(255,255,255,.15)', border: 'none', color: '#fff', fontSize: 16,
    cursor: 'pointer', width: 30, height: 30, borderRadius: 7, lineHeight: 1 },
  secTitle: { fontSize: 11, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '.06em',
    color: 'var(--pv-primary,#0066cc)', marginBottom: 11, paddingBottom: 6,
    borderBottom: '2px solid var(--pv-primary-l,#e6f0fb)' },
  grid2: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 11 },
  diLbl: { fontSize: 11, color: '#6b7280', marginBottom: 2 },
  diVal: { fontSize: 13, fontWeight: 600 },
  chip: { borderRadius: 6, padding: '4px 11px', fontSize: 11, fontWeight: 700, display: 'inline-block' },
  errChip: { background: '#f8d7da', color: '#721c24', borderRadius: 7, padding: '8px 11px',
    fontSize: 12, marginBottom: 10 },
  bdgOk: { background: '#d4edda', color: '#155724' },
  bdgBad: { background: '#f8d7da', color: '#721c24' },
  bdgGrey: { background: '#f3f4f6', color: '#6b7280' },
  notice: { background: '#eff6ff', border: '1px solid #bfdbfe', color: '#1e3a8a', borderRadius: 7,
    padding: '8px 11px', fontSize: 12, marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 },
  noticeBtn: { fontSize: 12, padding: '3px 9px', borderRadius: 6, border: '1px solid #93c5fd',
    background: '#fff', cursor: 'pointer', color: '#1e3a8a', fontWeight: 600 },
}

function stars(v) {
  const n = Number(v)
  if (isNaN(n)) return v == null ? '—' : String(v)
  const full = Math.floor(n)
  return '★'.repeat(Math.max(0, full)) + '☆'.repeat(Math.max(0, 5 - full)) + ' ' + n
}

// Resolve a section's record(s): sql → fetched rows; master_row → the clicked row.
function sectionData(sec, row, result) {
  if (sec.source === 'sql') {
    if (result?.error) return { error: result.error, rows: [] }
    return { rows: result?.rows || [] }
  }
  return { rows: row ? [row] : [] }
}

function FieldGrid({ sec, record }) {
  const fields = sec.fields || []
  return (
    <div style={{ ...C.grid2, gridTemplateColumns: `repeat(${sec.columns || 2}, 1fr)` }}>
      {fields.map((f, i) => {
        const raw = record?.[f.column]
        const val = f.renderer === 'stars'
          ? stars(raw)
          : f.renderer === 'compact'
            ? (raw == null || raw === '' ? '—' : formatDrawerChartValue(raw, 'compact'))
            : (raw == null || raw === '' ? '—' : String(raw))
        return (
          <div key={i}>
            <div style={C.diLbl}>{f.label}</div>
            <div style={C.diVal}>{val}</div>
          </div>
        )
      })}
    </div>
  )
}

function FlagChips({ sec, record }) {
  const chips = sec.chips || []
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
      {chips.map((c, i) => {
        const on = String(record?.[c.column]) === String(c.true_value ?? 1)
        return (
          <span key={i} style={{ ...C.chip,
            ...(on ? { background: '#fff3cd', color: '#856404' } : { background: '#f3f4f6', color: '#9ca3af' }) }}>
            {on ? `✓ ${c.label}` : `${c.label}: No`}
          </span>
        )
      })}
    </div>
  )
}

/** Newer-month notice for a projection-enabled section: shown only when the
 *  user applied specific months and none of them is the latest available. */
function NewerMonthNotice({ meta, appliedFilters, onShowMonth }) {
  const param = meta?.month_filter_param
  if (!param || !meta?.latest_filter_value) return null
  const applied = String(appliedFilters?.[param] ?? '').trim()
  if (!applied) return null
  const values = applied.split(',').map(s => s.trim()).filter(Boolean)
  if (values.includes(meta.latest_filter_value)) return null
  return (
    <div style={C.notice}>
      <span>Newer data available: <strong>{meta.latest_filter_value || monthLabel(meta.latest_snapshot)}</strong></span>
      {onShowMonth && (
        <button type="button" style={C.noticeBtn}
                onClick={() => onShowMonth(param, meta.latest_filter_value)}>Show</button>
      )}
    </div>
  )
}

function MeasureCards({ sec, rows, result, rowKey, projectionApi, onSaved, reload, drafts, setDrafts,
                        appliedFilters, onShowMonth, sectionError, setSectionError }) {
  const card = sec.card || {}
  const block = card.projection
  const meta = block ? result?.projection_meta : null
  const pvActive = !!(block && meta && !meta.error && projectionApi)
  const typeKey = block?.type_key

  const submit = async (r, hash, draft) => {
    const key = `${typeKey}:${hash}`
    const ident = result?.projections?.[typeKey]?.[hash]
    const body = {
      type_key: typeKey, section_id: sec.id, row_key: String(rowKey), identity_hash: hash,
      snapshot: r.__pv_month, cycle_no: r.__pv_cycle_no || 0,
      expected_revision: ident?.identity_revision || 0, request_id: draft.request_id,
      note: draft.note || '', expected_date: draft.expected_date || '', evidence: draft.evidence || '',
    }
    let res
    try {
      res = await projectionApi.mutate(draft.action, body)
    } catch (err) {
      res = { ok: false, status: 0, body: { error: err?.message || 'Network error' } }
    }
    if (res.ok) {
      setDrafts(prev => { const n = { ...prev }; delete n[key]; return n })
      setSectionError(null)
      await reload()
      onSaved?.()
      return
    }
    const msg = res.body?.error || `Save failed (${res.status || 'network'})`
    if (draft.action === 'undo') setSectionError(msg)
    else setDrafts(prev => ({ ...prev, [key]: { ...(prev[key] || draft), error: msg } }))
    if (res.status === 409) await reload()       // show the latest version; the draft is kept
  }

  if (!rows.length) return <div style={{ fontSize: 12, color: '#9ca3af' }}>No records.</div>
  return (
    <div>
      {block && meta?.error && <div style={C.errChip}>Projections unavailable: {meta.error}</div>}
      {sectionError && <div style={C.errChip}>{sectionError}</div>}
      {pvActive && <NewerMonthNotice meta={meta} appliedFilters={appliedFilters} onShowMonth={onShowMonth} />}
      {rows.map((r, i) => {
        // Current: the server-normalized status for projection cards, the
        // existing '1'/true rule for every other card.
        const compliant = pvActive && ('__pv_source_positive' in r)
          ? !!r.__pv_source_positive
          : (String(r[card.status_column]) === '1' || r[card.status_column] === true)
        const ineligible = pvActive && r.__pv_outcome === 'ineligible'
        const alerts = card.alerts || []
        const hash = r.__pv_identity_hash || ''
        const key = `${typeKey}:${hash}`
        return (
          <div key={i} style={{ border: '1px solid #e5e7eb', borderRadius: 9, padding: 14, marginBottom: 11 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span style={{ fontWeight: 800, fontSize: 15, color: 'var(--pv-primary,#0066cc)' }}>
                {r[card.title_column]}
              </span>
              <span style={{ ...C.chip, ...(ineligible ? C.bdgGrey : compliant ? C.bdgOk : C.bdgBad) }}>
                {ineligible ? 'Not eligible' : compliant ? '✓ Compliant' : '✗ Non-Compliant'}
              </span>
            </div>
            {card.desc_column && r[card.desc_column] != null && (
              <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 9 }}>{r[card.desc_column]}</div>
            )}
            {card.strip_column && (
              <div style={{ margin: '9px 0' }}>
                <ComplianceStrip items={r[card.strip_column]} size="lg" showLabels />
              </div>
            )}
            {alerts.map((a, ai) => {
              const body = r[a.body_column]
              if (body == null || body === '') return null
              const isErr = a.kind === 'error'
              return (
                <div key={ai} style={{ borderRadius: 7, padding: '10px 12px', marginTop: 8, fontSize: 12,
                  lineHeight: 1.45,
                  background: isErr ? '#f8d7da' : '#fff3cd',
                  borderLeft: `3px solid ${isErr ? '#dc2626' : '#f59e0b'}` }}>
                  {a.title && <div style={{ fontWeight: 700, marginBottom: 3,
                    color: isErr ? '#c62828' : '#856404' }}>{a.title}</div>}
                  <div>{String(body)}</div>
                </div>
              )
            })}
            {pvActive && hash && (
              <ProjectionControls
                row={r}
                identity={result?.projections?.[typeKey]?.[hash]}
                meta={meta}
                draft={drafts[key] || null}
                setDraft={(d) => setDrafts(prev => {
                  const n = { ...prev }
                  if (d) n[key] = d
                  else delete n[key]
                  return n
                })}
                onSubmit={(draft) => submit(r, hash, draft)}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

function AlertBlocks({ sec, record }) {
  const blocks = sec.blocks || []
  return (
    <div>
      {blocks.map((b, i) => {
        const body = record?.[b.body_column]
        if (body == null || body === '') return null
        const isErr = b.kind === 'error'
        return (
          <div key={i} style={{ borderRadius: 7, padding: '10px 12px', marginBottom: 8, fontSize: 12,
            lineHeight: 1.45, background: isErr ? '#f8d7da' : '#fff3cd',
            borderLeft: `3px solid ${isErr ? '#dc2626' : '#f59e0b'}` }}>
            {b.title && <div style={{ fontWeight: 700, marginBottom: 3 }}>{b.title}</div>}
            <div>{String(body)}</div>
          </div>
        )
      })}
    </div>
  )
}

function Section({ sec, row, result, loading, pv }) {
  const { rows, error } = sectionData(sec, row, result)
  let body
  if (loading) body = <div style={{ fontSize: 12, color: '#9ca3af' }}>Loading…</div>
  else if (error) body = <div style={C.errChip}>{error}</div>
  else if (sec.type === 'field_grid') body = <FieldGrid sec={sec} record={rows[0] || {}} />
  else if (sec.type === 'flag_chips') body = <FlagChips sec={sec} record={rows[0] || {}} />
  else if (sec.type === 'measure_cards') body = <MeasureCards sec={sec} rows={rows} result={result} {...pv} />
  else if (sec.type === 'alert_blocks') body = <AlertBlocks sec={sec} record={rows[0] || {}} />
  else if (sec.type === 'chart') body = <DrawerChartSection section={sec} rows={rows} />
  else body = <div style={{ fontSize: 12, color: '#9ca3af' }}>Unsupported section type: {sec.type}</div>

  return (
    <div style={{ marginBottom: 22 }}>
      {sec.title && <div style={C.secTitle}>{sec.title}</div>}
      {body}
    </div>
  )
}

export default function DetailDrawer({ schema, row, fetchDetail, onClose, projectionApi = null,
                                       onProjectionSaved = null, appliedFilters = null,
                                       onShowMonth = null }) {
  const [loading, setLoading] = useState(true)
  const [sections, setSections] = useState({})
  const [error, setError] = useState(null)
  const [drafts, setDrafts] = useState({})
  const [sectionError, setSectionError] = useState(null)
  const closeRef = useRef(null)
  const seqRef = useRef(0)

  const rowKeyCol = schema.row_key_column
  const rowKey = row?.[rowKeyCol]
  const hasSql = (schema.sections || []).some(s => s.source === 'sql' && s.has_sql)

  // Fetch all sql sections in one request. `silent` keeps the cards on screen
  // (timer refresh / after a save); a stale response never overwrites a newer one.
  const load = useCallback(async (silent = false) => {
    if (!hasSql) { setLoading(false); return }
    if (rowKey == null || rowKey === '') {
      setError(`No value for row key column "${rowKeyCol}"`)
      setLoading(false)
      return
    }
    const seq = ++seqRef.current
    if (!silent) { setLoading(true); setError(null) }
    try {
      const res = await fetchDetail(String(rowKey))
      if (seq !== seqRef.current) return
      setSections(res?.sections || {})
      if (!silent) setLoading(false)
    } catch (err) {
      if (seq !== seqRef.current) return
      if (!silent) { setError(err?.message || 'Failed to load details'); setLoading(false) }
    }
  }, [rowKey, rowKeyCol, hasSql, fetchDetail])

  useEffect(() => {
    load(false)
    return () => { seqRef.current++ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rowKey])

  // Timer refresh for projection-enabled sections (page visible only).
  const pollSeconds = Math.max(0, ...Object.values(sections).map(s => Number(s?.projection_meta?.poll_seconds || 0)))
  useEffect(() => {
    if (!pollSeconds) return undefined
    const id = setInterval(() => {
      if (document.visibilityState === 'visible') load(true)
    }, pollSeconds * 1000)
    return () => clearInterval(id)
  }, [pollSeconds, load])

  // Esc-to-close + scroll-lock + focus (PageHelpDrawer shell pattern).
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [onClose])

  const title = fillTemplate(schema.title_template, row)
  const subtitle = fillTemplate(schema.subtitle_template, row)
  const pv = {
    rowKey, projectionApi, onSaved: onProjectionSaved, reload: () => load(true),
    drafts, setDrafts, appliedFilters, onShowMonth, sectionError, setSectionError,
  }

  return (
    <div
      className="pv-drawer-backdrop"
      role="presentation"
      style={C.backdrop}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <aside
        className="pv-detail-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={title || 'Details'}
        style={C.drawer}
      >
        <header style={C.header}>
          <div>
            <div style={{ fontSize: 17, fontWeight: 700 }}>{title || 'Details'}</div>
            {subtitle && <div style={{ fontSize: 12, opacity: .85, marginTop: 3 }}>{subtitle}</div>}
          </div>
          <button ref={closeRef} onClick={onClose} aria-label="Close" style={C.close}>✕</button>
        </header>
        <div style={{ padding: 20 }}>
          {error && <div style={C.errChip}>{error}</div>}
          {(schema.sections || []).map(sec => (
            <Section
              key={sec.id}
              sec={sec}
              row={row}
              result={sections[sec.id]}
              loading={loading && sec.source === 'sql'}
              pv={pv}
            />
          ))}
        </div>
      </aside>
    </div>
  )
}
