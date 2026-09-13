import { useState, useEffect } from 'react'
import { listConjunctions, getStats } from '../api/orbitguard'
import StatCard from '../components/StatCard'
import ConjunctionList from '../components/ConjunctionList'

export default function ConjunctionsPage() {
  const [conjunctions, setConjunctions] = useState([])
  const [stats, setStats] = useState({
    objectsTracked: 133,
    activeConjunctions: 0,
    highRiskEvents: 0,
    satellitesMonitored: 587,
    objectsTrackedDelta: '',
    activeConjunctionsDelta: '',
    highRiskEventsDelta: '',
    satellitesMonitoredDelta: '',
  })
  const [selectedId, setSelectedId] = useState(null)

  useEffect(() => {
    async function loadData() {
      try {
        const [cList, statData] = await Promise.all([listConjunctions(), getStats()])
        if (Array.isArray(cList)) setConjunctions(cList)
        if (statData) setStats(statData)
      } catch (e) {
        console.warn('Error loading conjunctions page data:', e)
      }
    }
    loadData()
  }, [])

  return (
    <div className="space-y-5 p-5">
      <div>
        <h1 className="font-display text-lg font-semibold text-ink">Conjunctions</h1>
        <p className="mt-1 text-xs text-ink-faint">Every tracked close approach, prioritized by risk.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Objects tracked" value={stats.objectsTracked.toLocaleString()} delta={stats.objectsTrackedDelta} accent="text-risk-green" />
        <StatCard label="Active conjunctions" value={stats.activeConjunctions} delta={stats.activeConjunctionsDelta} accent="text-risk-amber" />
        <StatCard label="High-risk events" value={stats.highRiskEvents} delta={stats.highRiskEventsDelta} accent="text-risk-critical" />
        <StatCard label="Satellites monitored" value={stats.satellitesMonitored.toLocaleString()} delta={stats.satellitesMonitoredDelta} accent="text-risk-green" />
      </div>

      <ConjunctionList conjunctions={conjunctions} selectedId={selectedId} onSelect={setSelectedId} />
    </div>
  )
}
