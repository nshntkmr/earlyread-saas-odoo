// Canonical v1 defaults + enums for attribute_grid / metric_list — JS mirror
// of dashboard_builder/services/widget_config_defaults.py. The two sides are
// held identical by the golden fixtures (dashboard_builder/schemas/
// golden_fixtures) — change one, run BOTH fixture suites.

export const VERSION = 1

export const DATA_SHAPES = ['single_record', 'attribute_rows']
export const DENSITIES = ['comfortable', 'compact']
export const LAYOUTS = ['stacked', 'inline']
export const FIELD_LAYOUTS = ['inherit', ...LAYOUTS]
export const EMPHASES = ['normal', 'strong']
export const LEADING_VISUAL_MODES = ['none', 'icon', 'initials']
export const FIELD_ICON_MODES = ['none', 'static', 'column']
export const ATTR_FORMAT_TYPES = ['text', 'integer', 'decimal', 'percent',
  'currency', 'date', 'datetime', 'phone']
export const LINK_TYPES = ['none', 'url', 'tel', 'mailto', 'internal']
export const METRIC_FORMAT_TYPES = ['decimal', 'number', 'percent']
export const DIRECTIONS = ['lower_is_better', 'higher_is_better', 'neutral', 'manual']
export const LEGEND_MODES = ['auto', 'semantic', 'per_metric', 'hidden']

export const DEFAULT_STYLES = {
  info:    { foreground: '#087ad8', background: '#e7f1fb' },
  success: { foreground: '#059669', background: '#ecfdf5' },
  warning: { foreground: '#d97706', background: '#fef3c7' },
  danger:  { foreground: '#dc2626', background: '#fee2e2' },
}

export const NEUTRAL_STATUS = {
  key: '__neutral__', label: '', color: '#6b7280', background: '#f3f4f6',
}

export const ATTRIBUTE_GRID_DEFAULTS = {
  version: VERSION,
  data_shape: 'single_record',
  columns: 2,
  density: 'comfortable',
  default_layout: 'stacked',
  empty_text: 'No information available',
  default_style_key: '',
  styles: DEFAULT_STYLES,
  leading_visual: {
    mode: 'none', source_column: '', icon_key: '',
    foreground: '#059669', background: '#ecfdf5',
  },
  fields: [],
  row_mapping: {
    item_key_column: '', label_column: '', value_column: '',
    secondary_value_column: '', icon_key_column: '', style_key_column: '',
    row_order_column: '', column_start_column: '', column_span_column: '',
    layout_column: '', emphasis_column: '', divider_before_column: '',
    format_type_column: '', decimals_column: '', display_multiplier_column: '',
    prefix_column: '', suffix_column: '', null_text_column: '',
    link_type_column: '', link_value_column: '', is_visible_column: '',
  },
  row_icon: { allowed_keys: [], fallback_key: '' },
  row_default_format: {
    type: 'text', decimals: 0, display_multiplier: 1,
    prefix: '', suffix: '', null_text: '—',
  },
  row_link: { type: 'none', template: '', new_tab: false },
}

export const FIELD_ITEM_DEFAULTS = {
  key: '', label: '', value_column: '',
  icon: { mode: 'none', key: '', column: '', allowed_keys: [], fallback_key: '' },
  span: 1, layout: 'inherit', emphasis: 'normal', divider_before: false,
  format: { type: 'text', decimals: 0, display_multiplier: 1,
            prefix: '', suffix: '', null_text: '—' },
  link: { type: 'none', template: '', new_tab: false },
  style_key: '',
}

export const METRIC_LIST_DEFAULTS = {
  version: VERSION,
  mapping: {
    key_column: '', label_column: '', value_column: '', status_column: '',
    detail_column: '', icon_column: '', scale_min_column: '',
    scale_max_column: '', format_type_column: '', decimals_column: '',
    display_multiplier_column: '', prefix_column: '', suffix_column: '',
    direction_column: '',
  },
  icon: { allowed_keys: [], fallback_key: '' },
  scale: { min: 0, max: 1, clamp: true },
  value_format: { type: 'decimal', decimals: 3, display_multiplier: 1,
                  prefix: '', suffix: '' },
  progress: { show: true, height: 10, track_color: '#eef2f7' },
  detail_label: '',
  max_items: 20,
  default_direction: 'neutral',
  metric_settings: [],
  status_rules: [],
  legend: { mode: 'auto', position: 'bottom', include_threshold_text: true },
  empty_text: 'No metrics available',
}

export const STATUS_RULE_DEFAULTS = {
  key: '', applies_to: [], match_values: [], label: '',
  color: '#6b7280', background: '#f3f4f6', range: null, show_in_legend: true,
}

export const RANGE_DEFAULTS = {
  min: null, min_inclusive: true, max: null, max_inclusive: false,
}

export const METRIC_SETTING_DEFAULTS = { metric_key: '', direction: 'neutral' }
