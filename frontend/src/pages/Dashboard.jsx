import { useState } from 'react'
import { Link } from 'react-router-dom'
import { riskLevelMeta } from '../data/mockData'
import { formatProbability, getStats, listConjunctions, levelOf, isLive } from '../api/orbitguard'
import { useApi, Loading } from '../api/useApi'
import StatCard from '../components/StatCard'
import OrbitViewer from '../components/OrbitViewer'
import ConjunctionList from '../components/ConjunctionList'
import RiskTimeline from '../components/RiskTimeline'
import SimulationBadge from '../components/SimulationBadge'

export default function Dashboard() {
  const statsQuery = useApi(getStats, [])
  const listQuery = useApi(listConjunctions, [])
  const [selectedId, setSelectedId] = useState(null)

  if (statsQuery.loading || listQuery.loading) {
    return <Loading label="Screening the catalog…" />
  }

  const stats = statsQuery.data
  const conjunctions = listQuery.data ?? []
  if (!conjunctions.length) {
    return <div className="p-5 text-xs text-ink-faint">No upcoming conjunctions in the screening window.</div>
  }

  const selected = conjunctions.find((c) => c.id === selectedId) ?? conjunctions[0]
  const level = levelOf(selected)
  const meta = riskLevelMeta[level]

  return (
    <div className="space-y-5 p-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Objects tracked" value={stats.objectsTracked.toLocaleString()} delta={stats.objectsTrackedDelta} accent="text-risk-green" />
        <StatCard label="Active conjunctions" value={stats.activeConjunctions} delta={stats.activeConjunctionsDelta} accent="text-risk-amber" />
        <StatCard label="High-risk events" value={stats.highRiskEvents} delta={stats.highRiskEventsDelta} accent="text-risk-critical" />
        <StatCard label="Satellites monitored" value={stats.satellitesMonitored.toLocaleString()} delta={stats.satellitesMonitoredDelta} accent="text-risk-green" />
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1fr_320px]">
        <div className="panel h-[380px] overflow-hidden">
          <OrbitViewer conjunction={selected} />
        </div>

        <div className="panel flex flex-col p-4">
          <div className="mb-3 flex items-center justify-between">
            <span
              className="rounded px-2 py-0.5 text-[10px] font-semibold tracking-wide"
              style={{ color: meta.color, backgroundColor: `${meta.color}1A`, border: `1px solid ${meta.color}40` }}
            >
              {meta.label.toUpperCase()} CONJUNCTION
            </span>
            <SimulationBadge show={selected.simulated} />
            <span className="font-mono text-[11px] text-ink-faint">{selected.id}</span>
          </div>
          <div className="text-sm font-medium text-ink">
            {selected.primary} <span className="text-ink-faint">↔</span> {selected.secondary}
          </div>

          <dl className="mt-4 space-y-3 text-xs">
            <div className="flex justify-between">
              <dt className="text-ink-faint">Time of closest approach</dt>
              <dd className="font-mono text-ink">in {selected.tcaIn}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-faint">Minimum separation</dt>
              <dd className="font-mono text-ink">{selected.minDistanceM} m</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-faint">Collision probability</dt>
              <dd className="font-mono" style={{ color: meta.color }}>{formatProbability(selected.probability)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-faint">Relative velocity</dt>
              <dd className="font-mono text-ink">{selected.relVelocityKms} km/s</dd>
            </div>
          </dl>

          <div className="mt-auto flex flex-col gap-2 pt-4">
            <Link
              to={`/risk/${selected.id}`}
              className="rounded-md border border-signal/40 bg-signal/10 py-2 text-center text-xs font-medium text-signal transition hover:bg-signal/20"
            >
              Analyze risk
            </Link>
            <Link
              to={`/maneuver/${selected.id}`}
              className="rounded-md border border-line py-2 text-center text-xs font-medium text-ink-muted transition hover:bg-void-500"
            >
              Find safe maneuver
            </Link>
          </div>
        </div>
      </div>

      <ConjunctionList conjunctions={conjunctions} selectedId={selected.id} onSelect={setSelectedId} />

      <div className="text-right font-mono text-[10px] text-ink-faint">
        {conjunctions.live
          ? 'LIVE · screened from public TLE data'
          : isLive()
            ? 'MOCK DATA · backend configured but unreachable'
            : 'MOCK DATA · backend not connected'}
      </div>

      <RiskTimeline timeline={selected.timeline} />
    </div>
  )
}
