# -*- coding: utf-8 -*-
"""Canonical version-1 defaults + enums for attribute_grid / metric_list.

SINGLE SOURCE OF TRUTH on the Python side. The JS mirror lives in
``posterra_portal/static/src/shared/grid-utils/configDefaults.js``; the two are
held identical by the golden fixtures under ``dashboard_builder/schemas/
golden_fixtures/`` — change one, run both fixture suites.

Pure data — no ORM, no I/O, importable without Odoo.

Defaults are TRULY empty (``fields: []``, ``status_rules: []``, all mappings
``""``): a fresh widget carries no thresholds, no fields, no domain assumptions.
Fully-populated example objects live in the fixtures, never here.
"""

VERSION = 1

# ── Shared enums ───────────────────────────────────────────────────────────────
DATA_SHAPES = ('single_record', 'attribute_rows')
DENSITIES = ('comfortable', 'compact')
LAYOUTS = ('stacked', 'inline')
FIELD_LAYOUTS = ('inherit',) + LAYOUTS
EMPHASES = ('normal', 'strong')
LEADING_VISUAL_MODES = ('none', 'icon', 'initials')   # distinct from icon.mode
FIELD_ICON_MODES = ('none', 'static', 'column')       # distinct from leading_visual
ATTR_FORMAT_TYPES = ('text', 'integer', 'decimal', 'percent', 'currency',
                     'date', 'datetime', 'phone')
LINK_TYPES = ('none', 'url', 'tel', 'mailto', 'internal')
METRIC_FORMAT_TYPES = ('decimal', 'number', 'percent')
DIRECTIONS = ('lower_is_better', 'higher_is_better', 'neutral', 'manual')
LEGEND_MODES = ('auto', 'semantic', 'per_metric', 'hidden')
LEGEND_POSITIONS = ('bottom',)

# ── Numeric limits ─────────────────────────────────────────────────────────────
COLUMNS_MIN, COLUMNS_MAX = 1, 8
FIELDS_MIN, FIELDS_MAX = 1, 40
DECIMALS_MIN, DECIMALS_MAX = 0, 6
MAX_ITEMS_MIN, MAX_ITEMS_MAX = 1, 100
PROGRESS_HEIGHT_MIN, PROGRESS_HEIGHT_MAX = 2, 32
# Defensive row caps (render-side; SQL should carry its own LIMIT)
ATTRIBUTE_ROWS_CAP = 200
METRIC_ROWS_CAP = 500

# ── String caps / patterns ─────────────────────────────────────────────────────
KEY_PATTERN = r'^[a-z0-9_]{1,64}$'            # field keys / metric keys
STYLE_KEY_PATTERN = r'^[a-z0-9_-]{1,32}$'
ICON_KEY_PATTERN = r'^[a-z0-9_-]{1,64}$'      # dashboard.icon registry keys
COLOR_PATTERN = (r'^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{4}'
                 r'|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$')
LABEL_MAX = 120
TEXT_MAX = 200        # empty_text / detail_label / prefix / suffix / null_text
TEMPLATE_MAX = 1000   # link templates

DEFAULT_STYLES = {
    'info':    {'foreground': '#087ad8', 'background': '#e7f1fb'},
    'success': {'foreground': '#059669', 'background': '#ecfdf5'},
    'warning': {'foreground': '#d97706', 'background': '#fef3c7'},
    'danger':  {'foreground': '#dc2626', 'background': '#fee2e2'},
}

NEUTRAL_STATUS = {
    'key': '__neutral__',
    'label': '',
    'color': '#6b7280',
    'background': '#f3f4f6',
}

ATTRIBUTE_GRID_DEFAULTS = {
    'version': VERSION,
    'data_shape': 'single_record',
    'columns': 2,
    'density': 'comfortable',
    'default_layout': 'stacked',
    'empty_text': 'No information available',
    'default_style_key': '',
    'styles': DEFAULT_STYLES,
    'leading_visual': {
        'mode': 'none',
        'source_column': '',
        'icon_key': '',
        'foreground': '#059669',
        'background': '#ecfdf5',
    },
    'fields': [],
    'row_mapping': {
        'item_key_column': '',
        'label_column': '',
        'value_column': '',
        'secondary_value_column': '',
        'icon_key_column': '',
        'style_key_column': '',
        'row_order_column': '',
        'column_start_column': '',
        'column_span_column': '',
        'layout_column': '',
        'emphasis_column': '',
        'divider_before_column': '',
        'format_type_column': '',
        'decimals_column': '',
        'display_multiplier_column': '',
        'prefix_column': '',
        'suffix_column': '',
        'null_text_column': '',
        'link_type_column': '',
        'link_value_column': '',
        'is_visible_column': '',
    },
    'row_icon': {'allowed_keys': [], 'fallback_key': ''},
    'row_default_format': {
        'type': 'text', 'decimals': 0, 'display_multiplier': 1,
        'prefix': '', 'suffix': '', 'null_text': '—',
    },
    'row_link': {'type': 'none', 'template': '', 'new_tab': False},
}

# Per-item defaults for single_record fields[] entries.
FIELD_ITEM_DEFAULTS = {
    'key': '',
    'label': '',
    'value_column': '',
    'icon': {'mode': 'none', 'key': '', 'column': '',
             'allowed_keys': [], 'fallback_key': ''},
    'span': 1,
    'layout': 'inherit',
    'emphasis': 'normal',
    'divider_before': False,
    'format': {'type': 'text', 'decimals': 0, 'display_multiplier': 1,
               'prefix': '', 'suffix': '', 'null_text': '—'},
    'link': {'type': 'none', 'template': '', 'new_tab': False},
    'style_key': '',
}

METRIC_LIST_DEFAULTS = {
    'version': VERSION,
    'mapping': {
        'key_column': '',
        'label_column': '',
        'value_column': '',
        'status_column': '',
        'detail_column': '',
        'icon_column': '',
        'scale_min_column': '',
        'scale_max_column': '',
        'format_type_column': '',
        'decimals_column': '',
        'display_multiplier_column': '',
        'prefix_column': '',
        'suffix_column': '',
        'direction_column': '',
    },
    'icon': {'allowed_keys': [], 'fallback_key': ''},
    'scale': {'min': 0, 'max': 1, 'clamp': True},
    'value_format': {'type': 'decimal', 'decimals': 3, 'display_multiplier': 1,
                     'prefix': '', 'suffix': ''},
    'progress': {'show': True, 'height': 10, 'track_color': '#eef2f7'},
    'detail_label': '',
    'max_items': 20,
    'default_direction': 'neutral',
    'metric_settings': [],
    'status_rules': [],
    'legend': {'mode': 'auto', 'position': 'bottom',
               'include_threshold_text': True},
    'empty_text': 'No metrics available',
}

STATUS_RULE_DEFAULTS = {
    'key': '',
    'applies_to': [],
    'match_values': [],
    'label': '',
    'color': '#6b7280',
    'background': '#f3f4f6',
    'range': None,
    'show_in_legend': True,
}

RANGE_DEFAULTS = {
    'min': None, 'min_inclusive': True,
    'max': None, 'max_inclusive': False,
}

METRIC_SETTING_DEFAULTS = {
    'metric_key': '',
    'direction': 'neutral',
}
