import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { conjunctions as defaultConjunctions, getConjunction, riskLevelMeta } from '../data/mockData'
import { getConjunctionById, levelOf, formatProbability } from '../api/orbitguard'
import OrbitViewer from '../components/OrbitViewer'
import { useSettings, formatDistanceM } from '../context/SettingsContext'
import ExplainMyDecision from '../components/ExplainMyDecision'

export default function Conjunction() {
  const { id } = useParams()
  const [selected, setSelected] = useState(getConjunction(id) || defaultConjunctions[0])
  const { units } = useSettings()

  useEffect(() => {
    async function loadDetail() {
      try {
        const item = await getConjunctionById(id)
        if (item) setSelected(item)
      } catch (e) {
        console.warn('Error loading conjunction detail:', e)
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
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-ink-faint">Conjunction {selected.id}</div>
          <h1 className="mt-1 font-display text-lg font-semibold text-ink">
            {selected.primary} <span className="text-ink-faint">vs</span> {selected.secondary}
          </h1>
        </div>
        <span
          className="rounded px-3 py-1 text-xs font-semibold tracking-wide"
          style={{ color: meta.color, backgroundColor: `${meta.color}1A`, border: `1px solid ${meta.color}40` }}
        >
          Risk {selected.riskScore} / 100 · {meta.label.toUpperCase()}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_320px]">
        <div className="panel h-[360px] overflow-hidden">
          <OrbitViewer conjunction={selected} />
        </div>

        <div className="panel p-5">
          <div className="mb-3 text-xs font-medium tracking-wide text-ink-muted">EVENT METRICS</div>
          <dl className="space-y-3 text-xs">
            <Row label="Minimum separation" value={formatDistanceM(selected.minDistanceM, units)} />
            <Row label="Relative velocity" value={`${selected.relVelocityKms} km/s`} />
            <Row label="Time to closest approach" value={selected.tcaIn} />
            <Row label="Orbital geometry" value={selected.geometry} />
            <Row label="Uncertainty" value={selected.uncertainty} />
            <Row label="Collision probability" value={formatProbability(selected.probability)} />
          </dl>

          <div className="mt-6 flex flex-col gap-2">
            <Link
              to={`/risk/${selected.id}`}
              className="rounded-md border border-signal/40 bg-signal/10 py-2 text-center text-xs font-medium text-signal transition hover:bg-signal/20"
            >
              Analyze risk →
            </Link>
            <Link
              to={`/maneuver/${selected.id}`}
              className="rounded-md border border-line py-2 text-center text-xs font-medium text-ink-muted transition hover:bg-void-500"
            >
              Find safe maneuver →
            </Link>
          </div>
        </div>
      </div>

      {/* AI Risk Copilot Decision Intelligence */}
      <ExplainMyDecision conjunctionId={selected.id} className="mt-6" />
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between border-b border-line pb-2 last:border-0 last:pb-0">
      <dt className="text-ink-faint">{label}</dt>
      <dd className="font-mono text-ink">{value}</dd>
    </div>
  )
}
