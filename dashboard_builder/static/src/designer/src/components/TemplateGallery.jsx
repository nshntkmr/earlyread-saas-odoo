import React, { useState, useEffect } from 'react'
import { designerFetch } from '../api/client'
import { templatesUrl, templateUseUrl } from '../api/endpoints'

const CHART_ICONS = {
  bar: 'fa-bar-chart', line: 'fa-line-chart', pie: 'fa-pie-chart',
  donut: 'fa-circle-o-notch', gauge: 'fa-tachometer', radar: 'fa-bullseye',
  kpi: 'fa-hashtag', status_kpi: 'fa-arrow-up', table: 'fa-table',
  scatter: 'fa-braille', heatmap: 'fa-th', battle_card: 'fa-columns',
  insight_panel: 'fa-lightbulb-o', gauge_kpi: 'fa-dashboard',
}

/**
 * TemplateGallery — Browse and use pre-built widget templates.
 * Using a template creates one or more widget definitions in the library.
 */
export default function TemplateGallery({ apiBase }) {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [using, setUsing] = useState(null) // template id being used
  const [result, setResult] = useState(null) // last use result

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

  const handleUse = async (tmpl) => {
    setUsing(tmpl.id)
    setResult(null)
    try {
      const data = await designerFetch(templateUseUrl(apiBase, tmpl.id), {
        method: 'POST',
        body: JSON.stringify({}),
      })
      setResult({ templateName: tmpl.name, definitions: data.definitions || [] })
    } catch (err) {
      console.error('Failed to use template:', err)
      setResult({ error: err.message })
    } finally {
      setUsing(null)
    }
  }

  return (
    <div className="dd-page">
      <div className="dd-page-header">
        <h1 className="dd-page-title">Widget Templates</h1>
        <p className="dd-page-subtitle">
          Pre-built widget patterns — use a template to create definitions in your library.
        </p>
      </div>

      {/* Result banner */}
      {result && !result.error && (
        <div className="dd-result-banner dd-result-banner--success">
          <i className="fa fa-check-circle me-2" />
          Created {result.definitions.length} definition{result.definitions.length !== 1 ? 's' : ''} from
          "{result.templateName}" — check the Widget Library.
          <button
            type="button"
            className="dd-result-dismiss"
            onClick={() => setResult(null)}
          >
            <i className="fa fa-times" />
          </button>
        </div>
      )}
      {result && result.error && (
        <div className="dd-result-banner dd-result-banner--error">
          <i className="fa fa-exclamation-triangle me-2" />
          {result.error}
          <button
            type="button"
            className="dd-result-dismiss"
            onClick={() => setResult(null)}
          >
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
        <div className="dd-def-grid">
          {templates.map(tmpl => (
            <div key={tmpl.id} className="dd-def-card dd-tmpl-card">
              <div className="dd-def-card-icon">
                <i className={`fa ${CHART_ICONS[tmpl.chart_type] || 'fa-cube'}`} />
              </div>
              <div className="dd-def-card-body">
                <h3 className="dd-def-name">{tmpl.name}</h3>
                <p className="dd-def-desc">{tmpl.description || `${tmpl.chart_type} template`}</p>
                <div className="dd-def-meta">
                  <span className="dd-badge dd-badge--type">{tmpl.chart_type}</span>
                  {tmpl.category && (
                    <span className="dd-badge dd-badge--cat">{tmpl.category}</span>
                  )}
                </div>
              </div>
              <div className="dd-def-card-actions">
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
          ))}
        </div>
      )}
    </div>
  )
}
