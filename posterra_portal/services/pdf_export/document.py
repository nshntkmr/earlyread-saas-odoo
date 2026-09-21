# -*- coding: utf-8 -*-
"""Dataset → print HTML (QWeb) + Gotenberg footer HTML.

The template (``posterra_portal.pdf_export_document``) only lays out a
sanitised view model built here: every admin colour goes through
``safe_color``, values are plain strings (QWeb escapes them) and table cells
are pre-escaped ``Markup`` from ``cell_format``. Nothing is fetched at render
time — the logo is an inline data URI and JavaScript is disabled in the
renderer.
"""

import base64
import datetime
import re

from markupsafe import Markup, escape

from .cell_format import safe_color

_PLACEHOLDER_RE = re.compile(r'\{([A-Za-z0-9_]+)\}')
DEFAULT_TITLE = '{app_name} — {page_name} — {tab_name}'


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
            pct = max(0.0, min(100.0, float(p.get('progress_pct'))))
        except (TypeError, ValueError):
            pct = 0.0
        view.update({'progress_pct': f'{pct:.1f}'.rstrip('0').rstrip('.'),
                     'progress_color': safe_color(p.get('bar_color'), '#0d9488'),
                     'progress_note': str(p.get('progress_annotation') or '')})
    return view


def _header_view(block):
    p = block.get('payload') or {}
    if p.get('empty'):
        return {'empty': True}
    avatar = p.get('avatar') or {}
    stats = []
    for s in p.get('stats') or []:
        trend = s.get('trend') or {}
        t_arrow = {'up': '▲', 'down': '▼'}.get(trend.get('dir'), '–' if trend else '')
        t_color = {'good': '#059669', 'bad': '#dc2626'}.get(trend.get('status'), '#6b7280')
        stats.append({
            'label': str(s.get('label') or ''), 'value': str(s.get('value') or ''),
            'bg': safe_color(s.get('bg'), '#f5f7fa'),
            'label_color': safe_color(s.get('label_color'), '#52606d'),
            'value_color': safe_color(s.get('value_color'), '#1f2933'),
            'trend_arrow': t_arrow, 'trend_color': t_color,
            'trend_delta': str(trend.get('delta') or '') if trend else '',
        })
    return {
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


def _names(items, limit=6):
    names = [str(i.get('name') or f"#{i.get('widget_id')}") for i in items]
    more = len(names) - limit
    return ', '.join(names[:limit]) + (f' and {more} more' if more > 0 else '')


def build_notices(notices):
    """``[{text, severity}]`` printed under the title (severity info|warn|bad)."""
    out = [{'severity': 'info',
            'text': 'This PDF includes record headers, KPI cards and tables. Grid sorting and '
                    'column filters applied on screen are not reflected; tables use their '
                    'configured default order.'}]
    if notices.get('omitted'):
        n = len(notices['omitted'])
        out.append({'severity': 'info', 'text': f'{n} chart widget{"s were" if n > 1 else " was"} '
                                                f'not included: {_names(notices["omitted"])}.'})
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
    blocks = []
    for b in dataset.get('blocks') or []:
        span = b.get('col_span') or '12'
        view = {'kind': b['kind'], 'name': b.get('name') or '', 'span': span if span in ('3', '4', '6', '8', '12') else '12',
                'break_before': bool(b.get('page_break_before')), 'status': b.get('status')}
        if b.get('status') == 'failed':
            view['kind'] = 'unavailable'
        elif b['kind'] == 'kpi':
            view['kpi'] = _kpi_view(b)
        elif b['kind'] == 'record_header':
            view['header'] = _header_view(b)
        elif b['kind'] == 'table':
            caption = [f"{b['row_shown']:,} row{'s' if b['row_shown'] != 1 else ''}"]
            if b.get('more_available'):
                caption = [f"Showing first {b['row_shown']:,} rows; more rows are available"]
            if b.get('columns_total', 0) > b.get('columns_shown', 0):
                caption.append(f"first {b['columns_shown']} of {b['columns_total']} columns shown")
            view['table'] = {'columns': b['columns'], 'rows': b['rows'],
                             'caption': '. '.join(caption) + '.',
                             'dense': b.get('columns_shown', 0) > 12}
        blocks.append(view)
    # Rows: consecutive cards share one 12-column grid; every table is its
    # own full-width row (Chromium paginates a long table reliably only
    # outside a grid item). A "new page before" flag starts a new row.
    rows = []
    for view in blocks:
        if view['kind'] == 'table':
            rows.append({'type': 'table', 'block': view, 'break_before': view['break_before']})
            continue
        if not rows or rows[-1]['type'] != 'grid' or view['break_before']:
            rows.append({'type': 'grid', 'blocks': [], 'break_before': view['break_before']})
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
