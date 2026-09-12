import { useState, useEffect, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { conjunctions as defaultConjunctions, getConjunction } from '../data/mockData'
import { analyzeRisk, getConjunctionById } from '../api/orbitguard'
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
        const detail = await getConjunctionById(id)
        const riskRes = await analyzeRisk(id)

        setC(prev => ({
          ...prev,
          id: detail?.id || detail?.conjunction_id || id,
          primary: detail?.satellite1_name || prev.primary,
          secondary: detail?.satellite2_name || prev.secondary,
          riskScore: riskRes?.riskScore ?? detail?.risk_score ?? prev.riskScore,
          factors: riskRes?.factors && riskRes.factors.length > 0
            ? riskRes.factors.map(f => ({ label: f.factor || f.label, pct: f.contribution_percentage || f.pct }))
            : prev.factors,
          explanation: riskRes?.explanation || prev.explanation,
          timeline: riskRes?.timeline && riskRes.timeline.length > 0 ? riskRes.timeline : prev.timeline
        }))
      } catch (e) {
        console.warn("Error loading risk analysis live data:", e)
      }
    }
    loadRiskData()
  }, [id])

  const topFactors = useMemo(
    () => [...(c.factors || [])].sort((a, b) => b.pct - a.pct).slice(0, 2).map((f) => f.label.toLowerCase()),
    [c]
  )

  return (
    <div className="space-y-5 p-5">
      <div>
        <div className="text-[11px] uppercase tracking-wide text-ink-faint">Risk analysis · {c.id}</div>
        <h1 className="mt-1 font-display text-lg font-semibold text-ink">
          Why {c.primary} ↔ {c.secondary} is flagged
        </h1>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[220px_1fr]">
        <RiskScore score={c.riskScore} />
        <RiskFactors factors={c.factors} />
      </div>

      <div className="panel border-l-2 border-l-signal p-4 text-sm text-ink-muted">
        Risk is high because the <strong className="text-ink">{topFactors[0] || 'minimum separation'}</strong> and{' '}
        <strong className="text-ink">{topFactors[1] || 'relative velocity'}</strong> factors dominate the score, TCA is in{' '}
        {c.tcaIn || '42 min'}, and the orbital geometry is {(c.geometry || 'crossing').toLowerCase()}. SGP4 propagation and orbital
        mechanics drive these calculations — the model prioritizes and explains the result, it does not
        replace them.
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
