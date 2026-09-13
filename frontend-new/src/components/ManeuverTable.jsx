import { useSettings, formatDistanceKm } from '../context/SettingsContext'

function formatBurnCode(code) {
  if (!code || typeof code !== 'string') return ''
  const parts = code.split('@')
  if (parts.length === 2) {
    return `${parts[0]} m/s @ T-${parts[1]}h`
  }
  return code
}

export default function ManeuverTable({ candidates, selectedId, onSelect }) {
  const { units } = useSettings()
  if (!candidates?.length) {
    return (
      <div className="panel p-5 text-xs text-ink-faint">
        No maneuver candidates generated — this event does not require an avoidance maneuver.
      </div>
    )
  }

  return (
    <div className="panel overflow-hidden">
      <div className="border-b border-line px-4 py-2.5 text-xs font-medium tracking-wide text-ink-muted">
        MANEUVER CANDIDATES
      </div>
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="text-[10px] uppercase tracking-wide text-ink-faint">
            <th className="px-4 py-2 font-normal">Candidate</th>
            <th className="px-4 py-2 font-normal">Δv</th>
            <th className="px-4 py-2 font-normal">Direction</th>
            <th className="px-4 py-2 font-normal">New separation</th>
            <th className="px-4 py-2 font-normal">New risks</th>
            <th className="px-4 py-2 font-normal">Status</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c, idx) => {
            const safe = c.status === 'SAFE'
            const isSelected = selectedId === c.id
            const candidateNum = `#${String(idx + 1).padStart(2, '0')}`
            const rawCode = typeof c.id === 'string' && c.id.includes('@') ? c.id : null
            const formattedTag = rawCode ? formatBurnCode(rawCode) : null

            return (
              <tr
                key={c.id || idx}
                onClick={() => onSelect?.(c.id)}
                className={`cursor-pointer border-t border-line transition hover:bg-void-600 ${
                  isSelected ? 'bg-void-600' : ''
                }`}
              >
                <td className="px-4 py-2.5 text-ink">
                  <span className="font-mono font-semibold text-signal">{candidateNum}</span>
                  {formattedTag && (
                    <span className="ml-2.5 inline-block font-sans text-[11px] text-ink-muted bg-void-700/80 px-2 py-0.5 rounded border border-line/40">
                      {formattedTag}
                    </span>
                  )}
                </td>
                <td className="px-4 py-2.5 font-mono text-ink-muted">{c.deltaV.toFixed(2)} m/s</td>
                <td className="px-4 py-2.5 text-ink-muted">{c.direction}</td>
                <td className="px-4 py-2.5 font-mono text-ink-muted">{formatDistanceKm(c.newSeparationKm, units)}</td>
                <td className="px-4 py-2.5 text-ink-faint">{c.newRisk}</td>
                <td className="px-4 py-2.5">
                  <span
                    className="rounded px-2 py-0.5 text-[10px] font-semibold"
                    style={
                      safe
                        ? { color: '#3ED598', backgroundColor: '#3ED59820', border: '1px solid #3ED59850' }
                        : { color: '#F0475A', backgroundColor: '#F0475A20', border: '1px solid #F0475A50' }
                    }
                  >
                    {c.status}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
