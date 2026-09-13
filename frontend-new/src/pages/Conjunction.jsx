import { useParams, Link, Navigate } from 'react-router-dom'
import { getConjunction, riskLevelMeta, levelFromScore } from '../data/mockData'
import OrbitViewer from '../components/OrbitViewer'
import { useSettings, formatDistanceM } from '../context/SettingsContext'

export default function Conjunction() {
  const { id } = useParams()
  const c = getConjunction(id)
  const { units } = useSettings()
  if (!c) return <Navigate to="/" replace />

  const level = levelFromScore(c.riskScore)
  const meta = riskLevelMeta[level]

  return (
    <div className="space-y-5 p-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-ink-faint">Conjunction {c.id}</div>
          <h1 className="mt-1 font-display text-lg font-semibold text-ink">
            {c.primary} <span className="text-ink-faint">vs</span> {c.secondary}
          </h1>
        </div>
        <span
          className="rounded px-3 py-1 text-xs font-semibold tracking-wide"
          style={{ color: meta.color, backgroundColor: `${meta.color}1A`, border: `1px solid ${meta.color}40` }}
        >
          Risk {c.riskScore} / 100 · {meta.label.toUpperCase()}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_320px]">
        <div className="panel h-[360px] overflow-hidden">
          <OrbitViewer conjunction={c} />
        </div>

        <div className="panel p-5">
          <div className="mb-3 text-xs font-medium tracking-wide text-ink-muted">EVENT METRICS</div>
          <dl className="space-y-3 text-xs">
            <Row label="Minimum separation" value={formatDistanceM(c.minDistanceM, units)} />
            <Row label="Relative velocity" value={`${c.relVelocityKms} km/s`} />
            <Row label="Time to closest approach" value={c.tcaIn} />
            <Row label="Orbital geometry" value={c.geometry} />
            <Row label="Uncertainty" value={c.uncertainty} />
            <Row label="Collision probability" value={c.probability.toExponential(1)} />
          </dl>

          <div className="mt-6 flex flex-col gap-2">
            <Link
              to={`/risk/${c.id}`}
              className="rounded-md border border-signal/40 bg-signal/10 py-2 text-center text-xs font-medium text-signal transition hover:bg-signal/20"
            >
              Analyze risk →
            </Link>
            <Link
              to={`/maneuver/${c.id}`}
              className="rounded-md border border-line py-2 text-center text-xs font-medium text-ink-muted transition hover:bg-void-500"
            >
              Find safe maneuver →
            </Link>
          </div>
        </div>
      </div>
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
