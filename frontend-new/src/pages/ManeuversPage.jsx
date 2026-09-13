import { Link } from 'react-router-dom'
import { conjunctions, riskLevelMeta, levelFromScore } from '../data/mockData'

export default function ManeuversPage() {
  const eligible = conjunctions.filter((c) => c.maneuverCandidates.length > 0)
  const stable = conjunctions.filter((c) => c.maneuverCandidates.length === 0)

  return (
    <div className="space-y-5 p-5">
      <div>
        <h1 className="font-display text-lg font-semibold text-ink">Maneuvers</h1>
        <p className="mt-1 text-xs text-ink-faint">
          Events that need a candidate Δv search. Pick one to simulate and validate a response.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {eligible.map((c) => {
          const meta = riskLevelMeta[levelFromScore(c.riskScore)]
          const best = c.maneuverCandidates.find((m) => m.status === 'SAFE')
          return (
            <div key={c.id} className="panel p-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="font-mono text-sm text-ink">
                  {c.primary} <span className="text-ink-faint">↔</span> {c.secondary}
                </span>
                <span
                  className="rounded px-2 py-0.5 text-[10px] font-semibold"
                  style={{ color: meta.color, backgroundColor: `${meta.color}1A`, border: `1px solid ${meta.color}40` }}
                >
                  {meta.label.toUpperCase()}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-y-1 text-xs">
                <span className="text-ink-faint">Risk score</span>
                <span className="text-right font-mono text-ink">{c.riskScore} / 100</span>
                <span className="text-ink-faint">Candidates found</span>
                <span className="text-right font-mono text-ink">{c.maneuverCandidates.length}</span>
                <span className="text-ink-faint">Best safe Δv</span>
                <span className="text-right font-mono text-risk-green">
                  {best ? `${best.deltaV.toFixed(2)} m/s` : 'None yet'}
                </span>
              </div>
              <Link
                to={`/maneuver/${c.id}`}
                className="mt-4 block rounded-md border border-signal/40 bg-signal/10 py-2 text-center text-xs font-medium text-signal transition hover:bg-signal/20"
              >
                Simulate maneuver →
              </Link>
            </div>
          )
        })}
      </div>

      {stable.length > 0 && (
        <div>
          <div className="mb-2 text-xs font-medium tracking-wide text-ink-faint">NO MANEUVER REQUIRED</div>
          <div className="panel divide-y divide-line">
            {stable.map((c) => (
              <div key={c.id} className="flex items-center justify-between px-4 py-2.5 text-xs">
                <span className="font-mono text-ink-muted">
                  {c.primary} ↔ {c.secondary}
                </span>
                <span className="text-ink-faint">Risk {c.riskScore} / 100 — within safe margin</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
