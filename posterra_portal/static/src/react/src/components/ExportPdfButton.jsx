import React, { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useFilters } from '../state/FilterContext'
import { apiFetchBlob } from '../api/client'
import { pagePdfExportUrl } from '../api/endpoints'

/**
 * ExportPdfButton — page-level "Export PDF" (plan v5).
 *
 * Rendered ONCE by FilterBar's header renderer into the page-header END slot
 * (the server opens that slot whenever page_config.pdf_export is present).
 * Sends the APPLIED filter values, the current tab and every widget's request
 * state (selected scope option / scope value / widget-filter params, read from
 * the WidgetGrid registry) so the server runs each widget with the screen's
 * inputs. The server does all data work; this component only collects inputs,
 * shows progress and saves the returned PDF.
 */
export default function ExportPdfButton() {
  const {
    config, filterValues, currentTabKey, accessToken, refreshToken, apiBase,
    widgetStateRegistryRef,
  } = useFilters()
  const pdf = config?.pdf_export
  const [open, setOpen] = useState(false)
  const [keynote, setKeynote] = useState('')
  const [orientation, setOrientation] = useState(pdf?.orientation || 'landscape')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const firstFieldRef = useRef(null)

  const close = useCallback(() => {
    if (busy) return
    setOpen(false)
    setError('')
    setNotice('')
  }, [busy])

  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => { if (e.key === 'Escape') close() }
    document.addEventListener('keydown', onKey)
    const t = setTimeout(() => firstFieldRef.current?.focus(), 0)
    return () => { document.removeEventListener('keydown', onKey); clearTimeout(t) }
  }, [open, close])

  const collectWidgetState = () => {
    const merged = { scope_options: {}, scope_values: {}, widget_filters: {} }
    const registry = widgetStateRegistryRef?.current || {}
    Object.values(registry).forEach(getState => {
      if (typeof getState !== 'function') return
      const s = getState() || {}
      Object.assign(merged.scope_options, s.scope_options || {})
      Object.assign(merged.scope_values, s.scope_values || {})
      Object.assign(merged.widget_filters, s.widget_filters || {})
    })
    return merged
  }

  const exportPdf = async () => {
    if (busy) return
    setBusy(true)
    setError('')
    setNotice('')
    const body = {
      tab_key: currentTabKey || '',
      filters: { ...filterValues },
      ...collectWidgetState(),
      keynote: pdf?.keynote_enabled ? keynote.trim() : '',
      orientation,
    }
    try {
      const result = await apiFetchBlob(
        pagePdfExportUrl(apiBase, config.page.id),
        accessToken,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) },
        refreshToken,
      )
      const fallback = `${(config.page?.name || 'report').replace(/[^A-Za-z0-9_-]+/g, '_')}.pdf`
      const objectUrl = URL.createObjectURL(result.blob)
      const a = document.createElement('a')
      a.href = objectUrl
      a.download = result.filename || fallback
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
      if (result.incomplete) {
        setNotice('The PDF was downloaded, but some widgets could not be loaded. '
          + 'The first page of the PDF lists them.')
      } else {
        setOpen(false)
      }
    } catch (err) {
      console.warn('PDF export failed:', err)
      setError(err?.message || 'The PDF could not be generated. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  if (!pdf?.enabled) return null
  const maxChars = pdf.keynote_max_chars || 2000
  // Admin colours (validated server-side). A custom background without a text
  // colour gets white text so the label stays readable.
  const bg = pdf.button?.bg_color || ''
  const fg = pdf.button?.text_color || (bg ? '#ffffff' : '')
  const buttonStyle = {
    ...(bg ? { backgroundColor: bg, borderColor: bg } : {}),
    ...(fg ? { color: fg } : {}),
  }

  const modal = open && createPortal(
    <div className="wb-modal-overlay pv-pdf-modal-overlay" onMouseDown={e => { if (e.target === e.currentTarget) close() }}>
      <div className="wb-modal pv-pdf-modal" role="dialog" aria-modal="true" aria-labelledby="pv-pdf-title">
        <div className="wb-modal-header">
          <h3 className="wb-modal-title" id="pv-pdf-title">Export PDF</h3>
          <button type="button" className="wb-btn-close" aria-label="Close" onClick={close} disabled={busy}>×</button>
        </div>
        <div className="wb-modal-body">
          <p className="pv-pdf-help">
            Prints the current tab&apos;s record headers, KPI cards, tables and charts with the
            filters you applied. Maps and some custom widgets are not included yet.
          </p>
          {pdf.keynote_enabled && (
            <label className="pv-pdf-field">
              <span>Keynote <small>(optional, printed near the top)</small></span>
              <textarea
                ref={firstFieldRef}
                rows={4}
                maxLength={maxChars}
                value={keynote}
                disabled={busy}
                onChange={e => setKeynote(e.target.value)}
                placeholder="e.g. Focus this quarter on depression screening outreach."
              />
              <small className="pv-pdf-count">{keynote.length.toLocaleString()} / {maxChars.toLocaleString()}</small>
            </label>
          )}
          <label className="pv-pdf-field pv-pdf-inline">
            <span>Orientation</span>
            <select
              ref={pdf.keynote_enabled ? undefined : firstFieldRef}
              value={orientation}
              disabled={busy}
              onChange={e => setOrientation(e.target.value)}
            >
              <option value="landscape">Landscape</option>
              <option value="portrait">Portrait</option>
            </select>
          </label>
          {busy && <div className="pv-pdf-status" role="status">Generating PDF… this can take up to half a minute.</div>}
          {error && <div className="pv-pdf-error" role="alert">{error}</div>}
          {notice && <div className="pv-pdf-notice" role="status">{notice}</div>}
        </div>
        <div className="wb-modal-footer">
          <button type="button" className="btn btn-sm btn-outline-secondary" onClick={close} disabled={busy}>
            {notice ? 'Close' : 'Cancel'}
          </button>
          <button type="button" className="btn btn-sm btn-primary" onClick={exportPdf} disabled={busy}>
            {busy ? 'Generating…' : 'Download PDF'}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )

  return (
    <div className="pv-header-pdf">
      <button
        type="button"
        className={`btn btn-sm btn-outline-secondary pv-pdf-export-btn${bg || fg ? ' pv-pdf-export-btn--custom' : ''}`}
        style={buttonStyle}
        onClick={() => setOpen(true)}
        title="Export this tab as a PDF"
      >
        <i className="fa fa-file-pdf-o" aria-hidden="true" /> Export PDF
      </button>
      {modal}
    </div>
  )
}
