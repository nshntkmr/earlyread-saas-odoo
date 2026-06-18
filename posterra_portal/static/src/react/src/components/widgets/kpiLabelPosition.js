/**
 * Resolve where a KPI card's optional label renders relative to the value.
 *
 * Driven by the opt-in visual_config key `kpi_label_position`, emitted by the
 * backend as `data.kpi_label_position`. When the value is empty/'default' (the
 * default for every existing card), the renderer's CURRENT placement is
 * preserved — `defaultAbove` encodes that per-renderer/per-layout default, so
 * no existing KPI card changes unless an admin explicitly opts in.
 *
 * @param {string} pos          '' | 'default' | 'above_value' | 'below_value' | 'hidden'
 * @param {boolean} defaultAbove this renderer/layout's current placement
 *                               (true = label currently rendered above the value)
 * @returns {{ show: boolean, above: boolean, below: boolean }}
 *          `above`/`below` are mutually exclusive, so the label element renders
 *          in exactly one slot (or not at all when `show` is false).
 */
export function resolveLabelPlacement(pos, defaultAbove) {
  if (pos === 'hidden')      return { show: false, above: false, below: false }
  if (pos === 'above_value') return { show: true,  above: true,  below: false }
  if (pos === 'below_value') return { show: true,  above: false, below: true }
  // 'default' | '' | unknown → preserve current per-renderer placement
  return { show: true, above: defaultAbove, below: !defaultAbove }
}
