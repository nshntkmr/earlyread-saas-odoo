import React from 'react'
import ConnectionPicker from './ConnectionPicker'
import CustomSqlEditor from './CustomSqlEditor'
import { anyChildInherits } from './compositeUtils'

const STRATEGIES = [
  {
    key: 'shared',
    title: 'Shared Parent SQL',
    icon: 'fa-database',
    desc: 'One SQL query on the parent — children inherit its rows. Best when '
        + 'every block is a different view of the same result set.',
  },
  {
    key: 'own',
    title: 'Each Child Own SQL',
    icon: 'fa-code-fork',
    desc: 'Every child runs its own independent query. Best when blocks need '
        + 'different grains (e.g. a table adding a UNION ALL Total row).',
  },
]

const styles = {
  cards: { display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, marginTop: 8 },
  card: {
    display: 'flex', flexDirection: 'column', gap: 6, padding: '14px 16px',
    border: '1px solid #e5e7eb', borderRadius: 8, background: '#fff',
    cursor: 'pointer', textAlign: 'left',
  },
  cardActive: { borderColor: '#0d9488', boxShadow: '0 0 0 2px rgba(13,148,136,.25)' },
  cardTitle: { fontWeight: 600, fontSize: 14, color: '#1f2937' },
  cardDesc: { fontSize: 12, color: '#6b7280', lineHeight: 1.4 },
}

/**
 * Composite body for the Data Source step — three blocks in one step:
 *   1. Database Connection (shared by parent + ALL children in v1)
 *   2. Data Strategy default (shared parent SQL vs each child own SQL)
 *   3. Parent SQL editor — shown when the strategy is 'shared' OR any child
 *      still inherits (a child overridden to inherit needs the parent query).
 *
 * Composite is custom-SQL only in v1 — there is no Visual Builder / AI mode
 * toggle here (forced-SQL precedent: sankey / sankey_member_flow).
 */
export default function CompositeDataSource({
  connectionId,
  strategy,
  customSql,
  compositeChildren,
  onConnectionChange,
  onStrategyChange,
  onCustomSqlUpdate,
  apiBase,
  appContext,
}) {
  const showParentSql = strategy === 'shared' || anyChildInherits(compositeChildren)

  return (
    <div>
      <h3 className="wb-step-title">Data Source</h3>

      {/* Connection — parent and all children share it (v1: no cross-engine) */}
      <ConnectionPicker
        value={connectionId || 'local_pg'}
        onChange={onConnectionChange}
        apiBase={apiBase}
      />
      <p className="wb-hint" style={{ fontSize: 12, color: '#6c757d', marginTop: 4 }}>
        The parent query and every child block use this connection. Child schema
        sources are limited to it.
      </p>

      {/* Data strategy default */}
      <div className="wb-field-group" style={{ marginTop: 16 }}>
        <label className="wb-label">Data Strategy</label>
        <div style={styles.cards}>
          {STRATEGIES.map(s => {
            const active = (strategy || 'shared') === s.key
            return (
              <button
                key={s.key}
                type="button"
                style={{ ...styles.card, ...(active ? styles.cardActive : {}) }}
                onClick={() => onStrategyChange(s.key)}
              >
                <span style={styles.cardTitle}>
                  <i className={`fa ${s.icon} me-2`} style={{ color: active ? '#0d9488' : '#9ca3af' }} />
                  {s.title}
                </span>
                <span style={styles.cardDesc}>{s.desc}</span>
              </button>
            )
          })}
        </div>
        <p className="wb-hint" style={{ fontSize: 12, color: '#6c757d', marginTop: 6 }}>
          This sets the default for new child blocks — each child can still be
          switched individually in the next step.
        </p>
      </div>

      {/* Parent SQL (composite is custom-SQL only in v1) */}
      {showParentSql ? (
        <div style={{ marginTop: 16 }}>
          <label className="wb-label">Parent SQL</label>
          <p className="wb-hint" style={{ fontSize: 12, color: '#6c757d', marginTop: 2 }}>
            Runs once; children with <strong>Inherit Parent</strong> share its rows.
          </p>
          <CustomSqlEditor
            sql={(customSql || {}).sql || ''}
            xColumn={(customSql || {}).xColumn || ''}
            yColumns={(customSql || {}).yColumns || ''}
            seriesColumn={(customSql || {}).seriesColumn || ''}
            schemaSourceId={(customSql || {}).schemaSourceId || null}
            testResult={(customSql || {}).testResult}
            testParams={(customSql || {}).testParams || {}}
            onUpdate={onCustomSqlUpdate}
            apiBase={apiBase}
            appContext={appContext}
            connectionId={connectionId || 'local_pg'}
            chartType="composite"
          />
        </div>
      ) : (
        <div className="wb-step-skip" style={{ marginTop: 16 }}>
          <i className="fa fa-info-circle me-2" />
          Every child uses its own SQL — define each query in the next step.
        </div>
      )}
    </div>
  )
}
