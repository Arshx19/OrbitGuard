import { useParams, Link, Navigate } from 'react-router-dom'
import { analyzeRisk, levelOf } from '../api/orbitguard'
import { useApi, Loading } from '../api/useApi'
import RiskScore from '../components/RiskScore'
import RiskFactors from '../components/RiskFactors'
import RiskTimeline from '../components/RiskTimeline'
import SimulationBadge from '../components/SimulationBadge'

export default function RiskAnalysis() {
  const { id } = useParams()
  const { data: c, loading } = useApi(() => analyzeRisk(id), [id])

  if (loading) return <Loading label="Computing collision probability…" />
  if (!c) return <Navigate to="/" replace />

  // Live data carries a narrative written by the risk engine from the same
  // counterfactuals that produce the factor bars. Mock data does not, so build
  // the original summary from its fields instead.
  const topFactors = [...(c.factors ?? [])]
    .filter((f) => (f.direction ?? 'raises') === 'raises')
    .sort((a, b) => b.pct - a.pct)
    .slice(0, 2)
    .map((f) => f.label.toLowerCase())

  return (
    <div className="space-y-5 p-5">
      <div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-ink-faint">
          Risk analysis · {c.id}
          <SimulationBadge show={c.simulated} />
        </div>
        <h1 className="mt-1 font-display text-lg font-semibold text-ink">
          Why {c.primary} ↔ {c.secondary} is flagged
        </h1>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[220px_1fr]">
        <RiskScore score={c.riskScore} level={levelOf(c)} probability={c.probability} />
        <RiskFactors factors={c.factors} />
      </div>

      {c.uncertaintySource && (
        <div className="-mt-2 text-[11px] text-ink-faint">
          Position uncertainty: {c.uncertaintySource}
          {c.uncertaintyExtrapolated && (
            <span className="ml-1 text-risk-amber">
              · element sets older than the training data, so error growth is extrapolated
            </span>
          )}
        </div>
      )}

      <div className="panel border-l-2 border-l-signal p-4 text-sm text-ink-muted">
        {c.narrative ? (
          c.narrative
        ) : (
          <>
            Risk is high because the <strong className="text-ink">{topFactors[0]}</strong>
            {topFactors[1] && (
              <>
                {' '}and <strong className="text-ink">{topFactors[1]}</strong>
              </>
            )}{' '}
            factors dominate the score, TCA is in {c.tcaIn}
            {c.geometry && <>, and the orbital geometry is {c.geometry.toLowerCase()}</>}. SGP4
            propagation and orbital mechanics drive these calculations — the model prioritizes and
            explains the result, it does not replace them.
          </>
        )}
      </div>

      {c.timeline && <RiskTimeline timeline={c.timeline} />}

      <div className="flex justify-end">
        <Link
          to={`/maneuver/${c.id}`}
          className="rounded-md border border-signal/40 bg-signal/10 px-4 py-2 text-xs font-medium text-signal transition hover:bg-signal/20"
        >
          Find safe maneuver →
        </Link>
      </div>
    </div>
  )
}
