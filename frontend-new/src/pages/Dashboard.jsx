import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { conjunctions as defaultConjunctions, stats as defaultStats, riskLevelMeta } from '../data/mockData'
import { getStats, listConjunctions, levelOf, formatProbability } from '../api/orbitguard'
import SimulationBadge from '../components/SimulationBadge'
import StatCard from '../components/StatCard'
import OrbitViewer from '../components/OrbitViewer'
import ConjunctionList from '../components/ConjunctionList'
import RiskTimeline from '../components/RiskTimeline'
import ExplainMyDecision from '../components/ExplainMyDecision'
import OrbitVisualization from '../components/OrbitVisualization'

export default function Dashboard() {
  const [statsData, setStatsData] = useState(defaultStats)
  const [conjunctionsList, setConjunctionsList] = useState(defaultConjunctions)
  const [selectedId, setSelectedId] = useState(defaultConjunctions[0]?.id)
  const [source, setSource] = useState('mock')
  const [activeTab, setActiveTab] = useState('overview') // 'overview' | 'globe'

  useEffect(() => {
    async function loadLiveData() {
      try {
        const liveStats = await getStats()
        if (liveStats) setStatsData(liveStats)

        const liveConj = await listConjunctions()
        if (liveConj && liveConj.length > 0) {
          setConjunctionsList(liveConj)
          setSource(liveConj.source || 'live')
          if (!selectedId) setSelectedId(liveConj[0].id)
        }
      } catch (e) {
        console.warn('Using fallback data for Dashboard:', e)
      }
    }

    loadLiveData()
    const interval = setInterval(loadLiveData, 5000)
    const handleRefreshed = () => loadLiveData()
    window.addEventListener('orbitguard-data-refreshed', handleRefreshed)

    return () => {
      clearInterval(interval)
      window.removeEventListener('orbitguard-data-refreshed', handleRefreshed)
    }
  }, [])

  const selected = conjunctionsList.find((c) => String(c.id) === String(selectedId)) || conjunctionsList[0]
  const meta = selected ? riskLevelMeta[levelOf(selected)] || riskLevelMeta.green : riskLevelMeta.green

  return (
    <div className="space-y-5 p-5">
      {/* Tab Switcher: Operations Dashboard vs 3D Orbit Globe */}
      <div className="flex items-center justify-between border-b border-line pb-3">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('overview')}
            className={`px-4 py-2 text-xs font-semibold rounded-md transition-all ${
              activeTab === 'overview'
                ? 'bg-signal/20 text-signal border border-signal/40'
                : 'bg-void-700 text-ink-muted hover:text-ink hover:bg-void-600 border border-line'
            }`}
          >
            📊 Live Risk Operations
          </button>
          <button
            onClick={() => setActiveTab('globe')}
            className={`px-4 py-2 text-xs font-semibold rounded-md transition-all ${
              activeTab === 'globe'
                ? 'bg-signal/20 text-signal border border-signal/40'
                : 'bg-void-700 text-ink-muted hover:text-ink hover:bg-void-600 border border-line'
            }`}
          >
            🌍 3D LEO Orbit View
          </button>
        </div>

        <div className="text-right font-mono text-[10px]">
          <span className={`px-2 py-0.5 rounded font-semibold ${source === 'live' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : 'bg-amber-500/20 text-amber-300'}`}>
            {source === 'live' ? `LIVE · ${(statsData.objectsTracked || 133).toLocaleString()} SGP4 Catalog Screened` : 'FALLBACK DATA'}
          </span>
        </div>
      </div>

      {activeTab === 'globe' ? (
        <OrbitVisualization />
      ) : (
        <>
          {/* Today's Operational Horizon Callout */}
          <div className="flex items-center justify-between p-3 rounded-lg bg-indigo-950/30 border border-indigo-500/30 text-xs">
            <div className="flex items-center gap-2 text-indigo-300 font-semibold">
              <span>📅 TODAY'S SCREENING HORIZON ({new Date().toISOString().slice(0, 10)})</span>
            </div>
            <span className="text-[11px] text-ink-muted">
              Showing active close approaches occurring within today's 24h propagation window
            </span>
          </div>

          {/* Live System Stat Cards */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard label="Objects tracked" value={(statsData.objectsTracked ?? 133).toLocaleString()} delta={statsData.objectsTrackedDelta ?? ''} accent="text-risk-green" />
            <StatCard label="Active conjunctions" value={statsData.activeConjunctions ?? conjunctionsList.length} delta={statsData.activeConjunctionsDelta ?? ''} accent="text-risk-amber" />
            <StatCard label="High-risk events" value={statsData.highRiskEvents ?? 1} delta={statsData.highRiskEventsDelta ?? ''} accent="text-risk-critical" />
            <StatCard label="Satellites monitored" value={(statsData.satellitesMonitored ?? 587).toLocaleString()} delta={statsData.satellitesMonitoredDelta ?? ''} accent="text-risk-green" />
          </div>

          {/* 3D Orbit Viewer + Event Metrics */}
          {selected && (
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
                    <dd className="font-mono text-ink">in {selected.tcaIn || '42 min'}</dd>
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
          )}

          {/* Active Conjunctions Table */}
          <ConjunctionList conjunctions={conjunctionsList} selectedId={selected?.id} onSelect={setSelectedId} />

          {/* AI Risk Copilot Decision Intelligence */}
          {selected && <ExplainMyDecision conjunctionId={selected.id} className="mt-6" />}

          {/* Risk Timeline */}
          {selected && <RiskTimeline timeline={selected.timeline} />}
        </>
      )}
    </div>
  )
}
