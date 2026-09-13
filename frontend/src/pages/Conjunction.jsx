import { useState, useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { conjunctions as defaultConjunctions, riskLevelMeta } from '../data/mockData'
import { getConjunctionById, levelOf, formatProbability } from '../api/orbitguard'
import SimulationBadge from '../components/SimulationBadge'
import OrbitViewer from '../components/OrbitViewer'
import ExplainMyDecision from '../components/ExplainMyDecision'

export default function Conjunction() {
  const { id } = useParams()
  const [selected, setSelected] = useState(defaultConjunctions[0])

  useEffect(() => {
    async function loadDetail() {
      try {
        // getConjunctionById already returns the page's shape, live or mock.
        const item = await getConjunctionById(id)
        if (item) setSelected(item)
      } catch (e) {
        console.warn("Error loading conjunction detail:", e)
      }
    }
    loadDetail()
    const interval = setInterval(loadDetail, 5000)
    const handleRefreshed = () => loadDetail()
    window.addEventListener('orbitguard-data-refreshed', handleRefreshed)

    return () => {
      clearInterval(interval)
      window.removeEventListener('orbitguard-data-refreshed', handleRefreshed)
    }
  }, [id])


  const meta = riskLevelMeta[levelOf(selected)] || riskLevelMeta.green

  return (
    <div className="space-y-5 p-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-ink-faint">CONJUNCTION ANALYSIS</div>
          <h1 className="mt-1 text-xl font-semibold text-ink">
            {selected.primary} ↔ {selected.secondary}
          </h1>
        </div>

        <span
          className="rounded px-2 py-1 text-[10px] font-semibold tracking-wide"
          style={{
            color: meta.color,
            backgroundColor: `${meta.color}1A`,
            border: `1px solid ${meta.color}40`,
          }}
        >
          {meta.label.toUpperCase()}
        </span>
        <SimulationBadge show={selected.simulated} className="ml-2" />
      </div>

      {/* Orbit + Details */}
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1fr_320px]">
        <div className="panel h-[420px] overflow-hidden">
          <OrbitViewer conjunction={selected} />
        </div>

        <div className="panel p-4">
          <div className="mb-4 text-xs font-medium tracking-wide text-ink-muted">
            CLOSE APPROACH DATA
          </div>

          <dl className="space-y-4 text-xs">
            <div className="flex justify-between">
              <dt className="text-ink-faint">Conjunction ID</dt>
              <dd className="font-mono text-ink">{selected.id}</dd>
            </div>

            <div className="flex justify-between">
              <dt className="text-ink-faint">Time of closest approach</dt>
              <dd className="font-mono text-ink">{selected.tcaIn}</dd>
            </div>

            <div className="flex justify-between">
              <dt className="text-ink-faint">Minimum separation</dt>
              <dd className="font-mono text-ink">
                {selected.minDistanceM} m
              </dd>
            </div>

            <div className="flex justify-between">
              <dt className="text-ink-faint">Relative velocity</dt>
              <dd className="font-mono text-ink">
                {selected.relVelocityKms} km/s
              </dd>
            </div>

            <div className="flex justify-between">
              <dt className="text-ink-faint">Collision probability</dt>
              <dd
                className="font-mono"
                style={{ color: meta.color }}
              >
                {formatProbability(selected.probability)}
              </dd>
            </div>

            <div className="flex justify-between">
              <dt className="text-ink-faint">Risk score</dt>
              <dd
                className="font-mono font-semibold"
                style={{ color: meta.color }}
              >
                {selected.riskScore}
              </dd>
            </div>
          </dl>

          <div className="mt-6 flex flex-col gap-2">
            <Link
              to={`/risk/${selected.id}`}
              className="rounded-md border border-signal/40 bg-signal/10 py-2 text-center text-xs font-medium text-signal transition hover:bg-signal/20"
            >
              Analyze Risk
            </Link>

            <Link
              to={`/maneuver/${selected.id}`}
              className="rounded-md border border-line py-2 text-center text-xs font-medium text-ink-muted transition hover:bg-void-500"
            >
              Find Safe Maneuver
            </Link>

            <Link
              to="/"
              className="rounded-md border border-line py-2 text-center text-xs font-medium text-ink-faint transition hover:bg-void-500"
            >
              ← Back to Dashboard
            </Link>
          </div>
        </div>
      </div>

      {/* Explanation */}
      <div className="panel p-4">
        <div className="mb-2 text-xs font-medium tracking-wide text-ink-muted">
          CONJUNCTION SUMMARY
        </div>

        <p className="text-xs leading-6 text-ink-faint">
          {selected.primary} and {selected.secondary} are predicted to have
          a close approach with a minimum separation of{' '}
          <span className="font-mono text-ink">
            {selected.minDistanceM} m
          </span>
          . The estimated relative velocity is{' '}
          <span className="font-mono text-ink">
            {selected.relVelocityKms} km/s
          </span>
          .
        </p>
      </div>

      {/* AI Risk Copilot Decision Intelligence */}
      <ExplainMyDecision conjunctionId={selected.id} className="mt-6" />
    </div>
  )
}