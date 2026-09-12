import { Link } from 'react-router-dom'
import { riskLevelMeta, levelFromScore } from '../data/mockData'

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
                {new Date(c.tca).toISOString().slice(11, 19)} UTC
              </td>
              <td className="px-4 py-2.5 font-mono text-ink-muted">{c.minDistanceM} m</td>
              <td className="px-4 py-2.5 font-mono text-ink-muted">{c.relVelocityKms} km/s</td>
              <td className="px-4 py-2.5 font-mono text-ink-muted">{c.probability.toExponential(1)}</td>
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
