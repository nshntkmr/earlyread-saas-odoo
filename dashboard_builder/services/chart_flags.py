# -*- coding: utf-8 -*-
"""
Chart Flags — Visual Config Schema per Chart Family

Defines which visual toggles/options appear in the React builder
for each chart type. The React builder fetches this schema and
dynamically renders controls (checkboxes, dropdowns, number inputs).

Flags are pure rendering instructions — no column names, filter params,
app IDs, or data-source references. This ensures widgets remain
portable across apps, pages, and tabs.

Adding a new flag:
  1. Add the flag dict here
  2. Handle it in _build_echart_option() (dashboard_widget.py)
  3. React builder auto-renders the control from the schema
"""

# ── Bar Chart Flags ──────────────────────────────────────────────────────────

BAR_FLAGS = [
    {
        'flag': 'orientation',
        'type': 'select',
        'default': 'vertical',
        'label': 'Orientation',
        'help': 'Vertical = categories on X-axis, values on Y-axis. Horizontal = swapped.',
        'options': [
            {'value': 'vertical', 'label': 'Vertical'},
            {'value': 'horizontal', 'label': 'Horizontal'},
        ],
    },
    {
        'flag': 'stack',
        'type': 'boolean',
        'default': False,
        'label': 'Stack Bars',
        'help': 'Stack series on top of each other instead of side-by-side.',
    },
    {
        'flag': 'stack_mode',
        'type': 'select',
        'default': 'absolute',
        'label': 'Stack Mode',
        'help': 'Absolute shows raw values stacked. Percentage normalizes each category to 100%.',
        'options': [
            {'value': 'absolute', 'label': 'Absolute Values'},
            {'value': 'percent', 'label': 'Percentage (100%)'},
        ],
        'show_when': {'stack': True},
    },
    {
        'flag': 'show_labels',
        'type': 'boolean',
        'default': False,
        'label': 'Show Value Labels',
        'help': 'Display numeric value on each bar.',
    },
    {
        'flag': 'show_percent_in_label',
        'type': 'boolean',
        'default': False,
        'label': 'Show Percentage in Label',
        'help': 'Append percentage to value label: e.g. "2,484 (42.9%)". '
                'Percentage is auto-calculated from total across all categories.',
        'show_when': {'show_labels': True},
    },
    {
        'flag': 'label_position',
        'type': 'select',
        'default': 'top',
        'label': 'Label Position',
        'help': 'Where the value label appears relative to the bar.',
        'options': [
            {'value': 'top', 'label': 'Top'},
            {'value': 'inside', 'label': 'Inside'},
            {'value': 'outside', 'label': 'Outside'},
        ],
        'show_when': {'show_labels': True},
    },
    {
        'flag': 'color_mode',
        'type': 'select',
        'default': 'by_series',
        'label': 'Color Mode',
        'help': 'How bars are colored. By Series = one color per series (grouped/stacked). '
                'By Category = each category gets a different color (best for single-series).',
        'options': [
            {'value': 'by_series', 'label': 'By Series (default)'},
            {'value': 'by_category', 'label': 'By Category'},
        ],
    },
    {
        'flag': 'number_format',
        'type': 'select',
        'default': 'auto',
        'label': 'Number Format',
        'help': 'How values are formatted on labels and tooltips.',
        'options': [
            {'value': 'auto', 'label': 'Auto'},
            {'value': 'comma', 'label': 'Comma (1,234)'},
            {'value': 'compact', 'label': 'Compact (1.2K)'},
            {'value': 'percent', 'label': 'Percent (42.9%)'},
        ],
    },
    {
        'flag': 'sort',
        'type': 'select',
        'default': 'none',
        'label': 'Sort Categories',
        'help': 'Reorder bars by value or alphabetically. SQL Order uses the query ORDER BY.',
        'options': [
            {'value': 'none', 'label': 'SQL Order (default)'},
            {'value': 'value_desc', 'label': 'Highest First'},
            {'value': 'value_asc', 'label': 'Lowest First'},
            {'value': 'alpha_asc', 'label': 'A \u2192 Z'},
            {'value': 'alpha_desc', 'label': 'Z \u2192 A'},
        ],
    },
    {
        'flag': 'limit',
        'type': 'number',
        'default': 0,
        'label': 'Max Categories',
        'help': 'Limit how many bars to show. 0 = show all. Applied after sort.',
    },
    {
        'flag': 'show_axis_labels',
        'type': 'boolean',
        'default': True,
        'label': 'Show Axis Labels',
        'help': 'Show category names and value ticks on the axes.',
    },
    {
        'flag': 'bar_width',
        'type': 'number',
        'default': None,
        'label': 'Bar Width (px)',
        'help': 'Fixed bar width in pixels. Leave empty for auto width.',
    },
    {
        'flag': 'bar_gap',
        'type': 'text',
        'default': '30%',
        'label': 'Bar Gap',
        'help': 'Space between bars in the same category (e.g. "30%", "10px").',
    },
    {
        'flag': 'target_line',
        'type': 'number',
        'default': None,
        'label': 'Target / Reference Line',
        'help': 'Draws a dashed horizontal line at this value for benchmarking.',
    },
    {
        'flag': 'target_label',
        'type': 'text',
        'default': '',
        'label': 'Target Line Label',
        'help': 'Label shown next to the reference line (e.g. "Q4 Target").',
        'show_when': {'target_line': '__not_null__'},
    },
]


# ── Pie / Donut — Common Flags ────────────────────────────────────────────────

_PIE_DONUT_COMMON = [
    {
        'flag': 'show_labels',
        'type': 'boolean',
        'default': True,
        'label': 'Show Slice Labels',
        'help': 'Display label text on or near each slice.',
    },
    {
        'flag': 'label_position',
        'type': 'select',
        'default': 'outside',
        'label': 'Label Position',
        'help': 'Where slice labels appear relative to the pie/donut.',
        'options': [
            {'value': 'outside', 'label': 'Outside'},
            {'value': 'inside', 'label': 'Inside'},
        ],
        'show_when': {'show_labels': True},
    },
    {
        'flag': 'label_format',
        'type': 'select',
        'default': 'name',
        'label': 'Label Format',
        'help': 'What information to display in slice labels.',
        'options': [
            {'value': 'name', 'label': 'Name only'},
            {'value': 'name_value', 'label': 'Name + Value'},
            {'value': 'name_percent', 'label': 'Name + Percentage'},
            {'value': 'name_value_percent', 'label': 'Name + Value + Percentage'},
        ],
        'show_when': {'show_labels': True},
    },
    {
        'flag': 'legend_position',
        'type': 'select',
        'default': 'left',
        'label': 'Legend Position',
        'help': 'Where the legend appears, or hide it entirely.',
        'options': [
            {'value': 'left', 'label': 'Left (vertical)'},
            {'value': 'right', 'label': 'Right (vertical)'},
            {'value': 'top', 'label': 'Top (horizontal)'},
            {'value': 'bottom', 'label': 'Bottom (horizontal)'},
            {'value': 'none', 'label': 'Hidden'},
        ],
    },
    {
        'flag': 'sort',
        'type': 'select',
        'default': 'none',
        'label': 'Sort Slices',
        'help': 'Reorder slices by value. SQL Order uses the query ORDER BY.',
        'options': [
            {'value': 'none', 'label': 'SQL Order (default)'},
            {'value': 'value_desc', 'label': 'Largest First'},
            {'value': 'value_asc', 'label': 'Smallest First'},
        ],
    },
    {
        'flag': 'limit',
        'type': 'number',
        'default': 0,
        'label': 'Max Slices',
        'help': 'Limit how many slices to show. 0 = show all. Remaining slices are '
                'grouped as "Other".',
    },
]


# ── Donut-Specific Flags ──────────────────────────────────────────────────────

DONUT_FLAGS = [
    {
        'flag': 'donut_style',
        'type': 'select',
        'default': 'standard',
        'label': 'Donut Style',
        'help': 'Visual variant of the donut chart. '
                'Center Label shows the hovered slice name and value in the center hole. '
                'Rounded adds rounded corners between slices. '
                'Half shows a semicircle (180°). '
                'Rose (Nightingale) varies slice radius by value. '
                'Nested shows parent/child as two concentric rings. '
                'Multi-Ring places groups side-by-side as separate rings.',
        'options': [
            {'value': 'standard', 'label': 'Standard Donut'},
            {'value': 'label_center', 'label': 'Center Label (on hover)'},
            {'value': 'rounded', 'label': 'Rounded Corners'},
            {'value': 'semi', 'label': 'Half Donut (180°)'},
            {'value': 'rose', 'label': 'Rose / Nightingale'},
            {'value': 'nested', 'label': 'Nested (2 rings)'},
            {'value': 'multi_ring', 'label': 'Multi-Ring Comparison'},
        ],
    },
    {
        'flag': 'rose_type',
        'type': 'select',
        'default': 'area',
        'label': 'Rose Type',
        'help': '"Area" varies slice area proportionally (recommended). '
                '"Radius" varies only the radius.',
        'options': [
            {'value': 'area', 'label': 'Area (proportional)'},
            {'value': 'radius', 'label': 'Radius'},
        ],
        'show_when': {'donut_style': 'rose'},
    },
    # ── Nested ring flags ──────────────────────────────────────────────────
    {
        'flag': 'nested_inner_radius_start', 'type': 'text', 'default': '0%',
        'label': 'Inner Ring — Radius Start',
        'help': 'Inner ring starts at this % from center (default 0%).',
        'show_when': {'donut_style': 'nested'},
    },
    {
        'flag': 'nested_inner_radius_end', 'type': 'text', 'default': '30%',
        'label': 'Inner Ring — Radius End',
        'help': 'Inner ring ends at this % from center (default 30%).',
        'show_when': {'donut_style': 'nested'},
    },
    {
        'flag': 'nested_inner_label_pos', 'type': 'select', 'default': 'inner',
        'label': 'Inner Ring — Label Position',
        'options': [
            {'value': 'inner', 'label': 'Inner (centered in slice)'},
            {'value': 'inside', 'label': 'Inside (near edge)'},
            {'value': 'outside', 'label': 'Outside'},
        ],
        'show_when': {'donut_style': 'nested'},
    },
    {
        'flag': 'nested_inner_label_format', 'type': 'select', 'default': 'name',
        'label': 'Inner Ring — Label Format',
        'options': [
            {'value': 'name', 'label': 'Name only'},
            {'value': 'name_value', 'label': 'Name + Value'},
            {'value': 'name_percent', 'label': 'Name + Percentage'},
            {'value': 'name_value_percent', 'label': 'Name + Value + Percentage'},
        ],
        'show_when': {'donut_style': 'nested'},
    },
    {
        'flag': 'nested_outer_radius_start', 'type': 'text', 'default': '40%',
        'label': 'Outer Ring — Radius Start',
        'help': 'Outer ring starts at this % from center (default 40%). Must be > inner ring end.',
        'show_when': {'donut_style': 'nested'},
    },
    {
        'flag': 'nested_outer_radius_end', 'type': 'text', 'default': '65%',
        'label': 'Outer Ring — Radius End',
        'help': 'Outer ring ends at this % from center (default 65%).',
        'show_when': {'donut_style': 'nested'},
    },
    {
        'flag': 'nested_outer_label_pos', 'type': 'select', 'default': 'outside',
        'label': 'Outer Ring — Label Position',
        'options': [
            {'value': 'outside', 'label': 'Outside'},
            {'value': 'inside', 'label': 'Inside'},
            {'value': 'inner', 'label': 'Inner (centered in slice)'},
        ],
        'show_when': {'donut_style': 'nested'},
    },
    {
        'flag': 'nested_outer_label_format', 'type': 'select', 'default': 'name',
        'label': 'Outer Ring — Label Format',
        'options': [
            {'value': 'name', 'label': 'Name only'},
            {'value': 'name_value', 'label': 'Name + Value'},
            {'value': 'name_percent', 'label': 'Name + Percentage'},
            {'value': 'name_value_percent', 'label': 'Name + Value + Percentage'},
        ],
        'show_when': {'donut_style': 'nested'},
    },
    {
        'flag': 'inner_radius',
        'type': 'text',
        'default': '40%',
        'label': 'Inner Radius',
        'help': 'Inner hole size as percentage (e.g. "40%"). Larger = bigger hole.',
        'show_when': {'donut_style': ['standard', 'label_center', 'rounded', 'rose']},
    },
    {
        'flag': 'outer_radius',
        'type': 'text',
        'default': '70%',
        'label': 'Outer Radius',
        'help': 'Outer edge size as percentage (e.g. "70%", "85%").',
        'show_when': {'donut_style': ['standard', 'label_center', 'rounded', 'rose']},
    },
    {
        'flag': 'center_mode',
        'type': 'select',
        'default': 'none',
        'label': 'Center Display',
        'help': 'What to show in the center hole. '
                '"Auto Total" computes the sum of all slices dynamically. '
                '"Static Text" shows free-form text you type.',
        'options': [
            {'value': 'none', 'label': 'None'},
            {'value': 'auto_total', 'label': 'Auto Total (computed from slices)'},
            {'value': 'static', 'label': 'Static Text'},
        ],
        'show_when': {'donut_style': ['standard', 'label_center', 'rounded', 'rose']},
    },
    {
        'flag': 'center_text',
        'type': 'text',
        'default': '',
        'label': 'Center Label',
        'help': 'Label shown above the computed total (e.g. "Total", "Admits", "Episodes").',
        'show_when': {'center_mode': 'auto_total'},
    },
    {
        'flag': 'center_static_text',
        'type': 'text',
        'default': '',
        'label': 'Center Static Text',
        'help': 'Free text shown in the center (e.g. "Market Share", "74%").',
        'show_when': {'center_mode': 'static'},
    },
    *_PIE_DONUT_COMMON,
]


# ── Pie-Specific Flags ────────────────────────────────────────────────────────

PIE_FLAGS = [*_PIE_DONUT_COMMON]


# ── Registry ─────────────────────────────────────────────────────────────────
# Add new chart families here as they are implemented.

CHART_FLAGS = {
    'bar': BAR_FLAGS,
    'pie': PIE_FLAGS,
    'donut': DONUT_FLAGS,
    # 'line': LINE_FLAGS,     # future
    # 'gauge': GAUGE_FLAGS,   # future
    # 'radar': RADAR_FLAGS,   # future
}


def get_flags_for_chart(chart_type):
    """Return the flag schema for a chart type.

    Returns an empty list for chart types without defined flags,
    allowing the builder to render with no chart-specific options.
    """
    return CHART_FLAGS.get(chart_type, [])
