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
        # ── Helper: ensure percentage suffix ─────────────────────
        def _ensure_pct(val, default):
            if not val:
                return default
            val = str(val).strip()
            if val.replace('.', '', 1).isdigit():
                val += '%'
            return val

        # ── Read visual_config flags (backward-compatible) ─────────
        donut_style    = vc.get('donut_style', 'standard') if chart_type == 'donut' else 'pie'
        show_labels    = vc.get('show_labels', True)
        label_position = vc.get('label_position', 'outside')
        show_percent   = vc.get('show_percent', False)
        label_format   = vc.get('label_format', '')
        legend_pos     = vc.get('legend_position', 'left')
        sort_mode      = vc.get('sort', 'none')
        vc_limit       = int(vc.get('limit', 0) or 0)
        inner_radius   = _ensure_pct(vc.get('inner_radius', ''), '40%') if chart_type == 'donut' else '0%'
        outer_radius   = _ensure_pct(vc.get('outer_radius', ''), '70%')
        rose_type_val  = vc.get('rose_type', 'area')
        center_text    = vc.get('center_text', '')
        center_mode    = vc.get('center_mode', 'none')
        center_static  = vc.get('center_static_text', '')

        # ── Build pie data ─────────────────────────────────────────
        pie_data = [
            {'name': str(col_val(r, x_col) or ''),
             'value': col_val(r, y_col_list[0]) if y_col_list else 0}
            for r in rows
        ]

        # ── Sort ───────────────────────────────────────────────────
        if sort_mode == 'value_desc':
            pie_data.sort(key=lambda d: (d['value'] or 0), reverse=True)
        elif sort_mode == 'value_asc':
            pie_data.sort(key=lambda d: (d['value'] or 0))

        # ── Limit (group remainder as "Other") ─────────────────────
        if vc_limit > 0 and len(pie_data) > vc_limit:
            shown = pie_data[:vc_limit]
            rest_val = sum((d['value'] or 0) for d in pie_data[vc_limit:])
            if rest_val:
                shown.append({'name': 'Other', 'value': rest_val})
            pie_data = shown

        # ── Helper: build label config ─────────────────────────────
        _LABEL_FMTS = {
            'name':               '{b}',
            'name_value':         '{b}: {c}',
            'name_percent':       '{b} ({d}%)',
            'name_value_percent': '{b}: {c} ({d}%)',
        }

        def _pie_label_cfg():
            if not show_labels:
                return {'show': False}
            cfg = {'show': True, 'position': label_position}
            fmt = label_format or ('name_percent' if show_percent else 'name')
            if fmt in _LABEL_FMTS:
                cfg['formatter'] = _LABEL_FMTS[fmt]
            return cfg

        # ── Helper: build legend config ────────────────────────────
        def _pie_legend_cfg():
            if legend_pos == 'none':
                return {'show': False}
            orient = 'vertical' if legend_pos in ('left', 'right') else 'horizontal'
            return {'orient': orient, legend_pos: legend_pos}

        # ── Tooltip (always shows value; percent if label_format includes it) ──
        _eff_fmt = label_format or ('name_percent' if show_percent else 'name')
        tooltip_fmt = '{b}: {c} ({d}%)' if 'percent' in _eff_fmt else '{b}: {c}'
        option['tooltip'] = {'trigger': 'item', 'formatter': tooltip_fmt}

        # ── Build series based on donut_style ──────────────────────

        if donut_style == 'pie':
            # pie_standard — solid circle, no hole
            option['series'] = [{
                'type': 'pie',
                'radius': outer_radius,
                'data': pie_data,
                'label': _pie_label_cfg(),
                'labelLine': {'show': show_labels and label_position == 'outside'},
                'emphasis': {'focus': 'self', 'blurScope': 'series',
                             'itemStyle': {'shadowBlur': 10}},
            }]

        elif donut_style == 'standard':
            # donut_standard — basic ring
            series_cfg = {
                'type': 'pie',
                'radius': [inner_radius, outer_radius],
                'data': pie_data,
                'label': _pie_label_cfg(),
                'labelLine': {'show': show_labels and label_position == 'outside'},
                'emphasis': {'focus': 'self', 'blurScope': 'series',
                             'itemStyle': {'shadowBlur': 10}},
            }
            option['series'] = [series_cfg]

        elif donut_style == 'label_center':
            # donut_label_center — hover shows name+value in center hole
            # Respects show_labels: when True, slice labels appear alongside center emphasis
            series_cfg = {
                'type': 'pie',
                'radius': [inner_radius, outer_radius],
                'avoidLabelOverlap': False,
                'data': pie_data,
                'label': _pie_label_cfg(),
                'labelLine': {'show': show_labels and label_position == 'outside'},
                'emphasis': {
                    'label': {
                        'show': True,
                        'fontSize': 18,
                        'fontWeight': 'bold',
                        'position': 'center',
                    },
                    'focus': 'self',
                    'blurScope': 'series',
                    'itemStyle': {'shadowBlur': 10},
                },
            }
            option['series'] = [series_cfg]

        elif donut_style == 'rounded':
            # donut_rounded — rounded corners with white gaps
            series_cfg = {
                'type': 'pie',
                'radius': [inner_radius, outer_radius],
                'data': pie_data,
                'label': _pie_label_cfg(),
                'labelLine': {'show': show_labels and label_position == 'outside'},
                'itemStyle': {
                    'borderRadius': 10,
                    'borderColor': '#fff',
                    'borderWidth': 2,
                },
                'emphasis': {'focus': 'self', 'blurScope': 'series',
                             'itemStyle': {'shadowBlur': 10}},
            }
            option['series'] = [series_cfg]

        elif donut_style == 'semi':
            # donut_semi — half donut (180°)
            # endAngle:360 with startAngle:180 restricts to top semicircle.
            # No filler item needed — ECharts fills the 180° arc with real data.
            label_cfg = _pie_label_cfg()
            if show_labels and label_position == 'outside':
                label_cfg['position'] = 'inside'
            series_cfg = {
                'type': 'pie',
                'radius': ['50%', '70%'],
                'center': ['50%', '70%'],
                'startAngle': 180,
                'endAngle': 360,
                'data': pie_data,
                'label': label_cfg,
                'labelLine': {'show': False},
                'emphasis': {'focus': 'self', 'blurScope': 'series',
                             'itemStyle': {'shadowBlur': 10}},
            }
            option['series'] = [series_cfg]

        elif donut_style == 'rose':
            # donut_rose — nightingale / rose chart
            series_cfg = {
                'type': 'pie',
                'radius': [inner_radius, outer_radius],
                'roseType': rose_type_val,
                'data': pie_data,
                'label': _pie_label_cfg(),
                'labelLine': {'show': show_labels and label_position == 'outside'},
                'emphasis': {'focus': 'self', 'blurScope': 'series',
                             'itemStyle': {'shadowBlur': 10}},
            }
            option['series'] = [series_cfg]

        elif donut_style == 'nested' and series_col:
            # donut_nested — 2 concentric rings (parent=x_col, child=series_column)
            from collections import OrderedDict
            parent_totals = OrderedDict()
            child_items = []
            for r in rows:
                parent = str(col_val(r, x_col) or '')
                child = str(col_val(r, series_col) or '')
                value = col_val(r, y_col_list[0]) if y_col_list else 0
                parent_totals[parent] = parent_totals.get(parent, 0) + (value or 0)
                child_items.append({
                    'name': f'{parent} \u2192 {child}' if child else parent,
                    'value': value,
                })

            inner_data = [{'name': k, 'value': v} for k, v in parent_totals.items()]

            # Apply sort/limit to inner ring
            if sort_mode == 'value_desc':
                inner_data.sort(key=lambda d: (d['value'] or 0), reverse=True)
            elif sort_mode == 'value_asc':
                inner_data.sort(key=lambda d: (d['value'] or 0))

            # Read per-ring config (defaults match previous hardcoded values)
            ni_start = _ensure_pct(vc.get('nested_inner_radius_start', ''), '0%')
            ni_end   = _ensure_pct(vc.get('nested_inner_radius_end', ''), '30%')
            ni_lpos  = vc.get('nested_inner_label_pos', 'inner')
            ni_lfmt  = vc.get('nested_inner_label_format', 'name')

            no_start = _ensure_pct(vc.get('nested_outer_radius_start', ''), '40%')
            no_end   = _ensure_pct(vc.get('nested_outer_radius_end', ''), '65%')
            no_lpos  = vc.get('nested_outer_label_pos', 'outside')
            no_lfmt  = vc.get('nested_outer_label_format', 'name')

            inner_series = {
                'type': 'pie',
                'radius': [ni_start, ni_end],
                'data': inner_data,
                'label': {
                    'show': show_labels,
                    'position': ni_lpos,
                    'fontSize': 11 if ni_lpos == 'inner' else 12,
                    'formatter': _LABEL_FMTS.get(ni_lfmt, '{b}'),
                },
                'labelLine': {'show': show_labels and ni_lpos == 'outside'},
                'emphasis': {'focus': 'self', 'blurScope': 'series',
                             'itemStyle': {'shadowBlur': 10}},
            }
            outer_series = {
                'type': 'pie',
                'radius': [no_start, no_end],
                'data': child_items,
                'label': {
                    'show': show_labels,
                    'position': no_lpos,
                    'formatter': _LABEL_FMTS.get(no_lfmt, '{b}'),
                },
                'labelLine': {'show': show_labels and no_lpos == 'outside'},
                'emphasis': {'focus': 'self', 'blurScope': 'series',
                             'itemStyle': {'shadowBlur': 10}},
            }
            option['series'] = [inner_series, outer_series]

        elif donut_style == 'multi_ring' and series_col:
            # donut_multi_ring — side-by-side rings grouped by series_column
            from collections import OrderedDict
            groups = OrderedDict()
            for r in rows:
                grp = str(col_val(r, series_col) or '')
                label = str(col_val(r, x_col) or '')
                value = col_val(r, y_col_list[0]) if y_col_list else 0
                groups.setdefault(grp, []).append({'name': label, 'value': value})

            group_keys = list(groups.keys())
            n = len(group_keys) or 1
            series_list = []
            for i, grp in enumerate(group_keys):
                center_x = f'{int((100 / (n + 1)) * (i + 1))}%'
                ring_data = groups[grp]
                # Apply sort/limit per ring
                if sort_mode == 'value_desc':
                    ring_data.sort(key=lambda d: (d['value'] or 0), reverse=True)
                elif sort_mode == 'value_asc':
                    ring_data.sort(key=lambda d: (d['value'] or 0))
                if vc_limit > 0 and len(ring_data) > vc_limit:
                    shown_r = ring_data[:vc_limit]
                    rest_r = sum((d['value'] or 0) for d in ring_data[vc_limit:])
                    if rest_r:
                        shown_r.append({'name': 'Other', 'value': rest_r})
                    ring_data = shown_r

                series_list.append({
                    'type': 'pie',
                    'radius': [inner_radius, outer_radius],
                    'center': [center_x, '50%'],
                    'data': ring_data,
                    'name': str(grp),
                    'label': _pie_label_cfg(),
                    'labelLine': {'show': show_labels and label_position == 'outside'},
                    'emphasis': {'focus': 'self', 'blurScope': 'series',
                                 'itemStyle': {'shadowBlur': 10}},
                })
            option['series'] = series_list

            # Add ring title (group name) centered inside each ring
            for i, grp in enumerate(group_keys):
                center_x = f'{int((100 / (n + 1)) * (i + 1))}%'
                option.setdefault('graphic', []).append({
                    'type': 'text',
                    'left': center_x,
                    'top': '50%',
                    'style': {
                        'text': str(grp),
                        'fontSize': 14,
                        'fontWeight': 'bold',
                        'fill': '#333',
                        'textAlign': 'center',
                        'textVerticalAlign': 'middle',
                    },
                })

        else:
            # Fallback for nested/multi_ring without series_column, or unknown style
            # Render as standard donut
            radius = [inner_radius, outer_radius] if chart_type == 'donut' else outer_radius
            option['series'] = [{
                'type': 'pie',
                'radius': radius,
                'data': pie_data,
                'label': _pie_label_cfg(),
                'labelLine': {'show': show_labels and label_position == 'outside'},
                'emphasis': {'focus': 'self', 'blurScope': 'series',
                             'itemStyle': {'shadowBlur': 10}},
            }]

        # ── Legend ─────────────────────────────────────────────────
        option['legend'] = _pie_legend_cfg()

        # ── Center display (graphic element) ─────────────────────────
        _center_styles = ('standard', 'label_center', 'rounded', 'rose')
        if center_mode == 'auto_total' and donut_style in _center_styles:
            total_val = sum((d.get('value') or 0) for d in pie_data)
            total_str = f'{total_val:,.0f}' if isinstance(total_val, (int, float)) else str(total_val)
            option.setdefault('graphic', []).append({
                'type': 'text',
                'left': 'center',
                'top': 'center',
                'style': {
                    'textAlign': 'center',
                    'textVerticalAlign': 'middle',
                    'rich': {
                        'label': {'fontSize': 12, 'fill': '#999', 'padding': [0, 0, 4, 0]},
                        'total': {'fontSize': 20, 'fontWeight': 'bold', 'fill': '#333'},
                    },
                    'text': ('{label|' + center_text + '}\n{total|' + total_str + '}') if center_text else ('{total|' + total_str + '}'),
                },
            })
        elif center_mode == 'static' and center_static and donut_style in _center_styles:
            option.setdefault('graphic', []).append({
                'type': 'text',
                'left': 'center',
                'top': 'center',
                'style': {
                    'text': center_static,
                    'fontSize': 16,
                    'fontWeight': 'bold',
                    'fill': '#333',
                    'textAlign': 'center',
                    'textVerticalAlign': 'middle',
                },
            })
        elif center_mode == 'none' and center_text and donut_style in _center_styles:
            # Backward compat: old widgets with center_text but no center_mode
            option.setdefault('graphic', []).append({
                'type': 'text',
                'left': 'center',
                'top': 'center',
                'style': {
                    'text': center_text,
                    'fontSize': 16,
                    'fontWeight': 'bold',
                    'fill': '#333',
                    'textAlign': 'center',
                    'textVerticalAlign': 'middle',
                },
            })

    elif chart_type == 'gauge':
        vc = visual_config or {}
        gauge_style = vc.get('gauge_style', 'standard')

        gauge_min = float(vc.get('gauge_min', config.get('gauge_min', 0)))
        gauge_max = float(vc.get('gauge_max', config.get('gauge_max', 100)))
        raw_val = col_val(rows[0], x_col) if rows else 0
        try:
            val = float(raw_val or 0)
        except (TypeError, ValueError):
            val = 0

        color_mode = vc.get('gauge_color_mode', 'single')
        warn_frac = float(vc.get('gauge_warn_threshold', 50)) / 100.0
        good_frac = float(vc.get('gauge_good_threshold', 70)) / 100.0

        if color_mode == 'traffic_light':
            axis_color = [[warn_frac, '#ef4444'], [good_frac, '#f59e0b'], [1.0, '#10b981']]
            val_range = gauge_max - gauge_min
            vf = (val - gauge_min) / val_range if val_range else 0
            pt_color = '#ef4444' if vf < warn_frac else ('#f59e0b' if vf < good_frac else '#10b981')
        else:
            pt_color = colors[0] if colors else '#0d9488'
            axis_color = [[1.0, pt_color]]

        # Non-ECharts variants — return plain dict
        if gauge_style == 'bullet':
            b_min = float(vc.get('bullet_min', 0))
            b_max = float(vc.get('bullet_max', 100))
            # Parse ranges
            ranges_raw = vc.get('bullet_ranges', '')
            ranges = []
            if ranges_raw and ranges_raw.strip():
                try:
                    ranges = json.loads(ranges_raw)
                except (json.JSONDecodeError, TypeError):
                    pass
            if not ranges:
                third = (b_max - b_min) / 3
                ranges = [
                    {'to': b_min + third, 'color': '#ef4444', 'label': f'Poor <{round(b_min + third)}'},
                    {'to': b_min + 2*third, 'color': '#f59e0b', 'label': f'Watch'},
                    {'to': b_max, 'color': '#10b981', 'label': f'Good >{round(b_min + 2*third)}'},
                ]
            threshold_parts = [r.get('label', '') for r in ranges if r.get('label')]
            threshold_text = ' | '.join(threshold_parts) if vc.get('bullet_show_labels', True) else ''
            bar_height = int(vc.get('bullet_bar_height', 12))
            orientation = vc.get('bullet_orientation', 'horizontal')

            # Multi-row: when >1 row and y_col_list has actual_value column
            if len(rows) > 1 and y_col_list:
                items = []
                for r in rows:
                    name = str(col_val(r, x_col) or '')
                    try:
                        rv = float(col_val(r, y_col_list[0]) or 0)
                    except (TypeError, ValueError):
                        rv = 0
                    bm = None
                    bm_label = ''
                    if len(y_col_list) >= 2:
                        try:
                            bm = float(col_val(r, y_col_list[1]) or 0)
                        except (TypeError, ValueError):
                            pass
                    if len(y_col_list) >= 3:
                        bm_label = str(col_val(r, y_col_list[2]) or '')
                    fmt = f'{round(rv, 1)}%' if b_max == 100 else str(round(rv, 1))
                    items.append({
                        'label': name, 'value': round(rv, 1),
                        'formatted_value': fmt,
                        'target': round(bm, 1) if bm is not None else None,
                        'target_label': bm_label,
                    })
                return {
                    'gauge_variant': 'bullet', 'multi': True,
                    'items': items,
                    'min': b_min, 'max': b_max, 'ranges': ranges,
                    'bar_height': bar_height, 'orientation': orientation,
                    'threshold_text': threshold_text,
                }

            # Single-row
            target = vc.get('target_value')
            if target is None and y_col_list:
                t_val = col_val(rows[0], y_col_list[0]) if rows else None
                if t_val is not None:
                    try:
                        target = float(t_val)
                    except (TypeError, ValueError):
                        pass
            return {
                'gauge_variant': 'bullet',
                'value': round(val, 1),
                'formatted_value': f'{round(val, 1)}%' if gauge_max == 100 else str(round(val, 1)),
                'target': round(target, 1) if target is not None else None,
                'min': b_min, 'max': b_max,
                'ranges': ranges,
                'label': vc.get('gauge_label', ''),
                'orientation': orientation,
                'bar_height': bar_height,
                'threshold_text': threshold_text,
                'target_label': vc.get('target_label', ''),
            }

        elif gauge_style == 'traffic_light_rag':
            red_t = float(vc.get('rag_red_threshold', 70))
            green_t = float(vc.get('rag_green_threshold', 85))
            invert = vc.get('rag_invert', False)

            def _rag(v):
                if invert:
                    return 'green' if v <= red_t else ('amber' if v <= green_t else 'red')
                return 'green' if v >= green_t else ('amber' if v >= red_t else 'red')

            # Multi-row: x=metric_name, y=[value, rag_status, status_text]
            if len(rows) > 1 and y_col_list:
                items = []
                for r in rows:
                    nm = str(col_val(r, x_col) or '')
                    try:
                        rv = float(col_val(r, y_col_list[0]) or 0)
                    except (TypeError, ValueError):
                        rv = 0
                    rs = ''
                    if len(y_col_list) >= 2:
                        rs = str(col_val(r, y_col_list[1]) or '').lower().strip()
                    if rs not in ('green', 'amber', 'red'):
                        rs = _rag(rv)
                    st = ''
                    if len(y_col_list) >= 3:
                        st = str(col_val(r, y_col_list[2]) or '')
                    fmt = f'{round(rv, 1)}%' if gauge_max == 100 else str(round(rv, 1))
                    items.append({
                        'label': nm, 'value': round(rv, 1),
                        'formatted_value': fmt, 'rag_status': rs, 'status_text': st,
                    })
                return {
                    'gauge_variant': 'traffic_light_rag', 'multi': True,
                    'items': items,
                }

            # Single-row (backward compatible)
            badge_override = ''
            if rows and y_col_list:
                if len(y_col_list) >= 1:
                    try:
                        sr = float(col_val(rows[0], y_col_list[0]) or 0)
                        if sr: red_t = sr
                    except (TypeError, ValueError): pass
                if len(y_col_list) >= 2:
                    try:
                        sg = float(col_val(rows[0], y_col_list[1]) or 0)
                        if sg: green_t = sg
                    except (TypeError, ValueError): pass
                if len(y_col_list) >= 3:
                    badge_override = str(col_val(rows[0], y_col_list[2]) or '')
            rag_status = _rag(val)
            badge_map = {'green': vc.get('rag_badge_green', 'On target'),
                         'amber': vc.get('rag_badge_amber', 'Watch'),
                         'red': vc.get('rag_badge_red', 'At risk')}
            rt, gt = round(red_t, 1), round(green_t, 1)
            thr = (f'G: <{rt} | A: {rt}-{gt} | R: >{gt}' if invert
                   else f'G: \u2265{gt} | A: {rt}-{gt} | R: <{rt}')
            badge = badge_override if badge_override else (badge_map.get(rag_status, '') if vc.get('rag_show_badge', True) else '')
            return {
                'gauge_variant': 'traffic_light_rag',
                'value': round(val, 1),
                'formatted_value': f'{round(val, 1)}%' if gauge_max == 100 else str(round(val, 1)),
                'rag_status': rag_status,
                'badge_text': badge,
                'threshold_text': thr if vc.get('rag_show_thresholds', True) else '',
                'label': vc.get('gauge_label', ''),
            }

        elif gauge_style == 'percentile_rank':
            p = int(val)
            suffix = 'th'
            if p % 10 == 1 and p % 100 != 11: suffix = 'st'
            elif p % 10 == 2 and p % 100 != 12: suffix = 'nd'
            elif p % 10 == 3 and p % 100 != 13: suffix = 'rd'
            if p >= 75: q_label, q_color = 'Top quartile', '#16a34a'
            elif p >= 50: q_label, q_color = '2nd quartile', '#2563eb'
            elif p >= 25: q_label, q_color = '3rd quartile', '#d97706'
            else: q_label, q_color = '4th quartile', '#dc2626'
            subtitle = ''
            actual_value = ''
            actual_label = ''
            if y_col_list:
                if len(y_col_list) >= 1:
                    sv = col_val(rows[0], y_col_list[0]) if rows else ''
                    subtitle = str(sv or '')
                if len(y_col_list) >= 2:
                    av = col_val(rows[0], y_col_list[1]) if rows else ''
                    actual_value = str(av or '')
                if len(y_col_list) >= 3:
                    al = col_val(rows[0], y_col_list[2]) if rows else ''
                    actual_label = str(al or '')
            return {
                'gauge_variant': 'percentile_rank',
                'percentile': p,
                'ordinal_text': f'{p}{suffix}',
                'subtitle': subtitle or config.get('title', ''),
                'quartile_label': q_label if vc.get('percentile_show_badge', True) else '',
                'quartile_color': q_color,
                'actual_value': actual_value,
                'actual_label': actual_label,
                'show_quartile_markers': vc.get('percentile_show_quartiles', True),
                'label': vc.get('gauge_label', ''),
            }

        # ECharts gauge variants
        fmt = '{value}%' if (gauge_max == 100 and gauge_min == 0) else '{value}'
        show_needle = vc.get('show_needle', True)
        show_progress = vc.get('show_progress_bar', True)

        if gauge_style == 'half_arc':
            option = {
                'animation': True, 'color': colors,
                'series': [{
                    'type': 'gauge', 'startAngle': 180, 'endAngle': 0,
                    'min': gauge_min, 'max': gauge_max,
                    'radius': '90%', 'center': ['50%', '70%'],
                    'progress': {'show': show_progress, 'width': 18, 'itemStyle': {'color': pt_color}},
                    'axisLine': {'lineStyle': {'width': 18, 'color': axis_color}},
                    'axisTick': {'show': False}, 'splitLine': {'show': False},
                    'axisLabel': {'show': False},
                    'pointer': {'show': False}, 'anchor': {'show': False},
                    'title': {'show': False},
                    'detail': {'fontSize': 28, 'fontWeight': 'bold', 'formatter': fmt,
                               'color': pt_color, 'offsetCenter': [0, '-10%']},
                    'data': [{'value': round(val, 1)}],
                }],
            }
        elif gauge_style == 'three_quarter':
            option = {
                'animation': True, 'color': colors,
                'series': [{
                    'type': 'gauge', 'startAngle': 225, 'endAngle': -45,
                    'min': gauge_min, 'max': gauge_max, 'radius': '85%',
                    'progress': {'show': show_progress, 'width': 12},
                    'axisLine': {'lineStyle': {'width': 12, 'color': axis_color}},
                    'axisTick': {'show': True, 'splitNumber': 5},
                    'splitLine': {'length': 10, 'lineStyle': {'width': 2, 'color': '#aaa'}},
                    'axisLabel': {'distance': 18, 'color': '#666', 'fontSize': 11},
                    'pointer': {'show': show_needle, 'length': '60%', 'width': 5},
                    'anchor': {'show': show_needle, 'size': 14,
                               'itemStyle': {'borderWidth': 6, 'borderColor': pt_color, 'color': '#fff'}},
                    'title': {'show': False},
                    'detail': {'fontSize': 30, 'fontWeight': 'bold', 'formatter': fmt,
                               'color': pt_color, 'offsetCenter': [0, '70%']},
                    'data': [{'value': round(val, 1)}],
                }],
            }
        elif gauge_style == 'multi_ring':
            # Multi-ring needs multiple rows
            mr_colors = colors or ['#0d9488', '#f59e0b', '#ef4444', '#3b82f6', '#8b5cf6', '#ec4899']
            max_rings = int(vc.get('multi_ring_max_rings', 6))
            arc_width = int(vc.get('multi_ring_arc_width', 10))
            ring_data = []
            for r in rows[:max_rings]:
                nm = str(col_val(r, x_col) or '')
                try:
                    rv = float(col_val(r, y_col_list[0]) if y_col_list else 0)
                except (TypeError, ValueError):
                    rv = 0
                ring_data.append({'name': nm, 'value': round(rv, 1)})
            series_list = []
            outer = 90
            gap = arc_width + 4
            for i, rd in enumerate(ring_data):
                rp = outer - i * gap
                if rp < 15:
                    break
                rc = mr_colors[i % len(mr_colors)]
                series_list.append({
                    'type': 'gauge', 'startAngle': 225, 'endAngle': -45,
                    'min': 0, 'max': gauge_max, 'radius': f'{rp}%',
                    'progress': {'show': True, 'width': arc_width, 'itemStyle': {'color': rc}},
                    'axisLine': {'lineStyle': {'width': arc_width, 'color': [[1.0, '#f3f4f6']]}},
                    'axisTick': {'show': False}, 'splitLine': {'show': False},
                    'axisLabel': {'show': False},
                    'pointer': {'show': False}, 'anchor': {'show': False},
                    'title': {'show': False}, 'detail': {'show': False},
                    'data': [{'value': rd['value'], 'name': rd['name']}],
                })
            option = {'animation': True, 'color': mr_colors, 'series': series_list}
            # Center text
            if vc.get('multi_ring_show_center', True):
                ct = vc.get('multi_ring_center_text', '')
                if not ct and ring_data:
                    ct = str(round(sum(d['value'] for d in ring_data) / len(ring_data), 1))
                option['graphic'] = [{'type': 'text', 'left': 'center', 'top': '42%',
                    'style': {'text': ct, 'fontSize': 24, 'fontWeight': 'bold',
                              'fill': '#1f2937', 'textAlign': 'center'}}]
                cs = vc.get('multi_ring_center_subtitle', '')
                if cs:
                    option['graphic'].append({'type': 'text', 'left': 'center', 'top': '52%',
                        'style': {'text': cs, 'fontSize': 11, 'fill': '#6b7280', 'textAlign': 'center'}})
            # Legend via hidden pie
            if vc.get('multi_ring_show_legend', True) and ring_data:
                option['legend'] = {'show': True, 'bottom': 0, 'itemGap': 12,
                    'data': [rd['name'] for rd in ring_data], 'textStyle': {'fontSize': 11}}
                option['series'].append({'type': 'pie', 'radius': [0, 0], 'label': {'show': False},
                    'data': [{'name': rd['name'], 'value': rd['value'],
                              'itemStyle': {'color': mr_colors[i % len(mr_colors)]}}
                             for i, rd in enumerate(ring_data)]})
        else:
            # standard (default)
            option = {
                'animation': True, 'color': colors,
                'series': [{
                    'type': 'gauge', 'startAngle': 200, 'endAngle': -20,
                    'min': gauge_min, 'max': gauge_max, 'radius': '85%',
                    'progress': {'show': show_progress, 'width': 14},
                    'axisLine': {'lineStyle': {'width': 14, 'color': axis_color}},
                    'axisTick': {'show': False},
                    'splitLine': {'length': 8, 'lineStyle': {'width': 2, 'color': '#aaa'}},
                    'axisLabel': {'distance': 20, 'color': '#666', 'fontSize': 11},
                    'anchor': {'show': show_needle, 'size': 16,
                               'itemStyle': {'borderWidth': 8, 'borderColor': pt_color, 'color': '#fff'}},
                    'pointer': {'show': show_needle},
                    'title': {'show': False},
                    'detail': {'fontSize': 32, 'fontWeight': 'bold', 'formatter': fmt,
                               'color': pt_color, 'offsetCenter': [0, '60%']},
                    'itemStyle': {'color': pt_color},
                    'data': [{'value': round(val, 1)}],
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
        _apply_line_variant_flags(option, vc, colors, col_idx, col_val,
                                  rows, x_col, y_col_list, series_col)

    return {'echart_option': option}


# ── Line variant builder (preview) ──────────────────────────────────────────

def _apply_line_variant_flags(option, vc, colors, col_idx, col_val,
                              rows, x_col, y_col_list, series_col):
    """Apply line_style variant + universal flags to an ECharts option.

    Called after the base series have been built (same category/series
    extraction as bar). Mutates ``option`` in-place.
    """
    line_style = vc.get('line_style', 'basic')

    # ── Universal line appearance flags ──────────────────────────
    smooth      = vc.get('smooth', False)
    show_points = vc.get('show_points', True)
    point_size  = int(vc.get('point_size', 4) or 4)
    line_width  = int(vc.get('line_width', 2) or 2)
    step_type   = vc.get('step_type', 'none')
    show_labels = vc.get('show_labels', False)
    label_pos   = vc.get('label_position', 'top')
    legend_pos  = vc.get('legend_position', 'top')
    sort_mode   = vc.get('sort', 'none')
    vc_limit    = int(vc.get('limit', 0) or 0)

    # ── Variant-specific transforms ──────────────────────────────

    if line_style in ('basic', 'area', 'stacked_line', 'stacked_area'):
        # Stack
        if line_style in ('stacked_line', 'stacked_area'):
            for s in option.get('series', []):
                s['stack'] = 'total'
                s['emphasis'] = {'focus': 'series'}

        # Area fill
        if line_style in ('area', 'stacked_area'):
            area_opacity = float(vc.get('area_opacity', 0.3) or 0.3)
            use_gradient = vc.get('area_gradient', False)
            for idx, s in enumerate(option.get('series', [])):
                if use_gradient:
                    c = colors[idx % len(colors)] if colors else '#5470c6'
                    s['areaStyle'] = {
                        'opacity': area_opacity,
                        'color': {
                            'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                            'colorStops': [
                                {'offset': 0, 'color': c},
                                {'offset': 1, 'color': 'rgba(255,255,255,0)'},
                            ],
                        },
                    }
                else:
                    s['areaStyle'] = {'opacity': area_opacity}

        # Step function
        if step_type and step_type != 'none':
            for s in option.get('series', []):
                s['step'] = step_type

    elif line_style == 'waterfall':
        _build_waterfall_series(option, vc, colors, col_idx, col_val,
                                rows, x_col, y_col_list)

    elif line_style == 'combo':
        _build_combo_series(option, vc, colors, y_col_list)

    elif line_style == 'benchmark':
        _build_benchmark_series(option, vc, y_col_list)

    # ── Apply universal appearance to all line-type series ────────
    for s in option.get('series', []):
        if s.get('type') != 'line':
            continue
        if smooth:
            s['smooth'] = True
        s['symbol'] = 'circle' if show_points else 'none'
        s['symbolSize'] = point_size
        s.setdefault('lineStyle', {})['width'] = line_width

    # ── Value labels ─────────────────────────────────────────────
    if show_labels:
        for s in option.get('series', []):
            s['label'] = {'show': True, 'position': label_pos}

    # ── Legend position ──────────────────────────────────────────
    if legend_pos == 'none':
        option['legend'] = {'show': False}
    else:
        orient = 'vertical' if legend_pos in ('left', 'right') else 'horizontal'
        option['legend'] = {'orient': orient, legend_pos: legend_pos}

    # ── Sort categories ──────────────────────────────────────────
    if sort_mode != 'none' and option.get('xAxis', {}).get('data'):
        x_vals = option['xAxis']['data']
        all_series = option.get('series', [])
        if all_series:
            zipped = list(zip(x_vals, *[s['data'] for s in all_series
                                        if isinstance(s.get('data'), list)]))
            if sort_mode == 'value_desc':
                zipped.sort(key=lambda p: (p[1] or 0), reverse=True)
            elif sort_mode == 'value_asc':
                zipped.sort(key=lambda p: (p[1] or 0))
            elif sort_mode == 'alpha_asc':
                zipped.sort(key=lambda p: str(p[0]).lower())
            elif sort_mode == 'alpha_desc':
                zipped.sort(key=lambda p: str(p[0]).lower(), reverse=True)
            option['xAxis']['data'] = [p[0] for p in zipped]
            idx = 1
            for s in all_series:
                if isinstance(s.get('data'), list) and idx < len(zipped[0]):
                    s['data'] = [p[idx] for p in zipped]
                    idx += 1

    # ── Limit data points ────────────────────────────────────────
    if vc_limit and vc_limit > 0 and option.get('xAxis', {}).get('data'):
        option['xAxis']['data'] = option['xAxis']['data'][:vc_limit]
        for s in option.get('series', []):
            if isinstance(s.get('data'), list):
                s['data'] = s['data'][:vc_limit]

    # ── Hide axis labels ─────────────────────────────────────────
    if vc.get('show_axis_labels') is False:
        for axis_key in ('xAxis', 'yAxis'):
            ax = option.get(axis_key)
            if isinstance(ax, dict):
                ax.setdefault('axisLabel', {})['show'] = False
            elif isinstance(ax, list):
                for a in ax:
                    a.setdefault('axisLabel', {})['show'] = False

    # ── Target / reference line ──────────────────────────────────
    target_line = vc.get('target_line')
    if target_line is not None and option.get('series'):
        target_label = vc.get('target_label', '')
        option['series'][0].setdefault('markLine', {
            'silent': True,
            'data': [{'yAxis': target_line,
                      'label': {'formatter': target_label or str(target_line)}}],
            'lineStyle': {'type': 'dashed', 'color': '#ef4444'},
        })


def _build_waterfall_series(option, vc, colors, col_idx, col_val,
                            rows, x_col, y_col_list):
    """Replace series with waterfall (bridge) bar segments."""
    pos_color = vc.get('wf_positive_color', '#91cc75')
    neg_color = vc.get('wf_negative_color', '#ee6666')
    total_color = vc.get('wf_total_color', '#5470c6')
    show_connectors = vc.get('wf_show_connectors', True)

    categories = []
    deltas = []
    for r in rows:
        categories.append(str(col_val(r, x_col) or ''))
        val = col_val(r, y_col_list[0]) if y_col_list else 0
        deltas.append(float(val or 0))

    # Compute base / positive / negative arrays
    base_data = []
    pos_data = []
    neg_data = []
    running = 0
    for d in deltas:
        if d >= 0:
            base_data.append(running)
            pos_data.append(d)
            neg_data.append(0)
        else:
            base_data.append(running + d)
            pos_data.append(0)
            neg_data.append(abs(d))
        running += d

    option['xAxis'] = {'type': 'category', 'data': categories}
    option['yAxis'] = {'type': 'value'}
    option['tooltip'] = {'trigger': 'axis', 'axisPointer': {'type': 'shadow'}}

    # Invisible base series
    option['series'] = [
        {
            'name': '_base',
            'type': 'bar',
            'stack': 'waterfall',
            'data': base_data,
            'itemStyle': {'color': 'transparent', 'borderColor': 'transparent'},
            'emphasis': {'itemStyle': {'color': 'transparent'}},
        },
        {
            'name': 'Increase',
            'type': 'bar',
            'stack': 'waterfall',
            'data': pos_data,
            'itemStyle': {'color': pos_color},
            'label': {'show': True, 'position': 'top'},
        },
        {
            'name': 'Decrease',
            'type': 'bar',
            'stack': 'waterfall',
            'data': neg_data,
            'itemStyle': {'color': neg_color},
            'label': {'show': True, 'position': 'bottom'},
        },
    ]

    # Connector line showing running total
    if show_connectors:
        connector_data = []
        r = 0
        for d in deltas:
            r += d
            connector_data.append(r)
        option['series'].append({
            'name': 'Total',
            'type': 'line',
            'data': connector_data,
            'symbol': 'none',
            'lineStyle': {'type': 'dashed', 'color': total_color, 'width': 1.5},
            'z': 10,
        })

    option['legend'] = {'data': ['Increase', 'Decrease', 'Total']}


def _build_combo_series(option, vc, colors, y_col_list):
    """Retype selected series from line to bar for combo charts."""
    bar_cols_raw = (vc.get('combo_bar_columns') or '').strip()
    bar_cols = set(c.strip() for c in bar_cols_raw.split(',') if c.strip())
    dual_axis = vc.get('combo_secondary_axis', False)

    line_idx = 0
    for s in option.get('series', []):
        if s.get('name', '') in bar_cols:
            s['type'] = 'bar'
        else:
            s['type'] = 'line'
            if dual_axis:
                s['yAxisIndex'] = 1
            line_idx += 1

    if dual_axis:
        primary_axis = option.get('yAxis', {'type': 'value'})
        if isinstance(primary_axis, dict):
            option['yAxis'] = [
                primary_axis,
                {'type': 'value', 'splitLine': {'show': False}},
            ]


def _build_benchmark_series(option, vc, y_col_list):
    """Apply benchmark styling — static markLine or dashed column series."""
    bm_mode = vc.get('benchmark_mode', 'static')
    bm_label = vc.get('benchmark_label', 'Target')

    if bm_mode == 'static':
        bm_value = vc.get('benchmark_value')
        if bm_value is not None and option.get('series'):
            option['series'][0].setdefault('markLine', {
                'silent': True,
                'data': [{'yAxis': bm_value,
                          'label': {'formatter': bm_label or str(bm_value)}}],
                'lineStyle': {'type': 'dashed', 'color': '#ef4444'},
            })
    elif bm_mode == 'column':
        bm_col = (vc.get('benchmark_column') or '').strip()
        if bm_col:
            for s in option.get('series', []):
                if s.get('name') == bm_col:
                    s['lineStyle'] = {'type': 'dashed', 'width': 2}
                    s['symbol'] = 'none'
                    s['name'] = bm_label or bm_col
