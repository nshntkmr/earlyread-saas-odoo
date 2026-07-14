import React, { useEffect, useState, useRef } from 'react'
import { ComplianceStrip } from '@posterra/grid-utils'
import DrawerChartSection from './DrawerChartSection'
import { formatDrawerChartValue } from './drawerChartOptions'

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

function MeasureCards({ sec, rows }) {
  const card = sec.card || {}
  if (!rows.length) return <div style={{ fontSize: 12, color: '#9ca3af' }}>No records.</div>
  return (
    <div>
      {rows.map((r, i) => {
        const compliant = String(r[card.status_column]) === '1' || r[card.status_column] === true
        const alerts = card.alerts || []
        return (
          <div key={i} style={{ border: '1px solid #e5e7eb', borderRadius: 9, padding: 14, marginBottom: 11 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span style={{ fontWeight: 800, fontSize: 15, color: 'var(--pv-primary,#0066cc)' }}>
                {r[card.title_column]}
              </span>
              <span style={{ ...C.chip, ...(compliant ? C.bdgOk : C.bdgBad) }}>
                {compliant ? '✓ Compliant' : '✗ Non-Compliant'}
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

function Section({ sec, row, result, loading }) {
  const { rows, error } = sectionData(sec, row, result)
  let body
  if (loading) body = <div style={{ fontSize: 12, color: '#9ca3af' }}>Loading…</div>
  else if (error) body = <div style={C.errChip}>{error}</div>
  else if (sec.type === 'field_grid') body = <FieldGrid sec={sec} record={rows[0] || {}} />
  else if (sec.type === 'flag_chips') body = <FlagChips sec={sec} record={rows[0] || {}} />
  else if (sec.type === 'measure_cards') body = <MeasureCards sec={sec} rows={rows} />
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

export default function DetailDrawer({ schema, row, fetchDetail, onClose }) {
  const [loading, setLoading] = useState(true)
  const [sections, setSections] = useState({})
  const [error, setError] = useState(null)
  const closeRef = useRef(null)

  const rowKeyCol = schema.row_key_column
  const rowKey = row?.[rowKeyCol]

  // Fetch all sql sections in one request when the drawer opens.
  useEffect(() => {
    let cancelled = false
    const hasSql = (schema.sections || []).some(s => s.source === 'sql' && s.has_sql)
    if (!hasSql) { setLoading(false); return }
    if (rowKey == null || rowKey === '') {
      setError(`No value for row key column "${rowKeyCol}"`)
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    fetchDetail(String(rowKey))
      .then(res => { if (!cancelled) { setSections(res?.sections || {}); setLoading(false) } })
      .catch(err => { if (!cancelled) { setError(err?.message || 'Failed to load details'); setLoading(false) } })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rowKey])

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
            />
          ))}
        </div>
      </aside>
    </div>
  )
}
