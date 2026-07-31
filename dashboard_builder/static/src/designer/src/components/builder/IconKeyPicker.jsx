// IconKeyPicker — searchable dashboard.icon registry picker (active icons
// only; archived icons keep rendering in saved widgets but are not offered
// for NEW selection). Value is always a registry KEY, never a CSS class.
import React, { useEffect, useMemo, useState } from 'react'
import { designerFetch } from '../../api/client'

let _cache = null // module-level: one fetch per designer session

export default function IconKeyPicker({ apiBase, value, onChange, allowEmpty = true, placeholder = 'icon key' }) {
  const [icons, setIcons] = useState(_cache || [])
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (_cache) return
    designerFetch(`${apiBase}/dashboard/designer/api/icons`)
      .then((rows) => { _cache = rows || []; setIcons(_cache) })
      .catch(() => setIcons([]))
  }, [apiBase])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return icons
    return icons.filter(i => i.key.includes(q)
      || (i.label || '').toLowerCase().includes(q)
      || (i.category || '').toLowerCase().includes(q))
  }, [icons, query])

  const current = icons.find(i => i.key === value)

  return (
    <div className="wb-iconpicker" style={{ position: 'relative' }}>
      <button
        type="button"
        className="btn btn-sm btn-outline-secondary d-flex align-items-center gap-2"
        onClick={() => setOpen(o => !o)}
        style={{ minWidth: 140, justifyContent: 'flex-start' }}
      >
        {current
          ? <><i className={`fa ${current.fa_class}`} /> <span>{current.key}</span></>
          : <span className="text-muted">{value || placeholder}</span>}
      </button>
      {open && (
        <div
          className="border rounded bg-white shadow-sm p-2"
          style={{ position: 'absolute', zIndex: 40, width: 260, maxHeight: 280, overflowY: 'auto', top: '100%', left: 0 }}
        >
          <input
            className="form-control form-control-sm mb-2"
            placeholder="Search icons…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            autoFocus
          />
          {allowEmpty && (
            <button type="button" className="dropdown-item small text-muted"
              onClick={() => { onChange(''); setOpen(false) }}>
              (no icon)
            </button>
          )}
          {filtered.map(i => (
            <button key={i.key} type="button"
              className="dropdown-item small d-flex align-items-center gap-2"
              onClick={() => { onChange(i.key); setOpen(false) }}>
              <i className={`fa ${i.fa_class}`} style={{ width: 16 }} />
              <span>{i.label}</span>
              <code className="ms-auto" style={{ fontSize: 10 }}>{i.key}</code>
            </button>
          ))}
          {filtered.length === 0 && (
            <div className="small text-muted px-2 py-1">No icons match.</div>
          )}
        </div>
      )}
    </div>
  )
}
