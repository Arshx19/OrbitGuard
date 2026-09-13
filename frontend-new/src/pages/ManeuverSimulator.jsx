import { useState } from 'react'
import { useParams, Navigate } from 'react-router-dom'
import { getConjunction } from '../data/mockData'
import ManeuverTable from '../components/ManeuverTable'
import ManeuverViewer from '../components/ManeuverViewer'
import ValidationPanel from '../components/ValidationPanel'
import { validateManeuver } from '../api/orbitguard'

export default function ManeuverSimulator() {
  const { id } = useParams()
  const c = getConjunction(id)
  const [selectedCandidateId, setSelectedCandidateId] = useState(null)
  const [status, setStatus] = useState('idle') // idle | running | validated | rejected

  if (!c) return <Navigate to="/" replace />

  const candidate = c.maneuverCandidates.find((m) => m.id === selectedCandidateId)

  function handleSelect(candidateId) {
    setSelectedCandidateId(candidateId)
    setStatus('idle')
  }

  async function handleValidate() {
    if (!candidate) return
    setStatus('running')
    const result = await validateManeuver(c.id, candidate.id)
    setStatus(result.validated ? 'validated' : 'rejected')
  }

  return (
    <div className="space-y-5 p-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-ink-faint">Maneuver simulator · {c.id}</div>
          <h1 className="mt-1 font-display text-lg font-semibold text-ink">
            Minimum-Δv response for {c.primary}
          </h1>
        </div>
        <button
          onClick={handleValidate}
          disabled={!candidate || status === 'running'}
          className="rounded-md border border-signal/40 bg-signal/10 px-4 py-2 text-xs font-medium text-signal transition hover:bg-signal/20 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Validate maneuver
        </button>
      </div>

      <ManeuverTable
        candidates={c.maneuverCandidates}
        selectedId={selectedCandidateId}
        onSelect={handleSelect}
      />

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <div className="h-[320px]">
          <ManeuverViewer conjunction={c} candidate={candidate} />
        </div>
        <ValidationPanel status={status} candidate={candidate} conjunction={c} />
      </div>
    </div>
  )
}
