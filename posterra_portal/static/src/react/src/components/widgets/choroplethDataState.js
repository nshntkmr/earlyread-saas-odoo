/**
 * Decide whether an opt-in choropleth should render an all-zero selection with
 * its no-data color. Values passed here are already the renderer's numeric
 * region values; NULL/NaN regions have been excluded.
 *
 * Keeping this separate from NULL handling preserves the map contract:
 * suppressed/no-data values remain NULL, while genuine zeros remain available
 * to the tooltip and only affect the fill when the entire numeric selection is
 * zero and the widget explicitly enables the behavior.
 */
export function shouldUseAllZeroNoData(enabled, numericValues) {
  return enabled === true
    && Array.isArray(numericValues)
    && numericValues.length > 0
    && numericValues.every(value => value === 0)
}
