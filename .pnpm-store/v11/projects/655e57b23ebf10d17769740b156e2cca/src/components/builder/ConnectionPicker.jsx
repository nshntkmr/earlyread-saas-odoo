import React, { useEffect, useState } from 'react'
import { designerFetch } from '../../api/client'
import { connectionsUrl } from '../../api/endpoints'

/**
 * ConnectionPicker — dropdown that lists every database connection
 * available to the wizard (Local Postgres + active dashboard.connection
 * records). Phase 3 Path C of the ClickHouse integration.
 *
 * Drives the schema-source filter across all three Data Source modes
 * (Visual Builder, Custom SQL, AI Assistant). Default selection is
 * 'local_pg' so existing PG widget creation flows are byte-identical
 * to pre-Phase-3 behaviour.
 *
 * The connection's engine is read from the picked entry's metadata and
 * is propagated to:
 *   - the schema source list endpoint (?connection_id filter)
 *   - the executor dispatch in QueryBuilder.execute_preview() at preview time
 *   - the AI Assistant's dialect prompt selection (server-side via
 *     assemble_context reading source.engine)
 *
 * Props:
 *   value         string  — current selection ('local_pg' or stringified id)
 *   onChange      func    — (newValue, connectionMeta) -> void
 *   apiBase       string  — designer API base URL
 *   disabled      bool    — disable interaction (e.g. when SQL has been edited)
 */
export default function ConnectionPicker({ value, onChange, apiBase, disabled = false }) {
  const [connections, setConnections] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    designerFetch(connectionsUrl(apiBase))
      .then(data => {
        if (cancelled) return
        setConnections(Array.isArray(data) ? data : [])
        setError(null)
      })
      .catch(err => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.warn('ConnectionPicker: failed to load connections', err)
        setError(err.message || 'Failed to load connections')
        // Fall back to local-only so the wizard still works
        setConnections([{ id: 'local_pg', name: 'Local Postgres', engine: 'postgres_local', is_active: true }])
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [apiBase])

  const handleChange = (e) => {
    const newId = e.target.value
    const meta = connections.find(c => String(c.id) === String(newId))
    onChange(newId, meta || null)
  }

  // Hide the dropdown entirely when only Local Postgres exists — single
  // option means there's no choice to make. Once a CH connection is
  // added, the dropdown lights up automatically. Avoids visual clutter
  // for installations that haven't adopted CH yet.
  if (!loading && connections.length <= 1) {
    return null
  }

  return (
    <div className="wb-field-group" style={{ marginBottom: 12 }}>
      <label className="wb-label" htmlFor="wb-connection-picker">
        Database Connection
      </label>
      <select
        id="wb-connection-picker"
        className="wb-select"
        value={value || 'local_pg'}
        onChange={handleChange}
        disabled={disabled || loading}
        style={{ maxWidth: 360 }}
      >
        {loading ? (
          <option value="local_pg">Loading…</option>
        ) : (
          connections.map(c => (
            <option key={c.id} value={c.id}>
              {c.name}{c.engine && c.engine !== 'postgres_local' ? ` (${c.engine})` : ''}
            </option>
          ))
        )}
      </select>
      {error && (
        <div style={{ color: '#b91c1c', fontSize: 12, marginTop: 4 }}>
          ⚠ {error} — falling back to Local Postgres.
        </div>
      )}
      <div style={{ color: '#6b7280', fontSize: 12, marginTop: 4 }}>
        Schema sources below are filtered to this connection. Switching
        clears any picked sources to avoid mixing engines in one widget.
      </div>
    </div>
  )
}
