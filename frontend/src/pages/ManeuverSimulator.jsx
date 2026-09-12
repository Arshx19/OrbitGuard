import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { conjunctions as defaultConjunctions, getConjunction } from '../data/mockData'
import { optimizeManeuver, validateManeuver, getConjunctionById } from '../api/orbitguard'
import ManeuverTable from '../components/ManeuverTable'
import ManeuverViewer from '../components/ManeuverViewer'
import ValidationPanel from '../components/ValidationPanel'

export default function ManeuverSimulator() {
  const { id } = useParams()
  const defaultC = getConjunction(id) || defaultConjunctions[0]
  const [c, setC] = useState(defaultC)
  const [selectedCandidateId, setSelectedCandidateId] = useState(null)
  const [status, setStatus] = useState('idle') // idle | running | validated | rejected

  useEffect(() => {
    async function loadManeuverData() {
      try {
        const detail = await getConjunctionById(id)
        const candidates = await optimizeManeuver(id)

        setC(prev => ({
          ...prev,
          id: detail?.id || detail?.conjunction_id || id,
          primary: detail?.satellite1_name || prev.primary,
          secondary: detail?.satellite2_name || prev.secondary,
          maneuverCandidates: candidates && candidates.length > 0 ? candidates.map((cand, idx) => ({
            id: cand.candidate_id || cand.id || idx + 1,
            deltaV: cand.delta_v_magnitude_ms || cand.deltaV || 0.30,
            direction: cand.direction_name || cand.direction || 'Along-track',
            newSeparationKm: cand.new_miss_distance_km || cand.newSeparationKm || 4.50,
            newRisk: cand.secondary_threats_detected ? 'Threat Detected' : 'None detected',
            status: cand.is_safe || cand.status === 'SAFE' || cand.status === 'VALIDATED' ? 'SAFE' : 'REJECT',
            reason: cand.rejection_reason || cand.reason || 'Clears the original event and no new conjunction is introduced on re-screen.'
          })) : prev.maneuverCandidates
        }))
      } catch (e) {
        console.warn("Error loading maneuver simulator live data:", e)
      }
    }
    loadManeuverData()
  }, [id])

  const candidatesList = c.maneuverCandidates || defaultC.maneuverCandidates
  const candidate = candidatesList.find((m) => m.id === selectedCandidateId)

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
        candidates={candidatesList}
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
