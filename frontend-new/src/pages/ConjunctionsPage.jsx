import { useState } from 'react'
import { conjunctions, stats } from '../data/mockData'
import StatCard from '../components/StatCard'
import ConjunctionList from '../components/ConjunctionList'

export default function ConjunctionsPage() {
  const [selectedId, setSelectedId] = useState(null)

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
