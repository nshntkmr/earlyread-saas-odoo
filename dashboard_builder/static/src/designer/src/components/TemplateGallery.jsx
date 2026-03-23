import React, { useState, useEffect } from 'react'
import { designerFetch } from '../api/client'
import { templatesUrl, templateUseUrl } from '../api/endpoints'
import TemplateConfigPanel from './TemplateConfigPanel'

const CHART_ICONS = {
  bar: 'fa-bar-chart', line: 'fa-line-chart', pie: 'fa-pie-chart',
  donut: 'fa-circle-o-notch', gauge: 'fa-tachometer', radar: 'fa-bullseye',
  kpi: 'fa-hashtag', status_kpi: 'fa-arrow-up', table: 'fa-table',
  scatter: 'fa-braille', heatmap: 'fa-th', battle_card: 'fa-columns',
  insight_panel: 'fa-lightbulb-o', gauge_kpi: 'fa-dashboard',
  kpi_strip: 'fa-ellipsis-h',
}

/**
 * TemplateGallery — Browse and configure widget templates.
 *
 * Parameterized templates → inline TemplateConfigPanel expands below the card.
 * Legacy JSON templates → immediate creation (old behavior).
 */
export default function TemplateGallery({ apiBase, appContext, onUseTemplate }) {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [using, setUsing] = useState(null)
  const [result, setResult] = useState(null)
  const [editingId, setEditingId] = useState(null) // template id being configured

  useEffect(() => {
    loadTemplates()
  }, [apiBase])

  const loadTemplates = async () => {
    setLoading(true)
    try {
      const data = await designerFetch(templatesUrl(apiBase))
      setTemplates(data)
    } catch (err) {
      console.error('Failed to load templates:', err)
    } finally {
      setLoading(false)
    }
  }

  /** Legacy JSON template: immediate create */
  const handleUseLegacy = async (tmpl) => {
    const pageId = appContext?.page?.id
    if (!pageId) {
      setResult({ error: 'Please select an App and Page in the context bar first.' })
      return
    }
    setUsing(tmpl.id)
    setResult(null)
    try {
      const body = { page_id: pageId, tab_id: appContext?.tab?.id }
      const data = await designerFetch(templateUseUrl(apiBase, tmpl.id), {
        method: 'POST',
        body: JSON.stringify(body),
      })
      const count = (data.widget_ids || []).length
      setResult({ templateName: tmpl.name, count })
    } catch (err) {
      setResult({ error: err.message })
    } finally {
      setUsing(null)
    }
  }

  const handleUse = (tmpl) => {
    if (tmpl.template_mode === 'parameterized') {
      handleUseLegacy(tmpl) // For now, same flow — config panel does the real work
    } else {
      handleUseLegacy(tmpl)
    }
  }

  const handleEdit = (tmpl) => {
    setEditingId(editingId === tmpl.id ? null : tmpl.id) // toggle
    setResult(null)
  }

  const handleConfigCreated = (res) => {
    setEditingId(null)
    setResult(res)
  }

  return (
    <div className="dd-page">
      <div className="dd-page-header">
        <h1 className="dd-page-title">Widget Templates</h1>
        <p className="dd-page-subtitle">
          Pre-built widget patterns — configure and place on any dashboard page.
        </p>
      </div>

      {/* Result banner */}
      {result && !result.error && (
        <div className="dd-result-banner dd-result-banner--success">
          <i className="fa fa-check-circle me-2" />
          Created {result.count} widget{result.count !== 1 ? 's' : ''} from
          "{result.templateName}" — check the Widget Library.
          <button type="button" className="dd-result-dismiss" onClick={() => setResult(null)}>
            <i className="fa fa-times" />
          </button>
        </div>
      )}
      {result && result.error && (
        <div className="dd-result-banner dd-result-banner--error">
          <i className="fa fa-exclamation-triangle me-2" />
          {result.error}
          <button type="button" className="dd-result-dismiss" onClick={() => setResult(null)}>
            <i className="fa fa-times" />
          </button>
        </div>
      )}

      {/* Grid */}
      {loading ? (
        <div className="dd-loading-state">
          <span className="spinner-border spinner-border-sm me-2" />
          Loading templates...
        </div>
      ) : templates.length === 0 ? (
        <div className="dd-empty-state">
          <i className="fa fa-puzzle-piece dd-empty-icon" />
          <p>No templates available.</p>
        </div>
      ) : (
        <div className="dd-def-grid" style={{ gridTemplateColumns: '1fr' }}>
          {templates.map(tmpl => {
            const isEditing = editingId === tmpl.id

            return (
              <div key={tmpl.id}>
                {/* Card */}
                <div
                  className="dd-def-card dd-tmpl-card"
                  style={{
                    borderRadius: isEditing ? '12px 12px 0 0' : 12,
                    borderBottom: isEditing ? '1px dashed #cbd5e1' : undefined,
                  }}
                >
                  <div className="dd-def-card-icon">
                    <i className={`fa ${CHART_ICONS[tmpl.chart_type] || 'fa-cube'}`} />
                  </div>
                  <div className="dd-def-card-body">
                    <h3 className="dd-def-name">{tmpl.name}</h3>
                    <p className="dd-def-desc">{tmpl.description || `${tmpl.chart_type || 'widget'} template`}</p>
                    <div className="dd-def-meta">
                      {tmpl.chart_type && (
                        <span className="dd-badge dd-badge--type">{tmpl.chart_type}</span>
                      )}
                      {tmpl.category && (
                        <span className="dd-badge dd-badge--cat">{tmpl.category}</span>
                      )}
                      {tmpl.creates_count > 1 && (
                        <span className="dd-badge" style={{ background: '#fef3c7', color: '#92400e' }}>
                          Creates {tmpl.creates_count}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="dd-def-card-actions" style={{ display: 'flex', gap: 8 }}>
                    <button
                      type="button"
                      className={`wb-btn wb-btn--sm ${isEditing ? 'wb-btn--primary' : 'wb-btn--outline'}`}
                      onClick={() => handleEdit(tmpl)}
                    >
                      <i className={`fa ${isEditing ? 'fa-chevron-up' : 'fa-pencil'} me-1`} />
                      {isEditing ? 'Close' : 'Edit'}
                    </button>
                    <button
                      type="button"
                      className="wb-btn wb-btn--primary wb-btn--sm"
                      onClick={() => handleUse(tmpl)}
                      disabled={using === tmpl.id}
                    >
                      {using === tmpl.id ? (
                        <>
                          <span className="spinner-border spinner-border-sm me-1" />
                          Creating...
                        </>
                      ) : (
                        <>
                          <i className="fa fa-magic me-1" /> Use Template
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Inline Config Panel */}
                {isEditing && (
                  <TemplateConfigPanel
                    template={tmpl}
                    apiBase={apiBase}
                    appContext={appContext}
                    onCreated={handleConfigCreated}
                    onClose={() => setEditingId(null)}
                  />
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
