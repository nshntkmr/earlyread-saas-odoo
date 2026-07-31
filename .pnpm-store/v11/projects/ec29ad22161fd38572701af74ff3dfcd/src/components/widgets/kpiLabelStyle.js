export function buildKpiLabelStyle(data = {}, baseStyle = undefined) {
  const style = { ...(baseStyle || {}) }

  if (data.kpi_label_font_size) {
    style.fontSize = Number(data.kpi_label_font_size)
  }
  if (data.kpi_label_color) {
    style.color = data.kpi_label_color
  }
  if (data.kpi_label_bold) {
    style.fontWeight = 700
  }
  if (data.kpi_label_italic) {
    style.fontStyle = 'italic'
  }

  return Object.keys(style).length ? style : undefined
}
