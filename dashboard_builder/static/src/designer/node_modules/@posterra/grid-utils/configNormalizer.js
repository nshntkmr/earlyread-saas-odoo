// Normalize raw attribute_grid / metric_list configs to canonical v1 form.
// JS mirror of dashboard_builder/services/widget_config_normalizer.py — the
// golden fixtures assert the two produce STRUCTURALLY IDENTICAL canonical
// objects. Same contract: unknown keys dropped; known scalars keep the user
// value verbatim (validation is a separate concern); dicts merge recursively;
// lists replace wholesale with per-item normalization; `styles` merges user
// keys INTO the seeded defaults; `range: null` stays null.

import {
  ATTRIBUTE_GRID_DEFAULTS, FIELD_ITEM_DEFAULTS, METRIC_LIST_DEFAULTS,
  STATUS_RULE_DEFAULTS, RANGE_DEFAULTS, METRIC_SETTING_DEFAULTS,
  DEFAULT_STYLES,
} from './configDefaults.js'

const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v)
const deep = (v) => (v === undefined ? v : JSON.parse(JSON.stringify(v)))

function mergeKnown(defaults, raw) {
  const out = deep(defaults)
  if (!isObj(raw)) return out
  for (const key of Object.keys(defaults)) {
    if (!(key in raw)) continue
    const dflt = defaults[key]
    const val = raw[key]
    if (isObj(dflt) && isObj(val)) out[key] = mergeKnown(dflt, val)
    else out[key] = deep(val)
  }
  return out
}

function normalizeList(items, itemDefaults, itemFn) {
  if (!Array.isArray(items)) return []
  return items.map((item) => {
    let norm = mergeKnown(itemDefaults, isObj(item) ? item : {})
    if (itemFn) norm = itemFn(norm, item)
    return norm
  })
}

export function normalizeAttributeGrid(raw) {
  const src = isObj(raw) ? raw : {}
  const cfg = mergeKnown(ATTRIBUTE_GRID_DEFAULTS, src)
  const styles = deep(DEFAULT_STYLES)
  if (isObj(src.styles)) {
    for (const [k, v] of Object.entries(src.styles)) {
      if (isObj(v)) {
        styles[k] = {
          foreground: v.foreground !== undefined ? v.foreground : '',
          background: v.background !== undefined ? v.background : '',
        }
      }
    }
  }
  cfg.styles = styles
  cfg.fields = normalizeList(src.fields, FIELD_ITEM_DEFAULTS)
  return cfg
}

function normalizeRule(norm, rawItem) {
  const rawRange = isObj(rawItem) ? rawItem.range : null
  norm.range = (rawRange === null || rawRange === undefined)
    ? null
    : mergeKnown(RANGE_DEFAULTS, isObj(rawRange) ? rawRange : {})
  if (!Array.isArray(norm.applies_to)) norm.applies_to = []
  if (!Array.isArray(norm.match_values)) norm.match_values = []
  return norm
}

export function normalizeMetricList(raw) {
  const src = isObj(raw) ? raw : {}
  const cfg = mergeKnown(METRIC_LIST_DEFAULTS, src)
  cfg.status_rules = normalizeList(src.status_rules, STATUS_RULE_DEFAULTS, normalizeRule)
  cfg.metric_settings = normalizeList(src.metric_settings, METRIC_SETTING_DEFAULTS)
  if (!Array.isArray(cfg.icon.allowed_keys)) cfg.icon.allowed_keys = []
  return cfg
}
