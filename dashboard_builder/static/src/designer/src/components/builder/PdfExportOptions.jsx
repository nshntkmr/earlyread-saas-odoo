import React from 'react'

// Chart types the page PDF export prints in v1 (others are listed in the PDF
// as "not included"). Kept in sync with posterra_portal
// services/pdf_export/collector.py V1_KINDS.
const PRINTED_TYPES = new Set(['record_header', 'kpi', 'status_kpi', 'table'])

const SPANS = [
  { value: '', label: 'Same as on screen' },
  { value: '3', label: '25%' },
  { value: '4', label: '33%' },
  { value: '6', label: '50%' },
  { value: '8', label: '67%' },
  { value: '12', label: '100%' },
]

/**
 * PdfExportOptions — the widget definition's PDF print defaults.
 *
 * Seeded into NEW placements; a placed widget keeps its own values afterwards
 * (library updates never overwrite them). The page decides whether PDF export
 * is available at all (Pages → PDF Export in the admin).
 */
export default function PdfExportOptions({ chartType, appearance, onChange }) {
  const printed = PRINTED_TYPES.has(chartType)
  const include = appearance.pdfInclude !== false
  return (
    <div className="dd-section" style={{ marginTop: 16, padding: '12px 14px', border: '1px solid #e5e7eb', borderRadius: 8 }}>
      <div style={{ fontWeight: 600, marginBottom: 6 }}>
        <i className="fa fa-file-pdf-o me-1" /> PDF export
      </div>
      {!printed && (
        <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>
          This widget type is not printed in the page PDF yet; the PDF lists it as not included.
        </div>
      )}
      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
        <input
          type="checkbox"
          checked={include}
          onChange={e => onChange({ pdfInclude: e.target.checked })}
        />
        Include in page PDF
      </label>
      {include && (
        <>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, marginTop: 4 }}>
            <input
              type="checkbox"
              checked={appearance.pdfPageBreakBefore === true}
              onChange={e => onChange({ pdfPageBreakBefore: e.target.checked })}
            />
            Start on a new PDF page
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginTop: 6 }}>
            PDF width
            <select
              value={appearance.pdfColSpan || ''}
              onChange={e => onChange({ pdfColSpan: e.target.value })}
              style={{ fontSize: 13 }}
            >
              {SPANS.map(s => <option key={s.value || 'same'} value={s.value}>{s.label}</option>)}
            </select>
            {chartType === 'table' && (
              <span style={{ fontSize: 12, color: '#6b7280' }}>(tables always print full width)</span>
            )}
          </label>
        </>
      )}
      <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
        Defaults for new placements. Widgets already on a page keep their own PDF settings.
      </div>
    </div>
  )
}
