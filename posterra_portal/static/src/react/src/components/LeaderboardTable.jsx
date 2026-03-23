/**
 * LeaderboardTable — presentational component for ranked tables.
 *
 * Renders the same HTML structure as the former QWeb leaderboard_table template,
 * using identical CSS classes.  Handles the "You" row highlight and pinned row
 * separator (when a "You" row falls outside the max_rows limit).
 */
export default function LeaderboardTable({ data }) {
  const { name_header = 'HHA Name', headers = [], rows = [] } = data || {}
  if (rows.length === 0) return null

  return (
    <div className="pv-ml-table-wrap">
      <table className="pv-ml-table">
        <thead>
          <tr>
            <th className="pv-ml-th-rank">#</th>
            <th className="pv-ml-th-name">{name_header}</th>
            {headers.map((hdr, i) => (
              <th key={i} className="pv-ml-th-num">{hdr}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const isPinned = row.pinned
            return (
              <tr
                key={i}
                className={
                  (row.is_you ? 'pv-ml-you-row' : '') +
                  (isPinned ? ' pv-ml-pinned-row' : '')
                }
              >
                <td className="pv-ml-rank">
                  {isPinned ? '...' : row.rank}
                </td>
                <td className="pv-ml-name">
                  {row.name}
                  {row.is_you && <span className="pv-ml-you-badge ms-1">You</span>}
                  {row.sub_name && (
                    <div className="pv-ml-sub">{row.sub_name}</div>
                  )}
                </td>
                {(row.metrics || []).map((metric, j) => (
                  <td key={j} className={`pv-ml-num ${metric.color_class || ''}`}>
                    {metric.val}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
