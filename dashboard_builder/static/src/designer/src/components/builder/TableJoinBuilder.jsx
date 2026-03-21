import React, { useState, useEffect } from 'react'
import { designerFetch } from '../../api/client'
import { sourcesUrl, sourceDetailUrl, sourceRelationsUrl } from '../../api/endpoints'

/**
 * Step 2 (Visual mode): Select tables and configure JOINs.
 *
 * Props:
 *   sources     — [{id, name, alias, columns: [...]}]
 *   joins       — [{relation_id, source_id, target_id, ...}]
 *   onUpdate    — ({sources, joins}) => void
 *   apiBase     — string
 */
export default function TableJoinBuilder({ sources, joins, onUpdate, apiBase }) {
  const [availableSources, setAvailableSources] = useState([])
  const [relations, setRelations] = useState([])
  const [loading, setLoading] = useState(false)

  // Load available schema sources
  useEffect(() => {
    setLoading(true)
    designerFetch(sourcesUrl(apiBase))
      .then(data => setAvailableSources(data))
      .catch(err => console.error('Failed to load sources:', err))
      .finally(() => setLoading(false))
  }, [apiBase])

  // Load relations when sources change
  useEffect(() => {
    if (sources.length === 0) return
    const primaryId = sources[0]?.id
    if (!primaryId) return

    designerFetch(sourceRelationsUrl(apiBase, primaryId))
      .then(data => setRelations(data))
      .catch(err => console.error('Failed to load relations:', err))
  }, [sources, apiBase])

  const addPrimarySource = async (sourceId) => {
    if (!sourceId) return
    const detail = await designerFetch(sourceDetailUrl(apiBase, sourceId))
    onUpdate({ sources: [detail], joins: [] })
  }

  const addSecondarySource = async (sourceId) => {
    if (!sourceId) return
    const detail = await designerFetch(sourceDetailUrl(apiBase, sourceId))
    onUpdate({
      sources: [...sources, detail],
      joins,
    })
  }

  const removeSource = (idx) => {
    const updated = sources.filter((_, i) => i !== idx)
    onUpdate({ sources: updated, joins: [] })
  }

  if (loading) return <div className="wb-loading">Loading sources...</div>

  return (
    <div>
      <h3 className="wb-step-title">Select Data Tables</h3>

      {/* Primary table */}
      <div className="wb-field-group">
        <label className="wb-label">Primary Table</label>
        <select
          className="wb-select"
          value={sources[0]?.id || ''}
          onChange={e => addPrimarySource(Number(e.target.value))}
        >
          <option value="">-- Select table --</option>
          {availableSources.map(s => (
            <option key={s.id} value={s.id}>{s.name} ({s.table_name})</option>
          ))}
        </select>
      </div>

      {/* Selected tables */}
      {sources.length > 0 && (
        <div className="wb-selected-tables">
          {sources.map((src, idx) => (
            <div key={src.id} className="wb-table-chip">
              <span className="wb-table-chip-name">{src.name}</span>
              <span className="wb-table-chip-alias">{src.alias || `t${idx}`}</span>
              <span className="wb-table-chip-cols">{src.columns?.length || 0} cols</span>
              {idx > 0 && (
                <button type="button" className="wb-chip-remove" onClick={() => removeSource(idx)}>
                  <i className="fa fa-times" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Join display */}
      {sources.length > 1 && relations.length > 0 && (
        <div className="wb-join-display">
          <h4 className="wb-sub-title">Join Configuration</h4>
          {relations.map(rel => (
            <div key={rel.id} className="wb-join-row">
              <span>{sources[0]?.name}</span>
              <span className="wb-join-arrow">
                <i className="fa fa-arrows-h" /> {rel.join_type?.toUpperCase() || 'LEFT'} JOIN
              </span>
              <span>{rel.target?.name}</span>
              <span className="wb-join-on">
                ON {rel.source_column} = {rel.target_column}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Add table button */}
      {sources.length > 0 && sources.length < 4 && (
        <div className="wb-field-group">
          <button
            type="button"
            className="wb-btn wb-btn--outline"
            onClick={() => {
              const unused = availableSources.filter(
                s => !sources.find(sel => sel.id === s.id)
              )
              if (unused.length > 0) addSecondarySource(unused[0].id)
            }}
          >
            <i className="fa fa-plus" /> Add Table
          </button>
        </div>
      )}
    </div>
  )
}
