import { useState } from 'react'
import { Link } from 'react-router-dom'
import { riskLevelMeta, levelFromScore } from '../data/mockData'
import { useSettings, formatDistanceM } from '../context/SettingsContext'

function RiskBadge({ score }) {
  const level = levelFromScore(score)
  const meta = riskLevelMeta[level]
  return (
    <span
      className="rounded px-2 py-0.5 text-[10px] font-semibold tracking-wide"
      style={{ color: meta.color, backgroundColor: `${meta.color}1A`, border: `1px solid ${meta.color}40` }}
    >
      {meta.label.toUpperCase()}
    </span>
  )
}

export default function ConjunctionList({ conjunctions, selectedId, onSelect }) {
  const { units } = useSettings()
  const [filterMode, setFilterMode] = useState('today') // 'today' | 'all'

  // Filter conjunctions for today's data (TCA within 24 hours or today's date)
  const filteredConjunctions = conjunctions.filter((c) => {
    if (filterMode === 'all') return true
    if (c.tcaHours != null) return c.tcaHours <= 24.0
    // Check if TCA date is today
    const tcaDate = new Date(c.tca)
    const now = new Date()
    return (
      tcaDate.getUTCFullYear() === now.getUTCFullYear() &&
      tcaDate.getUTCMonth() === now.getUTCMonth() &&
      tcaDate.getUTCDate() === now.getUTCDate()
    )
  })

  // Fallback to all conjunctions if today's filtered set is empty
  const displayList = filteredConjunctions.length > 0 ? filteredConjunctions : conjunctions

  return (
    <div className="panel overflow-hidden">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-line px-4 py-2.5 gap-2">
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium tracking-wide text-ink-muted">ACTIVE CONJUNCTIONS</span>
          <div className="flex bg-void-900 rounded p-0.5 border border-line/60">
            <button
              onClick={() => setFilterMode('today')}
              className={`px-2.5 py-1 text-[11px] font-medium rounded transition-colors ${
                filterMode === 'today'
                  ? 'bg-signal/20 text-signal font-semibold'
                  : 'text-ink-muted hover:text-ink'
              }`}
            >
              📅 Today's Events (24h)
            </button>
            <button
              onClick={() => setFilterMode('all')}
              className={`px-2.5 py-1 text-[11px] font-medium rounded transition-colors ${
                filterMode === 'all'
                  ? 'bg-signal/20 text-signal font-semibold'
                  : 'text-ink-muted hover:text-ink'
              }`}
            >
              🌐 All Events
            </button>
          </div>
        </div>

        <span className="font-mono text-[11px] text-ink-faint">
          {displayList.length} {filterMode === 'today' ? "today's events" : 'tracked'}
        </span>
      </div>

      <table className="w-full text-left text-xs">
        <thead>
          <tr className="text-[10px] uppercase tracking-wide text-ink-faint">
            <th className="px-4 py-2 font-normal">Primary</th>
            <th className="px-4 py-2 font-normal">Secondary</th>
            <th className="px-4 py-2 font-normal">TCA</th>
            <th className="px-4 py-2 font-normal">Miss dist.</th>
            <th className="px-4 py-2 font-normal">Rel. vel.</th>
            <th className="px-4 py-2 font-normal">Probability</th>
            <th className="px-4 py-2 font-normal">Risk</th>
            <th className="px-4 py-2 font-normal" />
          </tr>
        </thead>
        <tbody>
          {displayList.map((c) => (
            <tr
              key={c.id}
              onClick={() => onSelect?.(c.id)}
              className={`cursor-pointer border-t border-line transition hover:bg-void-600 ${
                selectedId === c.id ? 'bg-void-600' : ''
              }`}
            >
              <td className="px-4 py-2.5 font-mono text-signal">{c.primary}</td>
              <td className="px-4 py-2.5 font-mono text-risk-critical/80">{c.secondary}</td>
              <td className="px-4 py-2.5 font-mono text-ink-muted">
                {c.tcaIn || `${new Date(c.tca).toISOString().slice(11, 19)} UTC`}
              </td>
              <td className="px-4 py-2.5 font-mono text-ink-muted">{formatDistanceM(c.minDistanceM, units)}</td>
              <td className="px-4 py-2.5 font-mono text-ink-muted">{c.relVelocityKms} km/s</td>
              <td className="px-4 py-2.5 font-mono text-ink-muted">
                {typeof c.probability === 'number' ? c.probability.toExponential(1) : c.probability}
              </td>
              <td className="px-4 py-2.5">
                <RiskBadge score={c.riskScore} />
              </td>
              <td className="px-4 py-2.5">
                <Link to={`/conjunction/${c.id}`} className="text-[11px] text-signal hover:underline">
                  Review →
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
