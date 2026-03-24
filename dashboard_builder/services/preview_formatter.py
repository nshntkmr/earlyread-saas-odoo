# -*- coding: utf-8 -*-
"""
Preview Formatter — transforms raw SQL results into render-ready data
for the Designer's LivePreview component.

Supports: KPI, charts (bar/line/pie/donut/radar/scatter/heatmap/gauge), tables.
"""

import json
import logging

_logger = logging.getLogger(__name__)

# ── Color palettes ────────────────────────────────────────────────────────────
_PALETTES = {
    'healthcare': ['#0d9488', '#14b8a6', '#2dd4bf', '#6ee7b7', '#34d399', '#059669'],
    'ocean':      ['#1d4ed8', '#3b82f6', '#60a5fa', '#93c5fd', '#0ea5e9', '#38bdf8'],
    'warm':       ['#ea580c', '#f97316', '#fb923c', '#fbbf24', '#f59e0b', '#d97706'],
    'mono':       ['#374151', '#6b7280', '#9ca3af', '#d1d5db', '#e5e7eb', '#f3f4f6'],
    'default':    ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#fc8452'],
}

_STATUS_MAP = {
    'up':          ('fa-arrow-up',             'status-up'),
    'disciplined': ('fa-arrow-up',             'status-up'),
    'growing':     ('fa-arrow-up',             'status-up'),
    'down':        ('fa-arrow-down',           'status-down'),
    'retreated':   ('fa-arrow-down',           'status-down'),
    'warning':     ('fa-exclamation-triangle',  'status-warning'),
    'neutral':     ('fa-minus',                'status-neutral'),
    'stable':      ('fa-minus',                'status-neutral'),
}


def format_preview(chart_type, columns, rows, config=None, visual_config=None):
    """Dispatch to the right formatter based on chart_type.

    Args:
        chart_type:    str — widget chart type (bar, line, kpi, table, etc.)
        columns:       list of str — column names from SQL result
        rows:          list of list — row data from SQL result
        config:        dict — widget configuration (x_column, y_columns, etc.)
        visual_config: dict — chart-specific visual flags (orientation, stack, etc.)

    Returns:
        dict — merged into the preview API response
    """
    config = config or {}
    visual_config = visual_config or {}

    if chart_type in ('kpi', 'status_kpi', 'kpi_strip'):
        return _format_kpi_preview(chart_type, columns, rows, config)

    if chart_type == 'table':
        return {}  # tables already work with raw columns/rows

    if chart_type in ('bar', 'line', 'pie', 'donut', 'radar', 'scatter', 'heatmap', 'gauge'):
        return _build_echart_preview(chart_type, columns, rows, config, visual_config)

    # Fallback — return raw data as-is
    return {}


# ── KPI Formatting ────────────────────────────────────────────────────────────

def _format_value(raw, fmt='number', prefix='', suffix=''):
    """Format a raw numeric value for KPI display."""
    if raw is None:
        return '--'
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return str(raw)

    if fmt == 'currency':
        formatted = f'${val:,.0f}'
    elif fmt == 'percent':
        formatted = f'{val:.1f}%'
    elif fmt == 'decimal':
        formatted = f'{val:,.2f}'
    else:  # number
        formatted = f'{val:,.0f}'

    return f'{prefix}{formatted}{suffix}'


def _format_kpi_preview(chart_type, columns, rows, config):
    """Build KPI preview data from raw SQL results."""
    x_col = (config.get('x_column') or '').strip()
    col_idx = {c: i for i, c in enumerate(columns)}

    # Default to first column if x_column not set
    if not x_col and columns:
        x_col = columns[0]

    raw_val = rows[0][col_idx[x_col]] if (rows and x_col in col_idx) else None
    formatted = _format_value(
        raw_val,
        config.get('kpi_format', 'number'),
        config.get('kpi_prefix', ''),
        config.get('kpi_suffix', ''),
    )

    result = {
        'formatted_value': formatted,
        'label': config.get('title') or x_col or 'KPI',
    }

    # Secondary value from y_columns (first entry)
    y_cols_raw = (config.get('y_columns') or '').strip()
    if y_cols_raw:
        y_col = y_cols_raw.split(',')[0].strip()
        if y_col in col_idx and rows:
            sec_val = rows[0][col_idx[y_col]]
            result['secondary'] = f'{y_col}: {_format_value(sec_val, config.get("kpi_format", "number"))}'

    # Status KPI — icon/css
    _logger.info("PREVIEW DEBUG: chart_type=%r, has_rows=%s, y_cols_raw=%r",
                 chart_type, bool(rows), y_cols_raw)
    if chart_type == 'status_kpi' and rows:
        status_col = config.get('status_column', '')
        _logger.info("PREVIEW DEBUG: status_col=%r, y_cols_raw=%r, raw_val=%r",
                     status_col, y_cols_raw, raw_val)
        if status_col and status_col in col_idx:
            # Explicit status column with text values (up/down/warning/etc.)
            status_val = str(rows[0][col_idx[status_col]]).lower()
            icon_cls, css_mod = _STATUS_MAP.get(status_val, ('fa-circle', 'status-neutral'))
            result['icon_class'] = icon_cls
            result['status_css'] = css_mod
        elif y_cols_raw:
            # Auto-compute trend by comparing x_column (current) vs y_column (prior)
            y_col = y_cols_raw.split(',')[0].strip()
            if y_col in col_idx:
                try:
                    current = float(raw_val or 0)
                    prior = float(rows[0][col_idx[y_col]] or 0)
                    if current > prior:
                        result['icon_class'] = 'fa-arrow-up'
                        result['status_css'] = 'status-up'
                    elif current < prior:
                        result['icon_class'] = 'fa-arrow-down'
                        result['status_css'] = 'status-down'
                    else:
                        result['icon_class'] = 'fa-minus'
                        result['status_css'] = 'status-neutral'
                except (TypeError, ValueError):
                    _logger.exception("PREVIEW DEBUG: float conversion failed")

    _logger.info("PREVIEW DEBUG: final result keys=%s", list(result.keys()))
    return result


# ── ECharts Option Building ───────────────────────────────────────────────────

def _get_palette_colors(palette, custom_json=None):
    """Get color array for the given palette name."""
    if palette == 'custom' and custom_json:
        try:
            return json.loads(custom_json)
        except (json.JSONDecodeError, TypeError):
            pass
    return _PALETTES.get(palette, _PALETTES['default'])


def _build_echart_preview(chart_type, columns, rows, config, visual_config=None):
    """Build an ECharts option dict for chart preview."""
    vc = visual_config or {}
    x_col = (config.get('x_column') or '').strip()
    y_cols_raw = (config.get('y_columns') or '').strip()
    y_col_list = [c.strip() for c in y_cols_raw.split(',') if c.strip()]
    series_col = (config.get('series_column') or '').strip()

    col_idx = {c: i for i, c in enumerate(columns)}

    def col_val(row, name):
        idx = col_idx.get(name)
        return row[idx] if idx is not None else None

    # Default first cols if not configured
    if not x_col and columns:
        x_col = columns[0]
    if not y_col_list and len(columns) > 1:
        y_col_list = [columns[1]]

    colors = _get_palette_colors(
        config.get('color_palette', 'default'),
        config.get('color_custom_json'),
    )

    option = {
        'tooltip': {'trigger': 'axis'},
        'animation': True,
        'color': colors,
    }

    if chart_type in ('bar', 'line'):
        option['legend'] = {}
        option['yAxis'] = {'type': 'value'}

        if series_col and series_col in col_idx:
            # Series break: group rows by x category, then by series value
            # Ensures each series has one data point per unique x category
            categories = []
            seen_cats = set()
            series_map = {}  # {series_name: {category: value}}
            for r in rows:
                cat = str(col_val(r, x_col) or '')
                if cat not in seen_cats:
                    categories.append(cat)
                    seen_cats.add(cat)
                sv = str(col_val(r, series_col) or 'Other')
                yv = col_val(r, y_col_list[0]) if y_col_list else 0
                series_map.setdefault(sv, {})[cat] = yv or 0

            option['xAxis'] = {'type': 'category', 'data': categories}
            option['series'] = [
                {'name': sv, 'type': chart_type,
                 'data': [cat_vals.get(cat, 0) for cat in categories]}
                for sv, cat_vals in series_map.items()
            ]
        else:
            x_data = [str(col_val(r, x_col) or '') for r in rows]
            option['xAxis'] = {'type': 'category', 'data': x_data}
            option['series'] = [
                {'name': yc, 'type': chart_type, 'data': [col_val(r, yc) or 0 for r in rows]}
                for yc in y_col_list
            ]

    elif chart_type in ('pie', 'donut'):
        pie_data = [
            {'name': str(col_val(r, x_col) or ''),
             'value': col_val(r, y_col_list[0]) if y_col_list else 0}
            for r in rows
        ]
        radius = ['40%', '70%'] if chart_type == 'donut' else '70%'
        option['tooltip'] = {'trigger': 'item'}
        option['legend'] = {'orient': 'vertical', 'left': 'left'}
        option['series'] = [{'type': 'pie', 'radius': radius, 'data': pie_data,
                              'emphasis': {'itemStyle': {'shadowBlur': 10}}}]

    elif chart_type == 'gauge':
        gauge_min = float(config.get('gauge_min', 0))
        gauge_max = float(config.get('gauge_max', 100))
        raw_val = col_val(rows[0], x_col) if rows else 0
        try:
            val = float(raw_val or 0)
        except (TypeError, ValueError):
            val = 0
        option = {
            'animation': True,
            'color': colors,
            'series': [{
                'type': 'gauge',
                'min': gauge_min,
                'max': gauge_max,
                'data': [{'value': val, 'name': config.get('title', '')}],
                'title': {'show': False},
                'detail': {'formatter': '{value}'},
            }],
        }

    elif chart_type == 'radar':
        indicators = [{'name': str(col_val(r, x_col) or ''), 'max': 100}
                      for r in rows]
        series_list = []
        for yc in y_col_list:
            vals = [col_val(r, yc) or 0 for r in rows]
            series_list.append({'name': yc, 'type': 'radar',
                                'data': [{'value': vals, 'name': yc}]})
        option['tooltip'] = {}
        option['legend'] = {'data': y_col_list}
        option['radar'] = {'indicator': indicators}
        option['series'] = series_list

    elif chart_type == 'scatter':
        x_data = [col_val(r, x_col) or 0 for r in rows]
        y_data = [col_val(r, y_col_list[0]) or 0 for r in rows] if y_col_list else []
        option['xAxis'] = {'type': 'value'}
        option['yAxis'] = {'type': 'value'}
        option['series'] = [{'type': 'scatter',
                              'data': [[x, y] for x, y in zip(x_data, y_data)]}]

    elif chart_type == 'heatmap':
        x_vals = sorted({str(col_val(r, x_col) or '') for r in rows})
        y_vals = sorted({str(col_val(r, y_col_list[0]) or '') for r in rows}) if y_col_list else []
        z_col = y_col_list[1] if len(y_col_list) > 1 else (columns[2] if len(columns) > 2 else None)
        heat_data = []
        for r in rows:
            xi = x_vals.index(str(col_val(r, x_col) or ''))
            yi = y_vals.index(str(col_val(r, y_col_list[0]) or '')) if y_col_list else 0
            zv = col_val(r, z_col) if z_col else 0
            heat_data.append([xi, yi, zv or 0])
        option['xAxis'] = {'type': 'category', 'data': x_vals}
        option['yAxis'] = {'type': 'category', 'data': y_vals}
        option['visualMap'] = {
            'min': min((d[2] for d in heat_data), default=0),
            'max': max((d[2] for d in heat_data), default=1),
            'calculable': True,
            'orient': 'horizontal', 'left': 'center', 'bottom': '5%',
            'inRange': {'color': (colors[:2] if len(colors) >= 2
                                  else ['#e0f2f1', '#0d9488'])},
        }
        option['series'] = [{'type': 'heatmap', 'data': heat_data,
                              'label': {'show': True}}]

    # ── Apply visual flags (chart-library-agnostic → ECharts translation) ──
    if chart_type == 'bar' and vc:
        # Orientation: swap axes for horizontal bars
        if vc.get('orientation') == 'horizontal':
            option['xAxis'], option['yAxis'] = option.get('yAxis', {}), option.get('xAxis', {})

        # Stack: stack series on top of each other
        if vc.get('stack'):
            for s in option.get('series', []):
                s['stack'] = 'total'
            # Percent stack mode
            if vc.get('stack_mode') == 'percent':
                option['yAxis'] = option.get('yAxis') or {}
                if isinstance(option['yAxis'], dict):
                    option['yAxis']['max'] = 100

        # Show value labels on bars
        if vc.get('show_labels'):
            pos = 'inside' if vc.get('stack') else 'top'
            for s in option.get('series', []):
                s['label'] = {'show': True, 'position': pos}

        # Hide axis labels
        if vc.get('show_axis_labels') is False:
            for axis_key in ('xAxis', 'yAxis'):
                ax = option.get(axis_key)
                if isinstance(ax, dict):
                    ax['axisLabel'] = {'show': False}

    elif chart_type == 'line' and vc:
        # Area fill
        if vc.get('show_area'):
            opacity = vc.get('area_opacity', 0.3)
            for s in option.get('series', []):
                s['areaStyle'] = {'opacity': opacity}

        # Smooth curves
        if vc.get('smooth'):
            for s in option.get('series', []):
                s['smooth'] = True

        # Stack
        if vc.get('stack'):
            for s in option.get('series', []):
                s['stack'] = 'total'

    return {'echart_option': option}
