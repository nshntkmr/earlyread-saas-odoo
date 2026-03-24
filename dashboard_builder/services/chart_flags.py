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
        'flag': 'label_position',
        'type': 'select',
        'default': 'top',
        'label': 'Label Position',
        'options': [
            {'value': 'top', 'label': 'Top'},
            {'value': 'inside', 'label': 'Inside'},
            {'value': 'outside', 'label': 'Outside'},
        ],
        'show_when': {'show_labels': True},
    },
    {
        'flag': 'sort',
        'type': 'select',
        'default': 'none',
        'label': 'Sort Categories',
        'options': [
            {'value': 'none', 'label': 'SQL Order (default)'},
            {'value': 'value_desc', 'label': 'Highest First'},
            {'value': 'value_asc', 'label': 'Lowest First'},
            {'value': 'alpha_asc', 'label': 'A → Z'},
            {'value': 'alpha_desc', 'label': 'Z → A'},
        ],
    },
    {
        'flag': 'limit',
        'type': 'number',
        'default': 0,
        'label': 'Max Categories',
        'help': '0 = show all. Truncates after sort.',
    },
    {
        'flag': 'show_axis_labels',
        'type': 'boolean',
        'default': True,
        'label': 'Show Axis Labels',
    },
    {
        'flag': 'bar_width',
        'type': 'number',
        'default': None,
        'label': 'Bar Width (px)',
        'help': 'Leave empty for auto width.',
    },
    {
        'flag': 'bar_gap',
        'type': 'text',
        'default': '30%',
        'label': 'Bar Gap',
        'help': 'Gap between bars (e.g. "30%", "10px").',
    },
    {
        'flag': 'target_line',
        'type': 'number',
        'default': None,
        'label': 'Target / Reference Line',
        'help': 'Draws a dashed reference line at this value.',
    },
    {
        'flag': 'target_label',
        'type': 'text',
        'default': '',
        'label': 'Target Line Label',
        'show_when': {'target_line': '__not_null__'},
    },
]


# ── Registry ─────────────────────────────────────────────────────────────────
# Add new chart families here as they are implemented.

CHART_FLAGS = {
    'bar': BAR_FLAGS,
    # 'line': LINE_FLAGS,     # future
    # 'pie': PIE_FLAGS,       # future
    # 'donut': DONUT_FLAGS,   # future
    # 'gauge': GAUGE_FLAGS,   # future
    # 'radar': RADAR_FLAGS,   # future
}


def get_flags_for_chart(chart_type):
    """Return the flag schema for a chart type.

    Returns an empty list for chart types without defined flags,
    allowing the builder to render with no chart-specific options.
    """
    return CHART_FLAGS.get(chart_type, [])
