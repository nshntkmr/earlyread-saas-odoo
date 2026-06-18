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
        'flag': 'axis_label_show_all',
        'type': 'boolean',
        'default': False,
        'label': 'Show All Category Labels',
        'help': 'Force every category label to display on the axis '
                '(disables ECharts auto-hide that drops labels when crowded). '
                'Recommended when you have a small fixed number of categories '
                'with long names.',
    },
    {
        'flag': 'axis_label_wrap',
        'type': 'boolean',
        'default': False,
        'label': 'Wrap Long Category Labels',
        'help': 'Break long category names onto multiple lines instead of '
                'truncating them. Applies to the X-axis (vertical bars) or '
                'Y-axis (horizontal bars).',
    },
    {
        'flag': 'axis_label_wrap_width',
        'type': 'number',
        'default': 100,
        'label': 'Wrap Width (px)',
        'help': 'Maximum pixel width of each label before wrapping. '
                'Smaller values = more line breaks. Typical range: 80–160.',
        'show_when': {'axis_label_wrap': True},
    },
    {
        'flag': 'axis_label_rotate',
        'type': 'number',
        'default': 0,
        'label': 'Label Rotation (degrees)',
        'help': 'Rotate axis labels. 0 = horizontal, 30–45 = diagonal, '
                '90 = vertical. Useful when wrap is off but labels still '
                'overlap.',
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


# ── Line Chart Flags ─────────────────────────────────────────────────────────

LINE_FLAGS = [
    # ── Primary variant selector ─────────────────────────────────
    {
        'flag': 'line_style',
        'type': 'select',
        'default': 'basic',
        'label': 'Line Style',
        'help': 'Basic = straight lines. Area = filled under. '
                'Stacked = cumulative. Waterfall = sequential deltas. '
                'Combo = mixed bar+line. Benchmark = trend vs target.',
        'options': [
            {'value': 'basic',        'label': 'Basic Line'},
            {'value': 'area',         'label': 'Area Chart'},
            {'value': 'stacked_line', 'label': 'Stacked Line'},
            {'value': 'stacked_area', 'label': 'Stacked Area'},
            {'value': 'waterfall',    'label': 'Waterfall / Bridge'},
            {'value': 'combo',        'label': 'Combo (Bar + Line)'},
            {'value': 'benchmark',    'label': 'Trend + Benchmark'},
        ],
    },

    # ── Universal line appearance ────────────────────────────────
    {
        'flag': 'smooth',
        'type': 'boolean',
        'default': False,
        'label': 'Smooth Curves',
        'help': 'Use spline interpolation instead of straight segments.',
        'show_when': {'line_style': ['basic', 'area', 'stacked_line', 'stacked_area', 'benchmark']},
    },
    {
        'flag': 'show_points',
        'type': 'boolean',
        'default': True,
        'label': 'Show Data Points',
        'help': 'Display circle markers at each data point.',
        'show_when': {'line_style': ['basic', 'area', 'stacked_line', 'stacked_area', 'benchmark']},
    },
    {
        'flag': 'point_size',
        'type': 'number',
        'default': 4,
        'label': 'Point Size (px)',
        'show_when': {'show_points': True},
    },
    {
        'flag': 'line_width',
        'type': 'number',
        'default': 2,
        'label': 'Line Width (px)',
        'show_when': {'line_style': ['basic', 'area', 'stacked_line', 'stacked_area', 'benchmark']},
    },
    {
        'flag': 'step_type',
        'type': 'select',
        'default': 'none',
        'label': 'Step Function',
        'help': 'Render as step function instead of diagonal lines.',
        'options': [
            {'value': 'none',   'label': 'None (diagonal)'},
            {'value': 'start',  'label': 'Step Start'},
            {'value': 'middle', 'label': 'Step Middle'},
            {'value': 'end',    'label': 'Step End'},
        ],
        'show_when': {'line_style': ['basic', 'area', 'stacked_line', 'stacked_area']},
    },

    # ── Area-specific ────────────────────────────────────────────
    {
        'flag': 'area_opacity',
        'type': 'number',
        'default': 0.3,
        'label': 'Area Opacity (0–1)',
        'help': 'Opacity of the filled area under the line. 0 = transparent, 1 = solid.',
        'show_when': {'line_style': ['area', 'stacked_area']},
    },
    {
        'flag': 'area_gradient',
        'type': 'boolean',
        'default': False,
        'label': 'Gradient Fill',
        'help': 'Vertical gradient from series color at top to transparent at bottom.',
        'show_when': {'line_style': ['area', 'stacked_area']},
    },

    # ── Waterfall-specific ───────────────────────────────────────
    {
        'flag': 'wf_positive_color',
        'type': 'text',
        'default': '#91cc75',
        'label': 'Positive Color',
        'help': 'Color for bars representing increases.',
        'show_when': {'line_style': 'waterfall'},
    },
    {
        'flag': 'wf_negative_color',
        'type': 'text',
        'default': '#ee6666',
        'label': 'Negative Color',
        'help': 'Color for bars representing decreases.',
        'show_when': {'line_style': 'waterfall'},
    },
    {
        'flag': 'wf_total_color',
        'type': 'text',
        'default': '#5470c6',
        'label': 'Total Bar Color',
        'help': 'Color for the starting/ending total bars.',
        'show_when': {'line_style': 'waterfall'},
    },
    {
        'flag': 'wf_show_connectors',
        'type': 'boolean',
        'default': True,
        'label': 'Show Connector Lines',
        'help': 'Dashed lines connecting bar tops to show running total.',
        'show_when': {'line_style': 'waterfall'},
    },

    # ── Combo-specific ───────────────────────────────────────────
    {
        'flag': 'combo_bar_columns',
        'type': 'text',
        'default': '',
        'label': 'Bar Columns (comma-separated)',
        'help': 'Which y_columns to render as bars. Remaining columns render as lines.',
        'show_when': {'line_style': 'combo'},
    },
    {
        'flag': 'combo_secondary_axis',
        'type': 'boolean',
        'default': False,
        'label': 'Dual Y-Axis',
        'help': 'Lines use a second Y-axis on the right. Useful when bar and line scales differ.',
        'show_when': {'line_style': 'combo'},
    },

    # ── Benchmark-specific ───────────────────────────────────────
    {
        'flag': 'benchmark_mode',
        'type': 'select',
        'default': 'static',
        'label': 'Benchmark Source',
        'help': 'Static = horizontal line at a fixed value. Column = render a query column as dashed line.',
        'options': [
            {'value': 'static', 'label': 'Static Value'},
            {'value': 'column', 'label': 'Column from Query'},
        ],
        'show_when': {'line_style': 'benchmark'},
    },
    {
        'flag': 'benchmark_value',
        'type': 'number',
        'default': None,
        'label': 'Benchmark Value',
        'help': 'The fixed target/reference value for the horizontal benchmark line.',
        'show_when': {'benchmark_mode': 'static', 'line_style': 'benchmark'},
    },
    {
        'flag': 'benchmark_label',
        'type': 'text',
        'default': 'Target',
        'label': 'Benchmark Label',
        'help': 'Label shown next to the benchmark line.',
        'show_when': {'line_style': 'benchmark'},
    },
    {
        'flag': 'benchmark_column',
        'type': 'text',
        'default': '',
        'label': 'Benchmark Column Name',
        'help': 'Name of the y_column that is the benchmark (rendered as dashed line).',
        'show_when': {'benchmark_mode': 'column', 'line_style': 'benchmark'},
    },

    # ── Common controls ──────────────────────────────────────────
    {
        'flag': 'show_labels',
        'type': 'boolean',
        'default': False,
        'label': 'Show Value Labels',
        'help': 'Display numeric value at each data point.',
    },
    {
        'flag': 'label_position',
        'type': 'select',
        'default': 'top',
        'label': 'Label Position',
        'options': [
            {'value': 'top', 'label': 'Top'},
            {'value': 'inside', 'label': 'Inside'},
        ],
        'show_when': {'show_labels': True},
    },
    {
        'flag': 'number_format',
        'type': 'select',
        'default': 'auto',
        'label': 'Number Format',
        'help': 'How values are formatted on labels and tooltips.',
        'options': [
            {'value': 'auto',    'label': 'Auto'},
            {'value': 'comma',   'label': 'Comma (1,234)'},
            {'value': 'compact', 'label': 'Compact (1.2K)'},
            {'value': 'percent', 'label': 'Percent (42.9%)'},
        ],
    },
    {
        'flag': 'show_axis_labels',
        'type': 'boolean',
        'default': True,
        'label': 'Show Axis Labels',
        'help': 'Show category names and value ticks on the axes.',
    },
    {
        'flag': 'legend_position',
        'type': 'select',
        'default': 'top',
        'label': 'Legend Position',
        'options': [
            {'value': 'top',    'label': 'Top (horizontal)'},
            {'value': 'bottom', 'label': 'Bottom (horizontal)'},
            {'value': 'left',   'label': 'Left (vertical)'},
            {'value': 'right',  'label': 'Right (vertical)'},
            {'value': 'none',   'label': 'Hidden'},
        ],
    },
    {
        'flag': 'target_line',
        'type': 'number',
        'default': None,
        'label': 'Reference Line Value',
        'help': 'Draws a dashed horizontal line at this value for benchmarking.',
        'show_when': {'line_style': ['basic', 'area', 'stacked_line', 'stacked_area']},
    },
    {
        'flag': 'target_label',
        'type': 'text',
        'default': '',
        'label': 'Reference Line Label',
        'help': 'Label shown next to the reference line (e.g. "Q4 Target").',
        'show_when': {'target_line': '__not_null__'},
    },
    {
        'flag': 'sort',
        'type': 'select',
        'default': 'none',
        'label': 'Sort Categories',
        'help': 'Reorder data points by value or alphabetically.',
        'options': [
            {'value': 'none',       'label': 'SQL Order (default)'},
            {'value': 'value_desc', 'label': 'Highest First'},
            {'value': 'value_asc',  'label': 'Lowest First'},
            {'value': 'alpha_asc',  'label': 'A → Z'},
            {'value': 'alpha_desc', 'label': 'Z → A'},
        ],
    },
    {
        'flag': 'limit',
        'type': 'number',
        'default': 0,
        'label': 'Max Data Points',
        'help': 'Limit how many data points to show. 0 = show all. Applied after sort.',
    },
]


# ── Gauge Chart Flags ────────────────────────────────────────────────────────

_ARC_STYLES = ['standard', 'half_arc', 'three_quarter']

GAUGE_FLAGS = [
    # ── Primary variant selector ─────────────────────────────────
    {
        'flag': 'gauge_style',
        'type': 'select',
        'default': 'standard',
        'label': 'Gauge Style',
        'help': 'Standard = 220° arc with needle. '
                'Half-Arc = 180° semicircle (KPI tiles). '
                'Three-Quarter = 270° cockpit-style. '
                'Bullet = horizontal progress bar with target. '
                'Traffic Light = RAG circles with status badge. '
                'Percentile Rank = position on 0-100 scale. '
                'Multi-Ring = concentric rings for composite scores.',
        'options': [
            {'value': 'standard',          'label': 'Standard Arc (220°)'},
            {'value': 'half_arc',          'label': 'Half-Arc (180°)'},
            {'value': 'three_quarter',     'label': 'Three-Quarter (270°)'},
            {'value': 'bullet',            'label': 'Bullet Gauge'},
            {'value': 'traffic_light_rag', 'label': 'Traffic Light / RAG'},
            {'value': 'percentile_rank',   'label': 'Percentile Rank'},
            {'value': 'multi_ring',        'label': 'Multi-Ring Nested'},
        ],
    },

    # ── Component label (all gauge variants) ─────────────────────
    {
        'flag': 'gauge_label',
        'type': 'text',
        'default': '',
        'label': 'Internal Label',
        'help': 'Text shown inside the gauge component (below the card title). '
                'Leave empty to show no internal label. '
                'The card header title is always shown separately.',
    },

    # ── Common arc flags (standard, half_arc, three_quarter) ─────
    {
        'flag': 'gauge_min',
        'type': 'number',
        'default': 0,
        'label': 'Scale Minimum',
        'help': 'Minimum value on the gauge scale.',
        'show_when': {'gauge_style': _ARC_STYLES},
    },
    {
        'flag': 'gauge_max',
        'type': 'number',
        'default': 100,
        'label': 'Scale Maximum',
        'help': 'Maximum value on the gauge scale.',
        'show_when': {'gauge_style': _ARC_STYLES},
    },
    {
        'flag': 'gauge_color_mode',
        'type': 'select',
        'default': 'single',
        'label': 'Color Mode',
        'help': 'Single uses palette color. Traffic Light shows red/amber/green zones.',
        'options': [
            {'value': 'single', 'label': 'Single Color (from palette)'},
            {'value': 'traffic_light', 'label': 'Traffic Light (R/A/G zones)'},
        ],
        'show_when': {'gauge_style': _ARC_STYLES},
    },
    {
        'flag': 'gauge_warn_threshold',
        'type': 'number',
        'default': 50,
        'label': 'Warning Threshold (%)',
        'help': 'Percentage of scale where color shifts from red to amber.',
        'show_when': {'gauge_color_mode': 'traffic_light'},
    },
    {
        'flag': 'gauge_good_threshold',
        'type': 'number',
        'default': 70,
        'label': 'Good Threshold (%)',
        'help': 'Percentage of scale where color shifts from amber to green.',
        'show_when': {'gauge_color_mode': 'traffic_light'},
    },
    {
        'flag': 'gauge_number_format',
        'type': 'select',
        'default': 'auto',
        'label': 'Number Format',
        'help': 'How the center value is displayed.',
        'options': [
            {'value': 'auto', 'label': 'Auto (% if 0-100)'},
            {'value': 'percent', 'label': 'Percent (78.4%)'},
            {'value': 'comma', 'label': 'Comma (1,234)'},
            {'value': 'decimal1', 'label': '1 Decimal (78.4)'},
            {'value': 'decimal2', 'label': '2 Decimals (78.40)'},
            {'value': 'integer', 'label': 'Integer (78)'},
            {'value': 'currency', 'label': 'Currency ($1,234)'},
        ],
        'show_when': {'gauge_style': _ARC_STYLES + ['bullet', 'percentile_rank', 'multi_ring']},
    },
    {
        'flag': 'show_needle',
        'type': 'boolean',
        'default': True,
        'label': 'Show Needle',
        'help': 'Display the pointer needle on the arc.',
        'show_when': {'gauge_style': ['standard', 'three_quarter']},
    },
    {
        'flag': 'show_progress_bar',
        'type': 'boolean',
        'default': True,
        'label': 'Show Progress Arc',
        'help': 'Colored arc from min to current value.',
        'show_when': {'gauge_style': _ARC_STYLES},
    },
    {
        'flag': 'show_scale_labels',
        'type': 'boolean',
        'default': True,
        'label': 'Show Scale Labels',
        'help': 'Display min/max and split labels around the arc.',
        'show_when': {'gauge_style': _ARC_STYLES},
    },

    # ── Target marker (arc + bullet) ─────────────────────────────
    {
        'flag': 'target_value',
        'type': 'number',
        'default': None,
        'label': 'Target Value',
        'help': 'Draws a target marker on the gauge. For arc gauges shows a dashed mark; '
                'for bullet shows a vertical line.',
        'show_when': {'gauge_style': _ARC_STYLES + ['bullet']},
    },
    {
        'flag': 'target_label',
        'type': 'text',
        'default': '',
        'label': 'Target Label',
        'help': 'Text shown near the target marker (e.g. "Target: ≥85%").',
        'show_when': {'target_value': '__not_null__'},
    },

    # ── Bullet gauge flags ───────────────────────────────────────
    {
        'flag': 'bullet_min',
        'type': 'number',
        'default': 0,
        'label': 'Scale Minimum',
        'help': 'Minimum value on the bullet scale.',
        'show_when': {'gauge_style': 'bullet'},
    },
    {
        'flag': 'bullet_max',
        'type': 'number',
        'default': 100,
        'label': 'Scale Maximum',
        'help': 'Maximum value on the bullet scale.',
        'show_when': {'gauge_style': 'bullet'},
    },
    {
        'flag': 'bullet_orientation',
        'type': 'select',
        'default': 'horizontal',
        'label': 'Orientation',
        'help': 'Direction of the bullet bar.',
        'options': [
            {'value': 'horizontal', 'label': 'Horizontal'},
            {'value': 'vertical', 'label': 'Vertical'},
        ],
        'show_when': {'gauge_style': 'bullet'},
    },
    {
        'flag': 'bullet_ranges',
        'type': 'text',
        'default': '',
        'label': 'Range Zones (JSON)',
        'help': 'JSON array of zones: [{"to": 70, "color": "#ef4444", "label": "Poor <70"}, '
                '{"to": 85, "color": "#f59e0b", "label": "At risk 70-85"}, '
                '{"to": 100, "color": "#10b981", "label": "On target >85"}]. '
                'Leave empty for auto red/amber/green.',
        'show_when': {'gauge_style': 'bullet'},
    },
    {
        'flag': 'bullet_show_labels',
        'type': 'boolean',
        'default': True,
        'label': 'Show Range Labels',
        'help': 'Display threshold descriptions below the bar (e.g. "Poor <70 | At risk 70-85").',
        'show_when': {'gauge_style': 'bullet'},
    },
    {
        'flag': 'bullet_bar_height',
        'type': 'number',
        'default': 12,
        'label': 'Bar Height (px)',
        'help': 'Height of the actual value bar inside the range zones.',
        'show_when': {'gauge_style': 'bullet'},
    },

    # ── Traffic Light / RAG flags ────────────────────────────────
    {
        'flag': 'rag_layout',
        'type': 'select',
        'default': 'circles',
        'label': 'Layout',
        'help': 'Circles = single KPI with 3 colored circles + value + badge. '
                'Scorecard = multiple metrics listed with colored dot + value + status text.',
        'options': [
            {'value': 'circles', 'label': 'Traffic Light (circles)'},
            {'value': 'scorecard', 'label': 'RAG Scorecard (list)'},
        ],
        'show_when': {'gauge_style': 'traffic_light_rag'},
    },
    {
        'flag': 'rag_red_threshold',
        'type': 'number',
        'default': 70,
        'label': 'Red → Amber Threshold',
        'help': 'Values below this are red.',
        'show_when': {'gauge_style': 'traffic_light_rag'},
    },
    {
        'flag': 'rag_green_threshold',
        'type': 'number',
        'default': 85,
        'label': 'Amber → Green Threshold',
        'help': 'Values at or above this are green.',
        'show_when': {'gauge_style': 'traffic_light_rag'},
    },
    {
        'flag': 'rag_invert',
        'type': 'boolean',
        'default': False,
        'label': 'Lower is Better',
        'help': 'Invert thresholds: lower values are green (e.g. rehospitalization rate).',
        'show_when': {'gauge_style': 'traffic_light_rag'},
    },
    {
        'flag': 'rag_show_badge',
        'type': 'boolean',
        'default': True,
        'label': 'Show Status Badge',
        'help': 'Display "On target", "At risk", etc. below the value.',
        'show_when': {'gauge_style': 'traffic_light_rag'},
    },
    {
        'flag': 'rag_badge_green',
        'type': 'text',
        'default': 'On target',
        'label': 'Green Badge Text',
        'show_when': {'rag_show_badge': True, 'gauge_style': 'traffic_light_rag'},
    },
    {
        'flag': 'rag_badge_amber',
        'type': 'text',
        'default': 'Watch',
        'label': 'Amber Badge Text',
        'show_when': {'rag_show_badge': True, 'gauge_style': 'traffic_light_rag'},
    },
    {
        'flag': 'rag_badge_red',
        'type': 'text',
        'default': 'At risk',
        'label': 'Red Badge Text',
        'show_when': {'rag_show_badge': True, 'gauge_style': 'traffic_light_rag'},
    },
    {
        'flag': 'rag_show_thresholds',
        'type': 'boolean',
        'default': True,
        'label': 'Show Threshold Text',
        'help': 'Display ranges below (e.g. "G: ≥85 | A: 70-85 | R: <70").',
        'show_when': {'gauge_style': 'traffic_light_rag'},
    },

    # ── Percentile Rank flags ────────────────────────────────────
    {
        'flag': 'percentile_show_quartiles',
        'type': 'boolean',
        'default': True,
        'label': 'Show Quartile Markers',
        'help': 'Display 25th, 50th, 75th markers on the bar.',
        'show_when': {'gauge_style': 'percentile_rank'},
    },
    {
        'flag': 'percentile_show_badge',
        'type': 'boolean',
        'default': True,
        'label': 'Show Quartile Badge',
        'help': 'Display "Top quartile", "2nd quartile" etc. badge.',
        'show_when': {'gauge_style': 'percentile_rank'},
    },
    {
        'flag': 'percentile_invert',
        'type': 'boolean',
        'default': False,
        'label': 'Lower is Better (Inverted)',
        'help': 'Higher rank means better (e.g. 88th percentile for rehospitalization).',
        'show_when': {'gauge_style': 'percentile_rank'},
    },

    # ── Multi-Ring Nested flags ──────────────────────────────────
    {
        'flag': 'multi_ring_max_rings',
        'type': 'number',
        'default': 6,
        'label': 'Max Rings',
        'help': 'Maximum number of concentric rings (2-6). Extra rows are ignored.',
        'show_when': {'gauge_style': 'multi_ring'},
    },
    {
        'flag': 'multi_ring_show_center',
        'type': 'boolean',
        'default': True,
        'label': 'Show Center Label',
        'help': 'Display a label/value in the center of the rings.',
        'show_when': {'gauge_style': 'multi_ring'},
    },
    {
        'flag': 'multi_ring_center_text',
        'type': 'text',
        'default': '',
        'label': 'Center Text',
        'help': 'Text shown in center (e.g. "3.5 ★", "B+"). Leave empty to auto-compute average.',
        'show_when': {'multi_ring_show_center': True, 'gauge_style': 'multi_ring'},
    },
    {
        'flag': 'multi_ring_center_subtitle',
        'type': 'text',
        'default': '',
        'label': 'Center Subtitle',
        'help': 'Small text below center value (e.g. "Star rating", "Overall grade").',
        'show_when': {'multi_ring_show_center': True, 'gauge_style': 'multi_ring'},
    },
    {
        'flag': 'multi_ring_show_legend',
        'type': 'boolean',
        'default': True,
        'label': 'Show Legend',
        'help': 'Display metric names and values below the rings.',
        'show_when': {'gauge_style': 'multi_ring'},
    },
    {
        'flag': 'multi_ring_arc_width',
        'type': 'number',
        'default': 10,
        'label': 'Arc Width (px)',
        'help': 'Width of each ring arc in pixels.',
        'show_when': {'gauge_style': 'multi_ring'},
    },
]


# ── KPI Card Flags ──────────────────────────────────────────────────────────

KPI_FLAGS = [
    {
        'flag': 'kpi_style',
        'type': 'select',
        'default': 'stat_card',
        'label': 'KPI Style',
        'help': 'Visual variant for the KPI card.',
        'options': [
            {'value': 'stat_card', 'label': 'Stat Card (trend badge)'},
            {'value': 'sparkline', 'label': 'Stat Card + Sparkline'},
            {'value': 'progress', 'label': 'Progress Bar (target)'},
            {'value': 'mini_gauge', 'label': 'Mini Gauge Ring'},
            {'value': 'comparison', 'label': 'Comparison (vs prior)'},
            {'value': 'rag_status', 'label': 'RAG Status Card'},
            {'value': 'strip', 'label': 'KPI Strip (compact)'},
        ],
    },
]


# ── Common Flags (all chart types) ──────────────────────────────────────────

# ── Map Chart Flags ──────────────────────────────────────────────────────────

MAP_FLAGS = [
    {
        'flag': 'map_style',
        'type': 'select',
        'default': 'light',
        'label': 'Map Style',
        'help': 'Base map tile style.',
        'options': [
            {'value': 'light', 'label': 'Light'},
            {'value': 'streets', 'label': 'Streets'},
            {'value': 'dark', 'label': 'Dark'},
            {'value': 'satellite', 'label': 'Satellite'},
        ],
    },
    {
        'flag': 'marker_mode',
        'type': 'select',
        'default': 'points',
        'label': 'Marker Mode',
        'help': 'How data is visualized on the map.',
        'options': [
            {'value': 'points', 'label': 'Point Markers'},
            {'value': 'bubble', 'label': 'Bubble (size by metric)'},
            {'value': 'choropleth', 'label': 'Choropleth (region fill)'},
            {'value': 'heatmap', 'label': 'Heatmap (density)'},
        ],
    },
    {
        'flag': 'clustering',
        'type': 'boolean',
        'default': True,
        'label': 'Cluster Nearby Markers',
        'help': 'Group nearby markers into clusters. Only applies to point/bubble modes.',
        'show_when': {'marker_mode': 'points'},
    },
    {
        'flag': 'default_zoom',
        'type': 'number',
        'default': 4,
        'label': 'Default Zoom Level',
        'help': '1 = world, 4 = country, 8 = state, 12 = city, 15 = street.',
    },
    {
        'flag': 'default_center_lat',
        'type': 'number',
        'default': 39.83,
        'label': 'Default Center Latitude',
        'help': 'Initial map center latitude. Default: geographic center of US.',
    },
    {
        'flag': 'default_center_lng',
        'type': 'number',
        'default': -98.58,
        'label': 'Default Center Longitude',
        'help': 'Initial map center longitude. Default: geographic center of US.',
    },
    {
        'flag': 'popup_columns',
        'type': 'text',
        'default': '',
        'label': 'Popup Info Columns',
        'help': 'Comma-separated SQL column names to show in marker/region popup on click.',
    },
    {
        'flag': 'color_column',
        'type': 'text',
        'default': '',
        'label': 'Color-By Column',
        'help': 'SQL column whose distinct values determine marker color (e.g., brand_name, category).',
    },
    {
        'flag': 'size_column',
        'type': 'text',
        'default': '',
        'label': 'Size-By Column',
        'help': 'SQL column whose numeric value scales marker size (bubble mode).',
        'show_when': {'marker_mode': 'bubble'},
    },
    {
        'flag': 'show_radius',
        'type': 'boolean',
        'default': False,
        'label': 'Show Radius Overlay',
        'help': 'Draw a circle radius around the selected marker.',
    },
    {
        'flag': 'radius_miles',
        'type': 'number',
        'default': 25,
        'label': 'Radius (miles)',
        'show_when': {'show_radius': True},
    },
    {
        'flag': 'click_filter_column',
        'type': 'text',
        'default': '',
        'label': 'Click → Filter Column',
        'help': 'SQL column value to push as filter when a marker/region is clicked.',
    },
    {
        'flag': 'click_filter_param',
        'type': 'text',
        'default': '',
        'label': 'Click → Filter Param',
        'help': 'Dashboard filter param name to set on click (e.g., hha_ccn, hha_state).',
    },
    # ── Choropleth-specific flags ──
    {
        'flag': 'choropleth_level',
        'type': 'select',
        'default': 'state',
        'label': 'Choropleth Level',
        'help': 'Geographic boundary level for region fills.',
        'show_when': {'marker_mode': 'choropleth'},
        'options': [
            {'value': 'state', 'label': 'State'},
            {'value': 'county', 'label': 'County'},
        ],
    },
    {
        'flag': 'choropleth_join_column',
        'type': 'text',
        'default': '',
        'label': 'Region Join Column',
        'help': 'SQL column with state abbreviation (e.g., FL) or county FIPS code to join to GeoJSON.',
        'show_when': {'marker_mode': 'choropleth'},
    },
    {
        'flag': 'choropleth_metric_column',
        'type': 'text',
        'default': '',
        'label': 'Metric Column',
        'help': 'SQL column with numeric value for color graduation.',
        'show_when': {'marker_mode': 'choropleth'},
    },
    {
        'flag': 'choropleth_color_scale',
        'type': 'select',
        'default': 'sequential',
        'label': 'Color Scale',
        'show_when': {'marker_mode': 'choropleth'},
        'options': [
            {'value': 'sequential', 'label': 'Sequential (light → dark)'},
            {'value': 'diverging', 'label': 'Diverging (red → blue)'},
        ],
    },
    {
        'flag': 'choropleth_ranges',
        'type': 'text',
        'default': '',
        'label': 'Range Breakpoints',
        'help': 'Comma-separated values for color breaks (e.g., 1,10,100,1000,10000). Auto-calculated if empty.',
        'show_when': {'marker_mode': 'choropleth'},
    },
    # ── Heatmap-specific flags ──
    {
        'flag': 'heatmap_weight_column',
        'type': 'text',
        'default': '',
        'label': 'Weight Column',
        'help': 'Optional numeric column to weight heatmap intensity (e.g., admissions). Uniform weight if empty.',
        'show_when': {'marker_mode': 'heatmap'},
    },
    {
        'flag': 'heatmap_radius',
        'type': 'number',
        'default': 20,
        'label': 'Heatmap Radius (px)',
        'help': 'Radius of influence for each point in pixels.',
        'show_when': {'marker_mode': 'heatmap'},
    },
    # ── Brand Layers panel flags ──
    {
        'flag': 'panel_label',
        'type': 'text',
        'default': 'Brand Layers',
        'label': 'Panel Label',
        'help': 'Header text for the layers panel (e.g., "Brand Layers", "Hospital Systems", "Lab Networks").',
    },
    {
        'flag': 'brand_category_column',
        'type': 'text',
        'default': '',
        'label': 'Brand Category Column',
        'help': 'SQL column for category tag under brand name (e.g., "Home Health", "native", "turnaround").',
    },
    {
        'flag': 'brand_summary_columns',
        'type': 'text',
        'default': '',
        'label': 'Brand Summary Metrics',
        'help': 'Comma-separated metric columns shown on each brand card (e.g., hha_admits,revenue).',
    },
    {
        'flag': 'search_columns',
        'type': 'text',
        'default': '',
        'label': 'Searchable Columns',
        'help': 'Comma-separated SQL columns searchable in the brand search (e.g., hha_name,hha_brand_name). Falls back to all columns if empty.',
    },
    # ── Search Radius panel flags ──
    {
        'flag': 'radius_min',
        'type': 'number',
        'default': 5,
        'label': 'Radius Min (miles)',
        'help': 'Minimum value for the radius slider.',
    },
    {
        'flag': 'radius_max',
        'type': 'number',
        'default': 200,
        'label': 'Radius Max (miles)',
        'help': 'Maximum value for the radius slider.',
    },
    {
        'flag': 'radius_default',
        'type': 'number',
        'default': 25,
        'label': 'Radius Default (miles)',
        'help': 'Default radius slider value on page load.',
    },
]


# ── Scatter Chart Flags ──────────────────────────────────────────────────────
#
# Scatter widgets support bubble sizing, color-by-series, and rich HTML
# tooltips entirely through these flags + echart_override formatter strings
# (no per-app code).
#
# Value-array index map for tooltip formatters:
#   {c0} = x_col          (X-axis)
#   {c1} = y_col          (Y-axis)
#   {c2} = size_col       (only if size_column is set)
#   {c3+} = extra cols    (every other SELECT column, in SELECT order)

SCATTER_FLAGS = [
    {
        'flag': 'size_column',
        'type': 'text',
        'default': '',
        'label': 'Bubble Size Column',
        'help': 'Optional. Name of the SQL column whose value sets each '
                'point\'s bubble size (e.g. "total_visits"). Leave empty '
                'for fixed-size dots. Convention: you can also pass the '
                'size column as the 2nd entry in y_columns.',
    },
    {
        'flag': 'bubble_min_px',
        'type': 'number',
        'default': 6,
        'label': 'Bubble Min Size (px)',
        'help': 'Minimum bubble diameter in pixels. Smaller = denser plot. '
                'Used when Bubble Size Column is set.',
    },
    {
        'flag': 'bubble_max_px',
        'type': 'number',
        'default': 40,
        'label': 'Bubble Max Size (px)',
        'help': 'Maximum bubble diameter in pixels. Larger = more dramatic '
                'size differences. Used when Bubble Size Column is set.',
    },
    {
        'flag': 'default_symbol_size',
        'type': 'number',
        'default': 8,
        'label': 'Default Dot Size (px)',
        'help': 'Bubble size when no Bubble Size Column is configured. '
                'Applies uniformly to all points.',
    },

    # ── Axis labels & formatting (no JSON paste needed for these) ───────
    {
        'flag': 'x_axis_title',
        'type': 'text',
        'default': '',
        'label': 'X-Axis Title',
        'help': 'Display name for the X-axis (e.g. "Therapy Share of Visits"). '
                'Leave blank to hide the axis name.',
    },
    {
        'flag': 'y_axis_title',
        'type': 'text',
        'default': '',
        'label': 'Y-Axis Title',
        'help': 'Display name for the Y-axis (e.g. "Stability Factor"). '
                'Leave blank to hide.',
    },
    {
        'flag': 'x_axis_format',
        'type': 'select',
        'default': 'auto',
        'label': 'X-Axis Tick Format',
        'help': 'How X-axis tick labels are formatted. "Percent" appends '
                '"%" to each tick (e.g. 50%, 60%).',
        'options': [
            {'value': 'auto',    'label': 'Auto (default)'},
            {'value': 'percent', 'label': 'Percent (50%)'},
        ],
    },
    {
        'flag': 'y_axis_format',
        'type': 'select',
        'default': 'auto',
        'label': 'Y-Axis Tick Format',
        'help': 'How Y-axis tick labels are formatted.',
        'options': [
            {'value': 'auto',    'label': 'Auto (default)'},
            {'value': 'percent', 'label': 'Percent (50%)'},
        ],
    },
    {
        'flag': 'x_axis_min',
        'type': 'number',
        'default': None,
        'label': 'X-Axis Min',
        'help': 'Minimum X-axis value. Leave blank for auto-fit.',
    },
    {
        'flag': 'x_axis_max',
        'type': 'number',
        'default': None,
        'label': 'X-Axis Max',
        'help': 'Maximum X-axis value. Leave blank for auto-fit. '
                'For percent metrics, set to 100.',
    },
    {
        'flag': 'y_axis_min',
        'type': 'number',
        'default': None,
        'label': 'Y-Axis Min',
        'help': 'Minimum Y-axis value. Leave blank for auto-fit.',
    },
    {
        'flag': 'y_axis_max',
        'type': 'number',
        'default': None,
        'label': 'Y-Axis Max',
        'help': 'Maximum Y-axis value. Leave blank for auto-fit. '
                'For 0–1 metrics like Stability Factor, set to 1.',
    },

    # ── Tooltip configuration (no JSON paste needed for label + 1 metric) ─
    #
    # For a bigger header card with multiple metrics + body table, see the
    # parked Rich Tooltip work. These three flags cover the common case
    # of "show the entity name + one key metric on hover".
    {
        'flag': 'tooltip_label_column',
        'type': 'text',
        'default': '',
        'label': 'Tooltip — Label Column',
        'help': 'SQL column whose value appears as the tooltip\'s bold '
                'header line (e.g. "hha_label"). Leave blank to use the '
                'ECharts default tooltip.',
    },
    {
        'flag': 'tooltip_metric_column',
        'type': 'text',
        'default': '',
        'label': 'Tooltip — Metric Column',
        'help': 'SQL column to display as a labeled metric below the '
                'header line (e.g. "total_visits"). Leave blank for a '
                'label-only tooltip.',
    },
    {
        'flag': 'tooltip_metric_label',
        'type': 'text',
        'default': '',
        'label': 'Tooltip — Metric Display Label',
        'help': 'Display label for the metric (e.g. "Total Visits"). '
                'Leave blank to use the column name.',
        'show_when': {'tooltip_metric_column': '__not_null__'},
    },
    {
        'flag': 'tooltip_metric_format',
        'type': 'select',
        'default': 'comma',
        'label': 'Tooltip — Metric Format',
        'help': 'How the metric value is formatted in the tooltip.',
        'options': [
            {'value': 'comma',   'label': 'Comma (1,234)'},
            {'value': 'percent', 'label': 'Percent (42.9%)'},
            {'value': 'decimal', 'label': 'Decimal (12.34)'},
            {'value': 'plain',   'label': 'Plain'},
        ],
        'show_when': {'tooltip_metric_column': '__not_null__'},
    },
    {
        'flag': 'tooltip_extras',
        'type': 'text',
        'default': '',
        'label': 'Tooltip — Extra Rows',
        'help': 'Additional SQL columns to show as extra rows beneath the '
                'metric. Comma-separated list. Each entry can be either:\n'
                '  • "column_name"            (uses column name as label)\n'
                '  • "column_name:Display"    (custom label after colon)\n'
                'Example: "fac_state:State, fac_county:County, brand_name:Brand"',
    },

    # ── Click action: clean drill-down value ──────────────────────────
    #
    # Lets the admin pick a SQL column whose value is sent when a user
    # clicks a bubble. Without this, the click handler falls back to
    # the data point's `name` (the multi-line tooltip text) or its
    # value array — neither is a clean key for filtering. Pair this
    # with the widget-level "Click Action = Go to another page" config
    # in the wizard's Filters & Actions step.
    {
        'flag': 'click_value_column',
        'type': 'text',
        'default': '',
        'label': 'Click Value Column',
        'help': 'Optional. Name of the SQL column whose raw value is '
                'sent as the URL filter param when a user clicks a '
                'bubble. For an HHA scatter with click→Profile, set '
                'this to "ccn_hha". Leave blank to use the default '
                '(name field, which is usually the tooltip text — '
                'rarely useful as a filter value).',
    },
]


COMMON_FLAGS = [
    {
        'flag': 'display_density',
        'type': 'select',
        'default': 'standard',
        'label': 'Display Density',
        'help': 'Controls card padding, font sizes, and spacing. '
                'Standard: generous (default). Compact: tighter (~120px). '
                'Dense: minimal (~80px, competitor-style).',
        'options': [
            {'value': 'standard', 'label': 'Standard (spacious)'},
            {'value': 'compact', 'label': 'Compact (tighter)'},
            {'value': 'dense', 'label': 'Dense (minimal)'},
        ],
    },
    {
        'flag': 'card_padding',
        'type': 'select',
        'default': 'standard',
        'label': 'Card Padding',
        'help': 'Controls inner padding around widget content. '
                'None: edge-to-edge (0px). Tight: minimal (4px). '
                'Standard: default. Spacious: generous (24px).',
        'options': [
            {'value': 'none', 'label': 'None (edge-to-edge)'},
            {'value': 'tight', 'label': 'Tight (4px)'},
            {'value': 'standard', 'label': 'Standard (default)'},
            {'value': 'spacious', 'label': 'Spacious (24px)'},
        ],
    },
]


# ── Registry ─────────────────────────────────────────────────────────────────
# Add new chart families here as they are implemented.
# COMMON_FLAGS are prepended to every chart type's flags.

# ─ Sankey flags ──────────────────────────────────────────────────────────────
# Sankey diagrams display flows between nodes with colored bands.
# Column mapping (Sankey v1 is Custom SQL only):
#   x_column      = source node
#   series_column = target node
#   y_columns[0]  = numeric value
#   y_columns[1]  = optional category column (drives per-link color)
SANKEY_FLAGS = [
    {
        'flag': 'sankey_orient', 'type': 'select', 'default': 'horizontal',
        'label': 'Flow Direction',
        'options': [
            {'value': 'horizontal', 'label': 'Left to right'},
            {'value': 'vertical',   'label': 'Top to bottom'},
        ],
        'help': 'Layout direction for the Sankey flow.',
    },
    {
        'flag': 'sankey_node_align', 'type': 'select', 'default': 'justify',
        'label': 'Node Alignment',
        'options': [
            {'value': 'left',    'label': 'Left'},
            {'value': 'right',   'label': 'Right'},
            {'value': 'justify', 'label': 'Justify (default)'},
        ],
        'help': 'Where to position node labels along the flow direction.',
    },
    {'flag': 'sankey_node_gap',       'type': 'number', 'default': 8,
     'label': 'Node Gap (px)',
     'help': 'Vertical spacing between nodes in the same column.'},
    {'flag': 'sankey_node_width',     'type': 'number', 'default': 20,
     'label': 'Node Width (px)',
     'help': 'Width of each node rectangle.'},
    {'flag': 'sankey_link_opacity',   'type': 'number', 'default': 0.5,
     'label': 'Link Opacity',
     'help': '0 (transparent) to 1 (solid). Per-link category colors inherit this.'},
    {'flag': 'sankey_link_curveness', 'type': 'number', 'default': 0.5,
     'label': 'Link Curveness',
     'help': '0 (straight lines) to 1 (curved bands).'},
    {
        'flag': 'sankey_label_position', 'type': 'select', 'default': 'right',
        'label': 'Label Position',
        'options': [
            {'value': 'left',   'label': 'Left'},
            {'value': 'right',  'label': 'Right'},
            {'value': 'top',    'label': 'Top'},
            {'value': 'bottom', 'label': 'Bottom'},
            {'value': 'inside', 'label': 'Inside node'},
        ],
        'help': 'Where to render the node label relative to the node rectangle.',
    },
]

# ─ Key Takeaways flags ───────────────────────────────────────────────────────
# Multi-row narrative list. Column mapping: x_column = takeaway text,
# series_column = severity. SQL row order is the display order.
KEY_TAKEAWAYS_FLAGS = [
    {
        'flag': 'max_items',
        'type': 'number',
        'default': 4,
        'label': 'Max Items',
        'help': 'Maximum number of takeaway rows to display. '
                'Allowed range is 1–10 (default 4). SQL row order is preserved.',
    },
]

CHART_FLAGS = {
    'bar': COMMON_FLAGS + BAR_FLAGS,
    'pie': COMMON_FLAGS + PIE_FLAGS,
    'donut': COMMON_FLAGS + DONUT_FLAGS,
    'line': COMMON_FLAGS + LINE_FLAGS,
    'gauge': COMMON_FLAGS + GAUGE_FLAGS,
    'kpi': COMMON_FLAGS + KPI_FLAGS,
    'status_kpi': COMMON_FLAGS + KPI_FLAGS,
    'scatter': COMMON_FLAGS + SCATTER_FLAGS,
    'sankey': COMMON_FLAGS + SANKEY_FLAGS,
    'sankey_member_flow': COMMON_FLAGS,
    'key_takeaways': COMMON_FLAGS + KEY_TAKEAWAYS_FLAGS,
    # 'radar': RADAR_FLAGS,   # future
    'map': MAP_FLAGS,
}


def get_flags_for_chart(chart_type):
    """Return the flag schema for a chart type.

    Returns an empty list for chart types without defined flags,
    allowing the builder to render with no chart-specific options.
    """
    return CHART_FLAGS.get(chart_type, [])
