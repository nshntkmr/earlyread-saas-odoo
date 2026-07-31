# -*- coding: utf-8 -*-
"""Pure, shared formatter for the ``record_header`` widget.

SINGLE SOURCE OF TRUTH used by BOTH:
  • posterra_portal ``dashboard.widget._build_record_header_data`` (portal runtime)
  • dashboard_builder ``preview_formatter.format_preview`` (designer preview)

No ORM / no I/O — inputs are already-resolved SQL columns/rows + an
already-merged config dict. This keeps portal render and designer preview
byte-for-byte identical (one implementation of cardinality, missing-column,
NULL, initials, overrides, and payload rules).

Fail-closed contract (an identity header must never show a wrong/partial
identity):
  • 0 rows                       → {'empty': True}
  • >1 row                       → {'error': ...}
  • 1 row but no columns         → {'error': ...}
  • duplicate identity alias     → {'error': ...}
  • configured title column gone → {'error': ...}
  • configured footer column gone→ {'error': ...}
  • SQL NULL in a valid column   → '' (blank, allowed)
  • no configured title column   → first result column (documented fallback)
"""

DEFAULT_AVATAR_COLOR = '#087ad8'


def _cell(row, idx):
    """Render a cell as text; DB NULL/None → '' (never the string 'None')."""
    if idx is None:
        return ''
    val = row[idx]
    return '' if val is None else str(val)


def _initials(title):
    """One word → first char; multiple → first char of first+last word;
    uppercased, max 2; blank → blank."""
    parts = [p for p in str(title or '').split() if p]
    if not parts:
        return ''
    letters = parts[0][:1] if len(parts) == 1 else (parts[0][:1] + parts[-1][:1])
    return letters.upper()[:2]


def format_record_header(cols, rows, config):
    """Return the render-ready ``record_header`` payload (fail-closed).

    config keys:
      x_column        — title column (default: first result column)
      y_columns       — CSV of footer value columns
      avatar_mode     — 'initials' | 'none'   (default 'initials')
      avatar_color    — hex string
      label_overrides — {column_name: 'Label'}
    """
    config = config or {}
    cols = list(cols or [])
    rows = list(rows or [])

    # ── Row cardinality (fail closed) ──────────────────────────────────
    if not rows:
        return {'type': 'record_header', 'empty': True}
    if len(rows) > 1:
        return {'type': 'record_header',
                'error': 'Identity query returned multiple rows'}
    if not cols:
        return {'type': 'record_header',
                'error': 'Identity query returned no columns'}

    row = rows[0]
    # Reject duplicate/ambiguous aliases used for identity fields.
    col_idx = {}
    for i, c in enumerate(cols):
        if c in col_idx:
            return {'type': 'record_header',
                    'error': 'Duplicate result column alias: %s' % c}
        col_idx[c] = i

    # ── Title (documented fallback = first column) ─────────────────────
    title_col = config.get('x_column') or cols[0]
    if title_col not in col_idx:
        return {'type': 'record_header',
                'error': 'Configured title column not found: %s' % title_col}
    title = _cell(row, col_idx[title_col])

    # ── Footer label/value pairs ───────────────────────────────────────
    overrides = config.get('label_overrides') or {}
    y_cols = [c.strip() for c in str(config.get('y_columns') or '').split(',') if c.strip()]
    fields = []
    for c in y_cols:
        if c not in col_idx:
            return {'type': 'record_header',
                    'error': 'Configured footer column not found: %s' % c}
        fields.append({
            'key': c,
            'label': overrides.get(c) or c,
            'value': _cell(row, col_idx[c]),
        })

    # ── Avatar (initials | none only this phase) ───────────────────────
    mode = config.get('avatar_mode') or 'initials'
    if mode not in ('initials', 'none'):
        mode = 'initials'
    avatar = {
        'mode': mode,
        'text': _initials(title) if mode == 'initials' else '',
        'color': config.get('avatar_color') or DEFAULT_AVATAR_COLOR,
    }

    return {
        'type': 'record_header',
        'title': title,
        'avatar': avatar,
        'fields': fields,
    }
