import { useState, useEffect, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { conjunctions as defaultConjunctions, getConjunction } from '../data/mockData'
import { analyzeRisk, levelOf } from '../api/orbitguard'
import SimulationBadge from '../components/SimulationBadge'
import RiskScore from '../components/RiskScore'
import RiskFactors from '../components/RiskFactors'
import RiskTimeline from '../components/RiskTimeline'

export default function RiskAnalysis() {
  const { id } = useParams()
  const defaultC = getConjunction(id) || defaultConjunctions[0]
  const [c, setC] = useState(defaultC)

  useEffect(() => {
    async function loadRiskData() {
      try {
        // analyzeRisk returns the full event plus its risk analysis, already in
        // the page's shape: one request instead of two.
        const riskRes = await analyzeRisk(id)
        if (riskRes) setC(prev => ({ ...prev, ...riskRes }))
      } catch (e) {
        console.warn("Error loading risk analysis live data:", e)
      }
    }
    loadRiskData()
  }, [id])

  const topFactors = useMemo(
    () => [...(c.factors || [])]
      .filter((f) => (f.direction ?? 'raises') === 'raises')
      .sort((a, b) => b.pct - a.pct)
      .slice(0, 2)
      .map((f) => f.label.toLowerCase()),
    [c]
  )

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
        {c.explanation ? (
          c.explanation
        ) : (
          <>
            Risk is high because the <strong className="text-ink">{topFactors[0] || 'minimum separation'}</strong> and{' '}
            <strong className="text-ink">{topFactors[1] || 'relative velocity'}</strong> factors dominate the score, TCA is in{' '}
            {c.tcaIn || '42 min'}, and the orbital geometry is {(c.geometry || 'crossing').toLowerCase()}. SGP4 propagation and orbital
            mechanics drive these calculations — the model prioritizes and explains the result, it does not
            replace them.
          </>
        )}
      </div>

      <RiskTimeline timeline={c.timeline} />

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
