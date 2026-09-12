import { useState } from 'react'
import { useParams, Navigate } from 'react-router-dom'
import ManeuverTable from '../components/ManeuverTable'
import ManeuverViewer from '../components/ManeuverViewer'
import ValidationPanel from '../components/ValidationPanel'
import SimulationBadge from '../components/SimulationBadge'
import { getConjunctionById, optimizeManeuver, validateManeuver } from '../api/orbitguard'
import { useApi, Loading } from '../api/useApi'

export default function ManeuverSimulator() {
  const { id } = useParams()
  const conjunctionQuery = useApi(() => getConjunctionById(id), [id])
  const candidatesQuery = useApi(() => optimizeManeuver(id), [id])
  const [selectedCandidateId, setSelectedCandidateId] = useState(null)
  const [status, setStatus] = useState('idle') // idle | running | validated | rejected
  const [result, setResult] = useState(null)

  if (conjunctionQuery.loading || candidatesQuery.loading) {
    return <Loading label="Searching burn magnitude, direction, and timing…" />
  }

  const c = conjunctionQuery.data
  if (!c) return <Navigate to="/" replace />

  const candidates = candidatesQuery.data ?? []
  const candidate = candidates.find((m) => m.id === selectedCandidateId)

  function handleSelect(candidateId) {
    setSelectedCandidateId(candidateId)
    setStatus('idle')
    setResult(null)
  }

  async function handleValidate() {
    if (!candidate) return
    setStatus('running')
    const outcome = await validateManeuver(c.id, candidate.id)
    setResult(outcome)
    setStatus(outcome.validated ? 'validated' : 'rejected')
  }

  return (
    <div className="space-y-5 p-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-ink-faint">
            Maneuver simulator · {c.id}
            <SimulationBadge show={c.simulated} />
          </div>
          <h1 className="mt-1 font-display text-lg font-semibold text-ink">
            Minimum-Δv response for {c.primary}
          </h1>
          {candidates.evaluated != null && (
            <div className="mt-1 text-[11px] text-ink-faint">
              {candidates.evaluated} candidates searched across magnitude, direction, and burn timing
              {candidates.recommendedId && <> · recommended {candidates.recommendedId}</>}
            </div>
          )}
          {candidates.reason && <div className="mt-1 text-[11px] text-ink-faint">{candidates.reason}</div>}
        </div>
        <button
          onClick={handleValidate}
          disabled={!candidate || status === 'running'}
          className="rounded-md border border-signal/40 bg-signal/10 px-4 py-2 text-xs font-medium text-signal transition hover:bg-signal/20 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Validate maneuver
        </button>
      </div>

      <ManeuverTable candidates={candidates} selectedId={selectedCandidateId} onSelect={handleSelect} />

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <div className="h-[320px]">
          <ManeuverViewer conjunction={c} candidate={candidate} />
        </div>
        <ValidationPanel status={status} candidate={candidate} conjunction={c} result={result} />
      </div>
    </div>
  )
}
