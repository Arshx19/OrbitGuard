import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { conjunctions as defaultConjunctions, stats as defaultStats, riskLevelMeta, levelFromScore } from '../data/mockData'
import { getStats, listConjunctions } from '../api/orbitguard'
import StatCard from '../components/StatCard'
import OrbitViewer from '../components/OrbitViewer'
import ConjunctionList from '../components/ConjunctionList'
import RiskTimeline from '../components/RiskTimeline'

export default function Dashboard() {
  const [statsData, setStatsData] = useState(defaultStats)
  const [conjunctionsList, setConjunctionsList] = useState(defaultConjunctions)
  const [selectedId, setSelectedId] = useState(defaultConjunctions[0].id)

  useEffect(() => {
    async function loadLiveData() {
      try {
        const liveStats = await getStats()
        if (liveStats) {
          setStatsData(prev => ({
            ...prev,
            objectsTracked: liveStats.objectsTracked || prev.objectsTracked,
            activeConjunctions: liveStats.activeConjunctions || prev.activeConjunctions,
            highRiskEvents: liveStats.highRiskEvents || prev.highRiskEvents,
            satellitesMonitored: liveStats.satellitesMonitored || prev.satellitesMonitored
          }))
        }
        
        const liveConj = await listConjunctions()
        if (liveConj && liveConj.length > 0) {
          setConjunctionsList(liveConj)
          if (liveConj[0] && liveConj[0].id) {
            setSelectedId(liveConj[0].id)
          }
        }
      } catch (e) {
        console.warn("Using fallback data for Dashboard:", e)
      }
    }
    loadLiveData()
  }, [])

  const selected = conjunctionsList.find((c) => String(c.id) === String(selectedId)) || conjunctionsList[0]
  const level = levelFromScore(selected?.riskScore || 94)
  const meta = riskLevelMeta[level] || riskLevelMeta.critical

  return (
    <div className="space-y-5 p-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Objects tracked" value={statsData.objectsTracked ? statsData.objectsTracked.toLocaleString() : '12,482'} delta={statsData.objectsTrackedDelta || '+2.6%'} accent="text-risk-green" />
        <StatCard label="Active conjunctions" value={statsData.activeConjunctions || 37} delta={statsData.activeConjunctionsDelta || '+6.1%'} accent="text-risk-amber" />
        <StatCard label="High-risk events" value={statsData.highRiskEvents || 5} delta={statsData.highRiskEventsDelta || '+25%'} accent="text-risk-critical" />
        <StatCard label="Satellites monitored" value={statsData.satellitesMonitored ? statsData.satellitesMonitored.toLocaleString() : '1,284'} delta={statsData.satellitesMonitoredDelta || '+0.3%'} accent="text-risk-green" />
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
              <dd className="font-mono" style={{ color: meta.color }}>{selected.probability ? selected.probability.toExponential(1) : '8.7e-2'}</dd>
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

      <ConjunctionList conjunctions={conjunctionsList} selectedId={selectedId} onSelect={setSelectedId} />

      <RiskTimeline timeline={selected.timeline} />
    </div>
  )
}
