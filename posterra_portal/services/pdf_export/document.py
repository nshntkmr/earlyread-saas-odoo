# -*- coding: utf-8 -*-
"""Dataset → print HTML (QWeb) + Gotenberg footer HTML.

The template (``posterra_portal.pdf_export_document``) only lays out a
sanitised view model built here: every admin colour goes through
``safe_color``, values are plain strings (QWeb escapes them) and table cells
are pre-escaped ``Markup`` from ``cell_format``. Nothing is fetched at render
time — the logo is an inline data URI, and the only script is the chart
block from ``charts.chart_scripts`` (vendored library as a data URI + the
server's chart options as escaped JSON).
"""

import base64
import datetime
import re

from markupsafe import Markup, escape

from .cell_format import safe_color
from .charts import CHART_PLACEHOLDER, chart_scripts
from .icons import IconSet, font_face_css
from .placement import effective_columns, resolve_placement
from .render_client import MARGIN_LEFT_IN, MARGIN_RIGHT_IN, PAPER_SIZES_IN

_PLACEHOLDER_RE = re.compile(r'\{([A-Za-z0-9_]+)\}')
DEFAULT_TITLE = '{app_name} — {page_name} — {tab_name}'

# Print grid geometry (must match the template CSS): 12 columns, 7px gap,
# cards with 8px padding + 1px border. Charts are drawn by script BEFORE the
# print layout exists, so each chart gets explicit pixel dimensions computed
# from the paper width (1in = 96 CSS px).
GRID_COLUMNS = 12
GRID_GAP_PX = 7
CARD_CHROME_PX = 18
CHART_MIN_H, CHART_MAX_H = 160, 440
SPARKLINE_H = 40                                # portal: EChartWidget height={40}
MINI_GAUGE_DEFAULT, MINI_GAUGE_MIN, MINI_GAUGE_MAX = 64, 40, 120   # payload mini_gauge_size


def _mini_gauge_size(payload):
    try:
        size = int(payload.get('mini_gauge_size') or MINI_GAUGE_DEFAULT)
    except (TypeError, ValueError):
        size = MINI_GAUGE_DEFAULT
    return max(MINI_GAUGE_MIN, min(MINI_GAUGE_MAX, size))


def content_width_px(paper, orientation):
    w, h = PAPER_SIZES_IN.get(paper or 'letter', PAPER_SIZES_IN['letter'])
    if orientation == 'landscape':
        w, h = h, w
    return (w - MARGIN_LEFT_IN - MARGIN_RIGHT_IN) * 96


def card_inner_width_px(content_px, span):
    n = int(span) if str(span) in ('3', '4', '6', '8', '12') else GRID_COLUMNS
    col = (content_px - (GRID_COLUMNS - 1) * GRID_GAP_PX) / GRID_COLUMNS
    return max(80, int(col * n + (n - 1) * GRID_GAP_PX - CARD_CHROME_PX))


def resolve_template(template, values):
    """``{name}`` placeholders → values; unknown names → ''."""
    out = _PLACEHOLDER_RE.sub(lambda m: str(values.get(m.group(1), '')), template or '')
    out = re.sub(r'(\s*—\s*)+$', '', out.strip())          # dangling separators
    return re.sub(r'\s*—\s*—\s*', ' — ', out).strip()


def logo_data_uri(app):
    raw = app.logo
    if not raw:
        return ''
    try:
        data = base64.b64decode(raw)
    except (ValueError, TypeError):
        return ''
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        mime = 'image/png'
    elif data[:3] == b'\xff\xd8\xff':
        mime = 'image/jpeg'
    elif data[:6] in (b'GIF87a', b'GIF89a'):
        mime = 'image/gif'
    elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        mime = 'image/webp'
    elif b'<svg' in data[:512].lower():
        mime = 'image/svg+xml'
    else:
        return ''
    return f'data:{mime};base64,{base64.b64encode(data).decode()}'


_ARROWS = {'status-up': ('▲', '#059669'), 'status-down': ('▼', '#dc2626'),
           'status-neutral': ('–', '#6b7280'), 'status-warning': ('!', '#d97706')}


def _kpi_view(block):
    p = block.get('payload') or {}
    arrow, arrow_color = _ARROWS.get(p.get('status_css') or '', ('', ''))
    secondary = p.get('secondary')
    if isinstance(secondary, dict):
        secondary = secondary.get('text') or ''
    view = {
        'title': block.get('name') or p.get('label') or '',
        'value': str(p.get('formatted_value') if p.get('formatted_value') is not None else ''),
        'value_color': safe_color(p.get('value_color')),
        'secondary': str(secondary or ''),
        'arrow': arrow, 'arrow_color': arrow_color,
        'variant': p.get('kpi_variant') or '',
    }
    if view['variant'] == 'comparison':
        diff_arrow, diff_color = _ARROWS.get(p.get('diff_status') or '', ('', '#6b7280'))
        view.update({
            'current_label': str(p.get('current_label') or ''),
            'prior_label': str(p.get('prior_label') or ''),
            'prior_value': str(p.get('prior_formatted') or ''),
            'diff': str(p.get('diff_annotation') or ''),
            'diff_color': diff_color,
        })
    if view['variant'] in ('progress', 'mini_gauge') and p.get('progress_pct') is not None:
        try:
            raw_pct = float(p.get('progress_pct'))
        except (TypeError, ValueError):
            raw_pct = 0.0
        pct = max(0.0, min(100.0, raw_pct))
        view.update({'progress_pct': f'{pct:.1f}'.rstrip('0').rstrip('.'),
                     'progress_color': safe_color(p.get('bar_color'), '#0d9488'),
                     'progress_note': str(p.get('progress_annotation') or ''),
                     # portal: status-up when at/above 100 % of target, else status-down
                     'progress_note_color': '#059669' if raw_pct >= 100 else '#dc2626'})
    if view['variant'] == 'mini_gauge':
        view['status_text'] = str(p.get('gauge_status_text') or '')
    return view


# Record Header tone pill fallback (record_header_formatter.TONE_COLORS['neutral'])
_NEUTRAL_PILL = ('#6b7280', '#f3f4f6')


def _pill(status):
    """``{text, color, background}`` → validated pill view, or None."""
    if not isinstance(status, dict) or not str(status.get('text') or ''):
        return None
    return {'text': str(status.get('text')),
            'color': safe_color(status.get('color'), _NEUTRAL_PILL[0]),
            'background': safe_color(status.get('background'), _NEUTRAL_PILL[1])}


def panel_columns(width_px, n_stats):
    """Grid columns of a ``stats_style = 'panel'`` header at this printed
    width, and whether the panel sits BESIDE the identity — the container
    query steps of ``.pv-record-header-stats--panel`` in posterra.css
    (≥ 1200 beside, one per tile; ≥ 1050 beside, 2 × 2; ≥ 640 a band of 4;
    ≥ 400 a band of 2; else one column)."""
    if width_px >= 1200:
        return max(1, n_stats), True
    if width_px >= 1050:
        return 2, True
    if width_px >= 640:
        return 4, False
    if width_px >= 400:
        return 2, False
    return 1, False


def _header_view(block, icons=None, width_px=0):
    """Print view of a Record Header payload. Every opt-in scorecard extra
    (``title_status``, ``subtitle_items``, ``badges``, tile ``icon`` /
    ``caption`` / ``status``, ``stats_style``, ``empty_text``) is printed only
    when the payload carries it; without them the view renders exactly the
    pre-extras markup."""
    icons = icons or IconSet()
    p = block.get('payload') or {}
    if p.get('empty'):
        view = {'empty': True}
        if str(p.get('empty_text') or '').strip():
            view['empty_text'] = str(p.get('empty_text')).strip()
        return view
    avatar = p.get('avatar') or {}
    panel = p.get('stats_style') == 'panel'
    raw_stats = [s for s in (p.get('stats') or []) if isinstance(s, dict)]
    cols, beside = panel_columns(width_px, len(raw_stats)) if panel else (0, False)
    stats = []
    for i, s in enumerate(raw_stats):
        trend = s.get('trend') or {}
        t_arrow = {'up': '▲', 'down': '▼'}.get(trend.get('dir'), '–' if trend else '')
        t_color = {'good': '#059669', 'bad': '#dc2626'}.get(trend.get('status'), '#6b7280')
        stat = {
            'label': str(s.get('label') or ''), 'value': str(s.get('value') or ''),
            'bg': safe_color(s.get('bg'), '#f5f7fa'),
            'label_color': safe_color(s.get('label_color'), '#52606d'),
            'value_color': safe_color(s.get('value_color'), '#1f2933'),
            'trend_arrow': t_arrow, 'trend_color': t_color,
            'trend_delta': str(trend.get('delta') or '') if trend else '',
        }
        glyph = icons(s.get('icon'))
        if glyph:
            stat['icon'] = glyph
            stat['icon_color'] = safe_color(s.get('icon_color'))
        if str(s.get('caption') or ''):
            stat['caption'] = str(s.get('caption'))
        pill = _pill(s.get('status'))
        if pill:
            stat['status'] = pill
        if panel:
            # transparent unless the tile sets its own background (screen rule)
            stat['bg'] = safe_color(s.get('bg'))
            stat['cls'] = ' '.join(c for c in (
                'first-col' if i % cols == 0 else '',
                'next-row' if i >= cols else '') if c)
        stats.append(stat)
    view = {
        'empty': False,
        'layout': p.get('layout') or 'classic',
        'title': str(p.get('title') or ''),
        'subtitle': str(p.get('subtitle') or ''),
        'avatar_text': str(avatar.get('text') or '') if avatar.get('mode', 'initials') != 'none' else '',
        'avatar_color': safe_color(avatar.get('color'), '#087ad8'),
        'avatar_round': (avatar.get('shape') or 'circle') == 'circle',
        'fields': [{'label': str(f.get('label') or ''), 'value': str(f.get('value') or '')}
                   for f in (p.get('fields') or []) if isinstance(f, dict)],
        'stats': stats,
        'chips': [str(c) for c in (p.get('chips') or [])],
        'chips_label': str(p.get('chips_label') or ''),
        'chip_bg': safe_color(p.get('chip_color'), '#e6f4ef'),
        'chip_fg': safe_color(p.get('chip_text_color'), '#0b6e4f'),
    }
    status = _pill(p.get('title_status'))
    if status:
        view['title_status'] = status
    items = [{'icon': icons(it.get('icon')), 'value': str(it.get('value') or '')}
             for it in (p.get('subtitle_items') or []) if isinstance(it, dict) and it.get('value')]
    if items:            # screen: subtitle items replace the plain subtitle
        view['subtitle_items'] = items
    badges = [{'label': str(b.get('label') or ''), 'value': str(b.get('value') or '')}
              for b in (p.get('badges') or []) if isinstance(b, dict) and b.get('value')]
    if badges:
        view['badges'] = badges
    if panel:
        view['panel'] = {'cols': cols, 'beside': beside}
    return view


# ── Attribute Grid / Metric List (shared grid-utils components) ──────────
_AG_ICON = ('#087ad8', '#e7f1fb')          # .pvag-icon default colours


def _attribute_grid_view(block, icons, width_px):
    """Print view of an ``attribute_grid`` payload: the shared placement
    resolves each field's column against the printed card width (the same
    function and responsive steps as the screen); items stay in SQL order."""
    p = block.get('payload') or {}
    if p.get('empty'):
        return {'empty': True, 'empty_text': str(p.get('empty_text') or '')}
    cols = effective_columns(width_px, p.get('columns') or 1)
    items = []
    for it in resolve_placement([i for i in (p.get('items') or []) if isinstance(i, dict)], cols):
        style = it.get('style') if isinstance(it.get('style'), dict) else {}
        glyph = icons((it.get('icon') or {}).get('fa_class')) if isinstance(it.get('icon'), dict) else ''
        items.append({
            'label': str(it.get('label') or ''),
            'value': str(it.get('value') if it.get('value') is not None else ''),
            'strong': it.get('emphasis') == 'strong',
            'null': bool(it.get('is_null')),
            'secondary': str(it.get('secondary_value') or ''),
            'inline': it.get('layout') == 'inline',
            'divider': bool(it.get('divider_before')),
            'icon': glyph,
            'icon_fg': safe_color(style.get('foreground'), _AG_ICON[0]) if glyph else '',
            'icon_bg': safe_color(style.get('background'), _AG_ICON[1]) if glyph else '',
            'grid_column': f"{it['resolved']['col']} / span {it['resolved']['span']}",
        })
    leading = None
    lv = p.get('leading_visual')
    if isinstance(lv, dict):
        text = icons((lv.get('icon') or {}).get('fa_class')) if lv.get('mode') == 'icon' \
            and isinstance(lv.get('icon'), dict) else str(lv.get('text') or '')
        if text:
            leading = {'text': text, 'is_icon': lv.get('mode') == 'icon',
                       'fg': safe_color(lv.get('foreground'), '#ffffff'),
                       'bg': safe_color(lv.get('background'), '#087ad8')}
    return {'empty': False, 'cols': cols, 'compact': p.get('density') == 'compact',
            'items': items, 'leading': leading}


def _metric_list_view(block, icons):
    """Print view of a ``metric_list`` payload (``MetricList.jsx``): label,
    status pill, value in the status colour, CSS bar, detail, per-metric
    thresholds and the legend."""
    p = block.get('payload') or {}
    if p.get('empty'):
        return {'empty': True, 'empty_text': str(p.get('empty_text') or '')}
    progress = p.get('progress') if isinstance(p.get('progress'), dict) else {}
    show_bar = bool(progress.get('show', True)) if progress else True
    try:
        bar_h = int(progress.get('height') or 10)
    except (TypeError, ValueError):
        bar_h = 10
    bar_h = max(3, min(12, round(bar_h * 0.7)))         # print scale (~0.7 of the screen)
    track = safe_color(progress.get('track_color'), '#eef2f7')
    neutral = p.get('neutral') if isinstance(p.get('neutral'), dict) else {}
    legend = p.get('legend') if isinstance(p.get('legend'), dict) else {}
    mode = legend.get('mode') or 'hidden'
    items = []
    for it in p.get('items') or []:
        if not isinstance(it, dict):
            continue
        st = it.get('status') if isinstance(it.get('status'), dict) else None
        color = safe_color((st or {}).get('color')) or safe_color(neutral.get('color')) or '#6b7280'
        frac = it.get('progress_fraction')
        pct = None
        if show_bar and isinstance(frac, (int, float)) and not isinstance(frac, bool):
            pct = f'{max(0.0, min(100.0, float(frac) * 100)):.1f}'.rstrip('0').rstrip('.')
        thresholds = []
        if mode == 'per_metric':
            thresholds = [{'label': str(t.get('label') or ''), 'text': str(t.get('text') or ''),
                           'color': safe_color(t.get('color'), '#6b7280')}
                          for t in (it.get('thresholds') or []) if isinstance(t, dict)]
        items.append({
            'label': str(it.get('label') or ''),
            'icon': icons((it.get('icon') or {}).get('fa_class')) if isinstance(it.get('icon'), dict) else '',
            'value': str(it.get('formatted_value') or ''),
            'color': color,
            'badge': {'label': str(st.get('label')), 'color': color,
                      'background': safe_color(st.get('background'), '#f3f4f6')}
            if st and str(st.get('label') or '') else None,
            'pct': pct,
            'out_of_range': bool(it.get('out_of_range')),
            'detail': str(it.get('detail') or ''),
            'thresholds': thresholds,
        })
    entries = []
    if mode in ('numeric', 'semantic'):
        for e in legend.get('entries') or []:
            if isinstance(e, dict):
                text = str(e.get('text') or '') if mode == 'numeric' else ''
                entries.append({'label': str(e.get('label') or '') + (f' · {text}' if text else ''),
                                'color': safe_color(e.get('color'), '#6b7280')})
    return {'empty': False, 'items': items, 'legend': entries, 'bar_h': bar_h, 'track': track,
            'detail_label': str(p.get('detail_label') or '')}


def _hex_tint(color, alpha='1f'):
    """``#rrggbb`` → ``#rrggbbaa`` (the portal badge's 12 % tint); other
    colour forms get the light grey badge background."""
    c = (color or '').strip()
    if re.fullmatch(r'#[0-9a-fA-F]{6}', c):
        return c + alpha
    if re.fullmatch(r'#[0-9a-fA-F]{3}', c):
        return '#' + ''.join(ch * 2 for ch in c[1:]) + alpha
    return '#f3f4f6'


def _notes_view(notes):
    """Card subtitle / footnote / header badge with validated colours.
    Absent or blank → nothing printed."""
    n = notes if isinstance(notes, dict) else {}
    badge_color = safe_color(n.get('badge_color'))
    return {
        'subtitle': str(n.get('subtitle') or ''),
        'subtitle_color': safe_color(n.get('subtitle_color')),
        'footnote': str(n.get('footnote') or ''),
        'footnote_color': safe_color(n.get('footnote_color')),
        'badge': str(n.get('badge') or ''),
        'badge_color': badge_color,
        'badge_bg': _hex_tint(badge_color) if badge_color else '',
    }


def _names(items, limit=6):
    names = [str(i.get('name') or f"#{i.get('widget_id')}") for i in items]
    more = len(names) - limit
    return ', '.join(names[:limit]) + (f' and {more} more' if more > 0 else '')


def build_notices(notices):
    """``[{text, severity}]`` printed under the title (severity info|warn|bad)."""
    out = [{'severity': 'info',
            'text': 'This PDF includes record headers, KPI cards, tables, charts, attribute grids and '
                    'metric lists. Grid sorting '
                    'and column filters applied on screen are not reflected; tables use their '
                    'configured default order.'}]
    if notices.get('omitted'):
        n = len(notices['omitted'])
        out.append({'severity': 'info', 'text': f'{n} widget{"s" if n > 1 else ""} of a type the PDF '
                                                f'cannot print yet {"were" if n > 1 else "was"} not '
                                                f'included: {_names(notices["omitted"])}.'})
    if notices.get('skipped_engine'):
        n = len(notices['skipped_engine'])
        out.append({'severity': 'warn', 'text': f'{n} widget{"s" if n > 1 else ""} use a data source '
                                                f'that PDF export does not support yet and '
                                                f'{"were" if n > 1 else "was"} skipped: '
                                                f'{_names(notices["skipped_engine"])}.'})
    failed = notices.get('failed') or []
    late = notices.get('not_loaded') or []
    if failed or late:
        parts = []
        if failed:
            parts.append(f'{len(failed)} widget{"s" if len(failed) > 1 else ""} could not be loaded '
                         f'({_names(failed)})')
        if late:
            parts.append(f'{len(late)} widget{"s were" if len(late) > 1 else " was"} not loaded within '
                         f'the time limit ({_names(late)})')
        out.append({'severity': 'bad', 'text': 'Incomplete report: ' + '; '.join(parts) + '.'})
    if notices.get('sort_not_applied'):
        out.append({'severity': 'warn', 'text': 'The configured table sort could not be applied to: '
                                                f'{_names(notices["sort_not_applied"])}.'})
    return out


def build_view(env, *, page, tab, app, user, dataset, keynote, orientation, paper, generated_at):
    tab_name = tab.name if tab else ''
    filters = dataset.get('filters') or []
    values = {'app_name': app.name or '', 'page_name': page.name or '', 'tab_name': tab_name,
              'date': generated_at.strftime('%b %d, %Y')}
    for f in filters:
        values[f['param']] = f['value_label']
    title = resolve_template(page.pdf_title_template or DEFAULT_TITLE, values)
    content_px = content_width_px(paper, orientation)
    specs = []          # charts drawn by the render service's script
    icons = IconSet()   # Font Awesome glyphs; the font is embedded only when used
    blocks = []
    for b in dataset.get('blocks') or []:
        span = b.get('col_span') or '12'
        view = {'kind': b['kind'], 'name': b.get('name') or '', 'span': span if span in ('3', '4', '6', '8', '12') else '12',
                'break_before': bool(b.get('page_break_before')), 'status': b.get('status')}
        try:
            row_span = int(b.get('row_span') or 1)
        except (TypeError, ValueError):
            row_span = 1
        if row_span > 1:                     # portal grid: gridRow: span N
            view['row_span'] = row_span
        view['notes'] = _notes_view(b.get('notes'))
        inner_px = card_inner_width_px(content_px, view['span'])
        if b.get('status') == 'failed':
            view['kind'] = 'unavailable'
        elif b['kind'] == 'attribute_grid':
            view['grid'] = _attribute_grid_view(b, icons, inner_px)
        elif b['kind'] == 'metric_list':
            view['metrics'] = _metric_list_view(b, icons)
        elif b['kind'] == 'chart':
            spec = {'id': f'pvc{len(specs) + 1}', 'option': b['option'],
                    'width': card_inner_width_px(content_px, view['span']),
                    'height': max(CHART_MIN_H, min(CHART_MAX_H, int(b.get('height') or 350)))}
            specs.append(spec)
            view['chart'] = {'id': spec['id'], 'width': spec['width'], 'height': spec['height']}
            view['sub_kpis'] = b.get('sub_kpis') or []          # gauge_kpi only
            view['alert_text'] = b.get('alert_text') or ''
        elif b['kind'] == 'kpi':
            view['kpi'] = _kpi_view(b)
            if b.get('mini_option'):
                variant = view['kpi']['variant']
                if variant == 'mini_gauge':
                    # Portal "split" card: ring on the left (its centre shows
                    # the value), label / status / annotation on the right.
                    width = height = _mini_gauge_size(b.get('payload') or {})
                    view['kpi']['layout'] = 'split'
                else:
                    width, height = card_inner_width_px(content_px, view['span']), SPARKLINE_H
                spec = {'id': f'pvc{len(specs) + 1}', 'option': b['mini_option'],
                        'width': width, 'height': height}
                specs.append(spec)
                view['kpi']['mini'] = {'id': spec['id'], 'width': width, 'height': height}
        elif b['kind'] == 'record_header':
            view['header'] = _header_view(b, icons, inner_px)
        elif b['kind'] == 'table':
            caption = [f"{b['row_shown']:,} row{'s' if b['row_shown'] != 1 else ''}"]
            if b.get('more_available'):
                caption = [f"Showing first {b['row_shown']:,} rows; more rows are available"]
            if b.get('columns_total', 0) > b.get('columns_shown', 0):
                caption.append(f"first {b['columns_shown']} of {b['columns_total']} columns shown")
            view['table'] = {'columns': b['columns'], 'rows': b['rows'],
                             # pinned "Total row" rows (collector.split_total_rows) —
                             # printed bold after the body by the template
                             'total_rows': b.get('total_rows') or [],
                             'caption': '. '.join(caption) + '.',
                             'dense': b.get('columns_shown', 0) > 12}
        blocks.append(view)
    # Rows: consecutive cards share one 12-column grid; every table is its
    # own full-width row (Chromium paginates a long table reliably only
    # outside a grid item). A "new page before" flag starts a new row.
    rows = []
    for view in blocks:
        # "New page before" on the FIRST printed widget would leave page 1
        # holding only the title block — never honour it there.
        brk = bool(view['break_before']) and bool(rows)
        if view['kind'] == 'table':
            rows.append({'type': 'table', 'block': view, 'break_before': brk})
            continue
        if not rows or rows[-1]['type'] != 'grid' or brk:
            rows.append({'type': 'grid', 'blocks': [], 'break_before': brk})
        rows[-1]['blocks'].append(view)
    return {
        'title': title,
        'app_name': app.name or '',
        'logo': logo_data_uri(app) if page.pdf_show_logo else '',
        'generated': f"Generated {generated_at.strftime('%Y-%m-%d %H:%M')} UTC by {user.login or user.name}",
        'filters': filters if page.pdf_show_filters else [],
        'show_filters': bool(page.pdf_show_filters),
        'badges': [{'value': b['value'], 'color': safe_color(b.get('color'))}
                   for b in dataset.get('badges') or []],
        'notices': build_notices(dataset.get('notices') or {}),
        'keynote': keynote or '',
        'rows': rows,
        'chart_scripts': chart_scripts(specs),
        'chart_placeholder': CHART_PLACEHOLDER,
        'icon_css': font_face_css() if icons.used else '',
        'orientation': orientation,
        'paper': paper,
        'consistency': 'Data was freshly collected when this PDF was generated; it is not a '
                       'historical snapshot.',
    }


def render_html(env, view):
    html = env['ir.qweb']._render('posterra_portal.pdf_export_document', {'v': view})
    return '<!DOCTYPE html>\n' + str(html)


def footer_html(page, app):
    text = (page.pdf_footer_text or '').replace('{app_name}', app.name or '')
    return (
        '<!doctype html><html><head><meta charset="utf-8"><style>'
        '*{box-sizing:border-box}html,body{margin:0;padding:0;width:100%}'
        "body{font-family:'Noto Sans','Liberation Sans',Arial,sans-serif;font-size:7.5px;color:#7b8794;"
        '-webkit-print-color-adjust:exact}'
        '.f{display:flex;justify-content:space-between;width:100%;padding:0 0.4in}'
        '</style></head><body><div class="f"><span>' + str(escape(text)) + '</span>'
        '<span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>'
        '</div></body></html>')


def filename_for(page, tab, generated_at):
    base = '_'.join(x for x in (page.name, tab.name if tab else '') if x)
    slug = re.sub(r'[^A-Za-z0-9_-]+', '_', base).strip('_') or 'report'
    return f'{slug}_{generated_at:%Y%m%d}.pdf'


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
