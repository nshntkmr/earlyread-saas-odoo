import React from 'react'

const AGG_FUNCS = ['SUM', 'COUNT', 'AVG', 'MIN', 'MAX', 'WAVG']

/**
 * Step 3 (Visual mode): Map X, Y, series columns with aggregation.
 *
 * Props:
 *   sources    — [{id, name, columns: [{column_name, display_name, data_type, is_measure, is_dimension}]}]
 *   columns    — { x: {source_id, column, alias}, y: [{source_id, column, agg, alias, displayName}], series: {...} }
 *   orderBy    — [{alias, dir}]
 *   limit      — number
 *   chartType  — string (for column links visibility)
 *   columnLinks — [{column, page_key, filter_param}]
 *   onUpdate   — ({columns, orderBy, limit, columnLinks}) => void
 */
export default function ColumnMapper({
  sources, columns, orderBy, limit, chartType, columnLinks,
  visualFlags,
  onUpdate,
}) {
  // Flatten all columns across sources
  const allCols = sources.flatMap(src =>
    (src.columns || []).map(c => ({ ...c, source_id: src.id, source_name: src.name }))
  )
  const dimensions = allCols.filter(c => c.is_dimension)
  const measures = allCols.filter(c => c.is_measure)

  const setX = (colKey) => {
    if (!colKey) {
      onUpdate({ columns: { ...columns, x: null } })
      return
    }
    const [sid, cname] = colKey.split(':')
    const col = allCols.find(c => c.source_id === Number(sid) && c.column_name === cname)
    onUpdate({
      columns: {
        ...columns,
        x: { source_id: Number(sid), column: cname, alias: col?.column_name || cname },
      },
    })
  }

  const addY = () => {
    onUpdate({
      columns: {
        ...columns,
        y: [...(columns.y || []), { source_id: null, column: '', agg: 'sum', alias: '', displayName: '', weightColumn: '' }],
      },
    })
  }

  const updateY = (idx, updates) => {
    const yList = [...(columns.y || [])]
    yList[idx] = { ...yList[idx], ...updates }
    onUpdate({ columns: { ...columns, y: yList } })
  }

  const removeY = (idx) => {
    const yList = (columns.y || []).filter((_, i) => i !== idx)
    onUpdate({ columns: { ...columns, y: yList } })
  }

  const setSeries = (colKey) => {
    if (!colKey) {
      onUpdate({ columns: { ...columns, series: null } })
      return
    }
    const [sid, cname] = colKey.split(':')
    onUpdate({
      columns: {
        ...columns,
        series: { source_id: Number(sid), column: cname, alias: cname },
      },
    })
  }

  return (
    <div>
      <h3 className="wb-step-title">Configure Columns</h3>

      {/* X-axis */}
      <div className="wb-field-group">
        <label className="wb-label">X-Axis / Labels</label>
        <select
          className="wb-select"
          value={columns.x ? `${columns.x.source_id}:${columns.x.column}` : ''}
          onChange={e => setX(e.target.value)}
        >
          <option value="">-- Select dimension --</option>
          {dimensions.map(c => (
            <option key={`${c.source_id}:${c.column_name}`} value={`${c.source_id}:${c.column_name}`}>
              {c.display_name} ({c.source_name}.{c.column_name})
            </option>
          ))}
        </select>
      </div>

      {/* Y-axis columns */}
      <div className="wb-field-group">
        <label className="wb-label">Y-Axis / Values</label>
        {/* Contextual hint for gauge bullet multi-row */}
        {chartType === 'gauge' && visualFlags?.gauge_style === 'bullet' && (
          <div style={{ fontSize: 11, color: '#6b7280', background: '#f0fdf4', border: '1px solid #bbf7d0',
                        borderRadius: 4, padding: '6px 10px', marginBottom: 8 }}>
            <i className="fa fa-info-circle" style={{ marginRight: 6, color: '#0d9488' }} />
            <strong>Multi-row bullet:</strong> X = metric name, Y1 = actual value, Y2 = benchmark/target value (optional), Y3 = benchmark label text (optional)
          </div>
        )}
        {chartType === 'gauge' && visualFlags?.gauge_style === 'traffic_light_rag' && (
          <div style={{ fontSize: 11, color: '#6b7280', background: '#fef2f2', border: '1px solid #fecaca',
                        borderRadius: 4, padding: '6px 10px', marginBottom: 8 }}>
            <i className="fa fa-info-circle" style={{ marginRight: 6, color: '#ef4444' }} />
            <strong>Traffic Light:</strong> X = value, Y1 = red threshold (optional), Y2 = green threshold (optional), Y3 = badge text (optional). Leave Y empty to use static thresholds from settings.
          </div>
        )}
        {chartType === 'gauge' && visualFlags?.gauge_style === 'percentile_rank' && (
          <div style={{ fontSize: 11, color: '#6b7280', background: '#eff6ff', border: '1px solid #bfdbfe',
                        borderRadius: 4, padding: '6px 10px', marginBottom: 8 }}>
            <i className="fa fa-info-circle" style={{ marginRight: 6, color: '#2563eb' }} />
            <strong>Percentile:</strong> X = percentile value (0-100), Y1 = subtitle, Y2 = actual value, Y3 = actual label
          </div>
        )}
        {chartType === 'gauge' && visualFlags?.gauge_style === 'multi_ring' && (
          <div style={{ fontSize: 11, color: '#6b7280', background: '#fefce8', border: '1px solid #fde68a',
                        borderRadius: 4, padding: '6px 10px', marginBottom: 8 }}>
            <i className="fa fa-info-circle" style={{ marginRight: 6, color: '#d97706' }} />
            <strong>Multi-ring:</strong> X = metric name (one row per ring), Y1 = metric value
          </div>
        )}
        {(columns.y || []).map((yCol, idx) => (
          <div key={idx} className="wb-y-row">
            <span className="wb-y-num">#{idx + 1}</span>
            <select
              className="wb-select wb-select--sm"
              value={yCol.source_id && yCol.column ? `${yCol.source_id}:${yCol.column}` : ''}
              onChange={e => {
                if (!e.target.value) return
                const [sid, cname] = e.target.value.split(':')
                const col = allCols.find(c => c.source_id === Number(sid) && c.column_name === cname)
                updateY(idx, {
                  source_id: Number(sid),
                  column: cname,
                  alias: col?.column_name || cname,
                  displayName: col?.display_name || cname,
                })
              }}
            >
              <option value="">-- Column --</option>
              {measures.map(c => (
                <option key={`${c.source_id}:${c.column_name}`} value={`${c.source_id}:${c.column_name}`}>
                  {c.display_name} ({c.column_name})
                </option>
              ))}
            </select>

            <div className="wb-agg-radio">
              {AGG_FUNCS.map(fn => (
                <label key={fn} className="wb-radio-label">
                  <input
                    type="radio"
                    name={`agg-${idx}`}
                    value={fn.toLowerCase()}
                    checked={(yCol.agg || 'sum') === fn.toLowerCase()}
                    onChange={() => updateY(idx, { agg: fn.toLowerCase(), ...(fn.toLowerCase() !== 'wavg' ? { weightColumn: '' } : {}) })}
                  />
                  {fn}
                </label>
              ))}
            </div>

            {yCol.agg === 'wavg' && (
              <select
                className="wb-select wb-select--sm"
                value={yCol.weightColumn || ''}
                onChange={e => updateY(idx, { weightColumn: e.target.value })}
                style={{ marginTop: 4 }}
              >
                <option value="">-- Weight column --</option>
                {measures.filter(c => c.column_name !== yCol.column).map(c => (
                  <option key={c.column_name} value={c.column_name}>
                    {c.display_name} ({c.column_name})
                  </option>
                ))}
              </select>
            )}

            <input
              type="text"
              className="wb-input wb-input--sm"
              value={yCol.displayName || ''}
              onChange={e => updateY(idx, { displayName: e.target.value })}
              placeholder="Display as..."
            />

            <button type="button" className="wb-btn-icon" onClick={() => removeY(idx)}>
              <i className="fa fa-trash" />
            </button>
          </div>
        ))}

        <button type="button" className="wb-btn wb-btn--outline" onClick={addY}>
          <i className="fa fa-plus" /> Add Value Column
        </button>
      </div>

      {/* Series / Group By */}
      <div className="wb-field-group">
        <label className="wb-label">Group By (Series)</label>
        <select
          className="wb-select"
          value={columns.series ? `${columns.series.source_id}:${columns.series.column}` : ''}
          onChange={e => setSeries(e.target.value)}
        >
          <option value="">(none)</option>
          {dimensions.map(c => (
            <option key={`${c.source_id}:${c.column_name}`} value={`${c.source_id}:${c.column_name}`}>
              {c.display_name} ({c.column_name})
            </option>
          ))}
        </select>
      </div>

      {/* Sort + Limit */}
      <div className="wb-inline-fields">
        <div className="wb-field-group">
          <label className="wb-label">Sort By</label>
          <select
            className="wb-select"
            value={orderBy?.[0]?.alias || ''}
            onChange={e => {
              const alias = e.target.value
              onUpdate({ orderBy: alias ? [{ alias, dir: orderBy?.[0]?.dir || 'DESC' }] : [] })
            }}
          >
            <option value="">(none)</option>
            {(columns.y || []).filter(y => y.column).map(y => (
              <option key={y.alias || y.column} value={y.alias || y.column}>
                {y.displayName || y.column}
              </option>
            ))}
          </select>
        </div>

        <div className="wb-field-group">
          <label className="wb-label">Direction</label>
          <select
            className="wb-select"
            value={orderBy?.[0]?.dir || 'DESC'}
            onChange={e => {
              if (orderBy?.[0]) {
                onUpdate({ orderBy: [{ ...orderBy[0], dir: e.target.value }] })
              }
            }}
          >
            <option value="DESC">DESC</option>
            <option value="ASC">ASC</option>
          </select>
        </div>

        <div className="wb-field-group">
          <label className="wb-label">Limit</label>
          <input
            type="number"
            className="wb-input"
            value={limit || ''}
            onChange={e => onUpdate({ limit: Number(e.target.value) || null })}
            min={1}
            max={1000}
            placeholder="10"
          />
        </div>
      </div>

      {/* Column links (table type only) */}
      {chartType === 'table' && (
        <div className="wb-field-group">
          <label className="wb-label">Column Links (clickable columns)</label>
          <p className="wb-hint">Configure after saving — edit in the widget Actions tab.</p>
        </div>
      )}
    </div>
  )
}
