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

# Tone palette for the opt-in status pills (title status / tile status). The
# SQL returns a TONE WORD, never a colour; unknown or blank words fall back to
# neutral. Values mirror widget_config_defaults.DEFAULT_STYLES + NEUTRAL_STATUS
# (the attribute_grid / metric_list palette) — duplicated here because this
# module must stay import-free so the standalone tests can load it by path.
TONE_COLORS = {
    'info':    {'color': '#087ad8', 'background': '#e7f1fb'},
    'success': {'color': '#059669', 'background': '#ecfdf5'},
    'warning': {'color': '#d97706', 'background': '#fef3c7'},
    'danger':  {'color': '#dc2626', 'background': '#fee2e2'},
    'neutral': {'color': '#6b7280', 'background': '#f3f4f6'},
}


def _status(text, tone):
    """Status pill payload: text + the tone's colours (unknown → neutral)."""
    colours = TONE_COLORS.get(str(tone or '').strip().lower()) or TONE_COLORS['neutral']
    return {'text': text, 'color': colours['color'],
            'background': colours['background']}


def _truthy(val):
    """visual_config booleans arrive as bool, int or text ('true')."""
    if isinstance(val, str):
        return val.strip().lower() in ('1', 'true', 'yes', 'on')
    return bool(val)


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
        empty = {'type': 'record_header', 'empty': True}
        # Opt-in placeholder ("Find a member to begin"). Absent → the grid
        # drops the empty header exactly as before.
        empty_text = str(config.get('empty_text') or '').strip()
        if empty_text:
            empty['empty_text'] = empty_text
        return empty
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

    payload = {
        'type': 'record_header',
        'title': title,
        'avatar': avatar,
        'fields': fields,
    }

    # ── Scorecard layout (opt-in: header_layout == 'scorecard') ──────────
    # Classic payload above is byte-identical when the key is absent. The
    # scorecard adds subtitle / stat tiles / chips from their own columns,
    # with the same fail-closed rule for a configured-but-missing column.
    if (config.get('header_layout') or 'classic') != 'scorecard':
        return payload

    payload['layout'] = 'scorecard'
    shape = config.get('avatar_shape') or 'rounded'
    avatar['shape'] = shape if shape in ('circle', 'rounded') else 'rounded'

    sub_col = (config.get('subtitle_column') or '').strip()
    if sub_col:
        if sub_col not in col_idx:
            return {'type': 'record_header',
                    'error': 'Configured subtitle column not found: %s' % sub_col}
        payload['subtitle'] = _cell(row, col_idx[sub_col])
    else:
        payload['subtitle'] = ''

    # ── Opt-in identity extras — an absent config key emits NO payload key,
    #    so headers configured before these existed are byte-identical. ────
    # subtitle_items: [{column, icon}] → "icon value" items; the renderers
    # show them instead of the plain subtitle when present.
    items_cfg = _as_list(config.get('subtitle_items'))
    if items_cfg:
        items = []
        for spec in items_cfg:
            col = str(spec.get('column') or '').strip()
            if not col:
                continue
            if col not in col_idx:
                return {'type': 'record_header',
                        'error': 'Configured subtitle item column not found: %s' % col}
            val = _cell(row, col_idx[col])
            if val:
                items.append({'icon': str(spec.get('icon') or '').strip(), 'value': val})
        payload['subtitle_items'] = items

    # title_status_column (+ optional tone column) → coloured pill by the title.
    ts_col = str(config.get('title_status_column') or '').strip()
    if ts_col:
        if ts_col not in col_idx:
            return {'type': 'record_header',
                    'error': 'Configured title status column not found: %s' % ts_col}
        tone_col = str(config.get('title_status_tone_column') or '').strip()
        if tone_col and tone_col not in col_idx:
            return {'type': 'record_header',
                    'error': 'Configured title status tone column not found: %s' % tone_col}
        text = _cell(row, col_idx[ts_col])
        if text:
            payload['title_status'] = _status(
                text, _cell(row, col_idx[tone_col]) if tone_col else '')

    # badges: [{column, label, copy}] → identifier pills under the subtitle.
    # A NULL/blank value hides its badge rather than printing an empty pill.
    badges_cfg = _as_list(config.get('badges'))
    if badges_cfg:
        badges = []
        for spec in badges_cfg:
            col = str(spec.get('column') or '').strip()
            if not col:
                continue
            if col not in col_idx:
                return {'type': 'record_header',
                        'error': 'Configured badge column not found: %s' % col}
            val = _cell(row, col_idx[col])
            if not val:
                continue
            badges.append({
                'key': col,
                'label': (spec.get('label') or overrides.get(col) or col),
                'value': val,
                'copy': _truthy(spec.get('copy')),
            })
        payload['badges'] = badges

    # Tile colours: per-tile override → header-wide default → blank (CSS
    # default). Blank keys are omitted from the payload so the renderers'
    # stylesheet defaults apply unchanged.
    defaults = {
        'icon_color':  (config.get('stat_icon_color') or '').strip(),
        'label_color': (config.get('stat_label_color') or '').strip(),
        'value_color': (config.get('stat_value_color') or '').strip(),
        'bg':          (config.get('stat_bg') or '').strip(),
    }
    stats = []
    for spec in _as_list(config.get('stats')):
        col = str((spec or {}).get('column') or '').strip()
        if not col:
            continue
        if col not in col_idx:
            return {'type': 'record_header',
                    'error': 'Configured stat column not found: %s' % col}
        fmt_kind = spec.get('format') or 'number'
        stat = {
            'key': col,
            'label': (spec.get('label') or overrides.get(col) or col),
            'icon': (spec.get('icon') or ''),
            'value': _format_stat(row[col_idx[col]], fmt_kind),
        }
        for k, default in defaults.items():
            colour = (str(spec.get(k) or '').strip()) or default
            if colour:
                stat[k] = colour
        # Optional trend vs a prior-value column (same row): arrow + delta.
        prior_col = str(spec.get('prior_column') or '').strip()
        if prior_col:
            if prior_col not in col_idx:
                return {'type': 'record_header',
                        'error': 'Configured prior column not found: %s' % prior_col}
            trend = _trend(row[col_idx[col]], row[col_idx[prior_col]], fmt_kind,
                           higher_is_better=spec.get('higher_is_better', True))
            if trend:
                stat['trend'] = trend
        # Optional caption: small text after the value (e.g. "Aug 2026").
        cap_col = str(spec.get('caption_column') or '').strip()
        if cap_col:
            if cap_col not in col_idx:
                return {'type': 'record_header',
                        'error': 'Configured caption column not found: %s' % cap_col}
            caption = _cell(row, col_idx[cap_col])
            if caption:
                stat['caption'] = caption
        # Optional status pill (+ tone column). color_value_by_status paints
        # the value in the pill's colour (e.g. MLR red above 100%).
        st_col = str(spec.get('status_column') or '').strip()
        if st_col:
            if st_col not in col_idx:
                return {'type': 'record_header',
                        'error': 'Configured status column not found: %s' % st_col}
            tone_col = str(spec.get('status_tone_column') or '').strip()
            if tone_col and tone_col not in col_idx:
                return {'type': 'record_header',
                        'error': 'Configured status tone column not found: %s' % tone_col}
            text = _cell(row, col_idx[st_col])
            if text:
                stat['status'] = _status(
                    text, _cell(row, col_idx[tone_col]) if tone_col else '')
                if _truthy(spec.get('color_value_by_status')):
                    stat['value_color'] = stat['status']['color']
        stats.append(stat)
    payload['stats'] = stats
    # stats_style 'panel' = one grey panel with hairline dividers (the
    # prototype look); anything else keeps today's tiles and emits no key.
    if str(config.get('stats_style') or '').strip() == 'panel':
        payload['stats_style'] = 'panel'

    chips_col = (config.get('chips_column') or '').strip()
    chips = []
    if chips_col:
        if chips_col not in col_idx:
            return {'type': 'record_header',
                    'error': 'Configured chips column not found: %s' % chips_col}
        chips = _as_chips(row[col_idx[chips_col]])
    payload['chips'] = chips
    payload['chips_label'] = config.get('chips_label') or ''
    payload['chip_color'] = config.get('chip_color') or ''
    payload['chip_text_color'] = config.get('chip_text_color') or ''
    return payload


def _as_list(value):
    """``stats`` may arrive as a list or as a JSON string (visual_config)."""
    if not value:
        return []
    if isinstance(value, str):
        import json
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return []
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _format_stat(val, fmt):
    """number → thousands separators (integral stays integral); percent →
    one decimal + '%'; text/other → as text. NULL → ''. Non-numeric input
    under a numeric format falls back to text (never raises)."""
    if val is None:
        return ''
    if fmt in ('number', 'percent'):
        try:
            num = float(val)
        except (TypeError, ValueError):
            return str(val)
        if fmt == 'percent':
            return '%.1f%%' % num
        if num == int(num):
            return '{:,}'.format(int(num))
        return '{:,.2f}'.format(num)
    return str(val)


def _trend(cur, prior, fmt_kind, higher_is_better=True):
    """Direction + formatted delta of ``cur`` vs ``prior``. ``None`` when
    either side is missing/non-numeric (no arrow rendered). Percent format →
    delta in points ('+1.2 pts'); number → signed integer/decimal."""
    try:
        c = float(cur)
        p = float(prior)
    except (TypeError, ValueError):
        return None
    diff = c - p
    if diff > 0:
        direction = 'up'
    elif diff < 0:
        direction = 'down'
    else:
        direction = 'flat'
    good = bool(higher_is_better) if higher_is_better not in ('false', 'False', 0, '0') else False
    if direction == 'flat':
        status = 'neutral'
    else:
        status = 'good' if (direction == 'up') == good else 'bad'
    if direction == 'flat':
        return {'dir': 'flat', 'status': 'neutral', 'delta': ''}
    sign = '+' if diff > 0 else '-'
    mag = abs(diff)
    if fmt_kind == 'percent':
        delta = '%s%.1f pts' % (sign, mag)
    elif mag == int(mag):
        delta = '%s%s' % (sign, '{:,}'.format(int(mag)))
    else:
        delta = '%s%s' % (sign, '{:,.2f}'.format(mag))
    return {'dir': direction, 'status': status, 'delta': delta}


def _as_chips(val):
    """JSON array (of strings) or CSV text → list of non-blank strings."""
    if val is None:
        return []
    if isinstance(val, (list, tuple)):
        items = val
    else:
        text = str(val).strip()
        if not text:
            return []
        items = None
        if text.startswith('['):
            import json
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    items = parsed
            except (TypeError, ValueError):
                items = None
        if items is None:
            items = text.split(',')
    return [str(x).strip() for x in items if str(x).strip()]
