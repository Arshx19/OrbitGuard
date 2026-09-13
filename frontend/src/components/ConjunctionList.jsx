import { Link } from 'react-router-dom'
import { riskLevelMeta } from '../data/mockData'
import { formatProbability, levelOf } from '../api/orbitguard'
import SimulationBadge from './SimulationBadge'

// Severity comes from the backend (keyed to collision probability) when live,
// and is bucketed from the score only for mock data. `score || 94` used to turn
// a genuine score of 0 into a CRITICAL badge.
function RiskBadge({ conjunction }) {
  const meta = riskLevelMeta[levelOf(conjunction)] || riskLevelMeta.green
  return (
    <span
      className="rounded px-2 py-0.5 text-[10px] font-semibold tracking-wide"
      style={{ color: meta.color, backgroundColor: `${meta.color}1A`, border: `1px solid ${meta.color}40` }}
    >
      {meta.label.toUpperCase()}
    </span>
  )
}

function formatTCA(tca) {
  if (!tca) return '04:12:00 UTC'
  try {
    const d = new Date(tca)
    if (!isNaN(d.getTime())) {
      return d.toISOString().slice(11, 19) + ' UTC'
    }
  } catch (e) {}
  return String(tca)
}

export default function ConjunctionList({ conjunctions = [], selectedId, onSelect }) {
  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <span className="text-xs font-medium tracking-wide text-ink-muted">ACTIVE CONJUNCTIONS</span>
        <span className="font-mono text-[11px] text-ink-faint">{conjunctions.length} tracked</span>
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
          {conjunctions.map((c) => (
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
                {formatTCA(c.tca)}
              </td>
              <td className="px-4 py-2.5 font-mono text-ink-muted">{c.minDistanceM} m</td>
              <td className="px-4 py-2.5 font-mono text-ink-muted">{c.relVelocityKms} km/s</td>
              <td className="px-4 py-2.5 font-mono text-ink-muted">{typeof c.probability === 'number' ? formatProbability(c.probability) : '—'}</td>
              <td className="px-4 py-2.5">
                <div className="flex items-center gap-1.5">
                  <RiskBadge conjunction={c} />
                  <SimulationBadge show={c.simulated} />
                </div>
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
