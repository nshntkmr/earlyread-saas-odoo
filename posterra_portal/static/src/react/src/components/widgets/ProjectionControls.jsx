import React, { useState } from 'react'

/**
 * ProjectionControls — the "Mark Projected Compliant" chip, buttons, popover
 * and history lines for ONE measure card of a projection-enabled
 * `measure_cards` drawer section.
 *
 * Everything shown here comes from the server overlay (spec §6): the row's
 * `__pv_outcome` picks the chip, the `__pv_can_*` flags decide the buttons
 * (never the colour), `projections[type][hash]` carries the cycles, the
 * identity-wide revision and the latest changes, and `projection_meta`
 * carries labels, colours and capture settings. A typed draft survives
 * drawer refreshes and a 409 keeps it for review.
 */

const ACTION_LABELS = {
  mark: 'Marked', edit: 'Edited', reproject: 'Re-projected', undo: 'Undone',
  admin_undo: 'Undone (admin)', admin_void: 'Voided',
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** '202607' → 'Jul 2026'; anything else is returned as-is. */
export function monthLabel(ym) {
  const s = String(ym || '')
  if (/^\d{6}$/.test(s)) {
    const m = parseInt(s.slice(4, 6), 10)
    if (m >= 1 && m <= 12) return `${MONTHS[m - 1]} ${s.slice(0, 4)}`
  }
  return s
}

function fmtDateTime(s) {
  if (!s) return ''
  const d = new Date(s.replace(' ', 'T') + (s.endsWith('Z') ? '' : 'Z'))
  if (isNaN(d.getTime())) return s
  return d.toLocaleString(undefined, { day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit' })
}

function fmtDate(s) {
  if (!s) return ''
  const d = new Date(s + 'T00:00:00')
  if (isNaN(d.getTime())) return s
  return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' })
}

function newRequestId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID().replace(/-/g, '')
  return 'r' + Date.now().toString(16) + Math.random().toString(16).slice(2)
}

const S = {
  chip: { borderRadius: 6, padding: '4px 11px', fontSize: 11, fontWeight: 700, display: 'inline-block',
    color: '#fff' },
  btn: { fontSize: 12, padding: '4px 10px', borderRadius: 6, border: '1px solid #d1d5db', background: '#fff',
    cursor: 'pointer' },
  btnPrimary: { fontSize: 12, padding: '4px 10px', borderRadius: 6, border: 'none', cursor: 'pointer',
    background: 'var(--pv-primary,#0066cc)', color: '#fff', fontWeight: 600 },
  pop: { border: '1px solid #e5e7eb', borderRadius: 8, padding: 12, marginTop: 8, background: '#f9fafb' },
  lbl: { fontSize: 11, color: '#6b7280', marginBottom: 3, display: 'block' },
  input: { width: '100%', fontSize: 12, padding: '5px 7px', border: '1px solid #d1d5db', borderRadius: 5,
    boxSizing: 'border-box' },
  hist: { fontSize: 11, color: '#6b7280', marginTop: 6, lineHeight: 1.5 },
  err: { background: '#f8d7da', color: '#721c24', borderRadius: 6, padding: '6px 9px', fontSize: 11,
    marginTop: 6 },
  note: { fontSize: 11, color: '#6b7280', marginTop: 4 },
}

export default function ProjectionControls({ row, identity, meta, draft, setDraft, onSubmit, saving }) {
  const [busy, setBusy] = useState(false)
  const outcome = row.__pv_outcome || ''
  const styles = meta?.styles || {}
  const style = outcome ? styles[outcome] : null
  const cycle = identity?.cycles?.[String(row.__pv_cycle_no)]
  const history = (identity?.history || []).slice(0, meta?.history_shown || 3)
  const canAct = !!meta?.can_act
  const labels = meta?.labels || {}
  const capture = meta?.capture || {}
  const evidenceOptions = capture.evidence_options || []

  const openDraft = (action) => setDraft({
    action, note: cycle?.note || '', expected_date: cycle?.expected_date || '',
    evidence: cycle?.evidence || '', request_id: newRequestId(), error: null,
    based_on_revision: identity?.identity_revision || 0,
  })
  const closeDraft = () => setDraft(null)

  const submit = async () => {
    if (!draft || busy) return
    setBusy(true)
    try { await onSubmit(draft) } finally { setBusy(false) }
  }

  const undo = async () => {
    if (busy) return
    if (!window.confirm('Cancel this projection from the latest available month? The record and its history are kept.')) return
    setBusy(true)
    try {
      await onSubmit({ action: 'undo', request_id: newRequestId(), based_on_revision: identity?.identity_revision || 0 })
    } finally { setBusy(false) }
  }

  const chipLabel = style ? String(style.label || outcome).replace('{month}', monthLabel(row.__pv_month)) : ''
  const stale = draft && identity && draft.based_on_revision !== identity.identity_revision

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        {style && (
          <span style={{ ...S.chip, background: style.color || '#6b7280' }}>{chipLabel}</span>
        )}
        {cycle?.expected_date && outcome !== '' && (
          <span style={S.note}>Expected by {fmtDate(cycle.expected_date)}</span>
        )}
        {cycle?.publish_state === 'pending' && outcome !== '' && (
          <span style={S.note}>Saved · reporting update pending</span>
        )}
        <span style={{ flex: 1 }} />
        {canAct && row.__pv_can_mark && (
          <button type="button" style={S.btnPrimary} disabled={busy || saving}
                  onClick={() => openDraft('mark')}>{labels.mark || 'Mark Projected Compliant'}</button>
        )}
        {canAct && row.__pv_can_reproject && (
          <button type="button" style={S.btnPrimary} disabled={busy || saving}
                  onClick={() => openDraft('reproject')}>{labels.reproject || 'Re-project'}</button>
        )}
        {canAct && row.__pv_can_edit && (
          <button type="button" style={S.btn} disabled={busy || saving}
                  onClick={() => openDraft('edit')}>Edit</button>
        )}
        {canAct && row.__pv_can_undo && (
          <button type="button" style={S.btn} disabled={busy || saving} onClick={undo}>Undo</button>
        )}
      </div>

      {history.length > 0 && (
        <div style={S.hist}>
          {history.map((h, i) => (
            <div key={i}>
              {ACTION_LABELS[h.action] || h.action} by {h.user} · {fmtDateTime(h.at)}
              {h.reason ? ` · ${h.reason}` : ''}
            </div>
          ))}
        </div>
      )}

      {draft && draft.action !== 'undo' && (
        <div style={S.pop} role="dialog" aria-label={draft.action}>
          <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 8 }}>
            {draft.action === 'mark' ? (labels.mark || 'Mark Projected Compliant')
              : draft.action === 'reproject' ? (labels.reproject || 'Re-project')
                : 'Edit projection'}
          </div>
          {evidenceOptions.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <label style={S.lbl}>Evidence</label>
              <select style={S.input} value={draft.evidence}
                      onChange={e => setDraft({ ...draft, evidence: e.target.value })}>
                <option value="">—</option>
                {evidenceOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          )}
          {capture.expected_date_enabled !== false && (
            <div style={{ marginBottom: 8 }}>
              <label style={S.lbl}>Expected closure date (optional)</label>
              <input type="date" style={S.input} value={draft.expected_date}
                     onChange={e => setDraft({ ...draft, expected_date: e.target.value })} />
            </div>
          )}
          {capture.note_enabled !== false && (
            <div style={{ marginBottom: 8 }}>
              <label style={S.lbl}>Comment (optional)</label>
              <textarea style={{ ...S.input, minHeight: 56 }} value={draft.note}
                        onChange={e => setDraft({ ...draft, note: e.target.value })} />
            </div>
          )}
          {stale && !draft.error && (
            <div style={S.note}>This draft is based on an older version. Review the latest details above before saving.</div>
          )}
          {draft.error && <div style={S.err}>{draft.error}</div>}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 6 }}>
            <button type="button" style={S.btn} disabled={busy} onClick={closeDraft}>Cancel</button>
            <button type="button" style={S.btnPrimary} disabled={busy} onClick={submit}>
              {busy ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
