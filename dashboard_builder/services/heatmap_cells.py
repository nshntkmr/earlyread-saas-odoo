# -*- coding: utf-8 -*-
"""Opt-in empty cells for HEATMAP charts.

SINGLE SOURCE OF TRUTH used by BOTH:
  • posterra_portal ``dashboard.widget._build_echart_option`` (portal runtime;
    the PDF export draws the same option)
  • dashboard_builder ``preview_formatter._build_echart_preview`` (designer preview)

Two visual_config options, both OFF by default. While they are off nothing
here changes the option, so every existing heatmap is byte-identical:

  ``heatmap_blank_null``    "Leave SQL NULL cells empty". A SQL NULL becomes a
                            JSON ``null`` cell, which ECharts does not draw at
                            all — no tint, no value label — instead of the
                            historical 0. The SQL decides: return NULL for
                            "nothing there" and 0 for a real zero.
  ``heatmap_label_column``  "Cell Label Column". Every cell becomes
                            ``[x, y, value, label_text]``; the series label
                            prints the text (``{@[3]}``) while ``visualMap``
                            keeps colouring by the value (``dimension: 2`` —
                            without it ECharts would map the LAST dimension,
                            the text). Lets the SQL print ``<11`` on a
                            suppressed cell, or put a totals row/column on the
                            grid: cells carrying -1 draw with the override's
                            ``outOfRange`` colour while the label prints the
                            total — provided the override sets
                            ``range: [0, 100000]`` and no ``min`` (while the
                            range equals the full extent ECharts counts every
                            value as in range).

No ORM / no I/O.
"""

BLANK_NULL_FLAG = 'heatmap_blank_null'
LABEL_COLUMN_FLAG = 'heatmap_label_column'
LABEL_FORMATTER = '{@[3]}'
VALUE_DIMENSION = 2


def label_column(vc, cols):
    """The configured cell-label column when it is present in the SQL result,
    else '' (unset, blank, or a column the query did not return → off)."""
    if not isinstance(vc, dict):
        return ''
    name = vc.get(LABEL_COLUMN_FLAG)
    name = name.strip() if isinstance(name, str) else ''
    return name if name and name in (cols or []) else ''


def label_text(raw):
    """Cell label text: NULL → '' (prints nothing), anything else as text."""
    return '' if raw is None else str(raw)


def blank_null_on(vc):
    """True when the flag is set in a parsed visual_config dict."""
    return isinstance(vc, dict) and bool(vc.get(BLANK_NULL_FLAG))


def cell_value(raw, blank_null):
    """A cell value as the builders store it. Historically every falsy SQL
    value became 0 (``value or 0``); with the flag a SQL NULL stays None so
    the chart leaves that cell empty."""
    if blank_null and raw is None:
        return None
    return raw or 0


def value_range(heat_data):
    """(min, max) over the drawn cells for ``visualMap``, with the historical
    defaults (0, 1) when nothing is drawn. Empty (None) cells are ignored."""
    values = [d[2] for d in heat_data if d[2] is not None]
    return (min(values, default=0), max(values, default=1))
