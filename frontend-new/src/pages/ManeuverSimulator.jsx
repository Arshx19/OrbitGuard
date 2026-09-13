import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { conjunctions as defaultConjunctions, getConjunction } from '../data/mockData'
import { optimizeManeuver, validateManeuver, getConjunctionById } from '../api/orbitguard'
import SimulationBadge from '../components/SimulationBadge'
import ManeuverTable from '../components/ManeuverTable'
import ManeuverViewer from '../components/ManeuverViewer'
import ValidationPanel from '../components/ValidationPanel'
import RiskTimeline from '../components/RiskTimeline'
import ExplainMyDecision from '../components/ExplainMyDecision'

export default function ManeuverSimulator() {
  const { id } = useParams()
  const defaultC = getConjunction(id) || defaultConjunctions[0]
  const [c, setC] = useState(defaultC)
  const [selectedCandidateId, setSelectedCandidateId] = useState(null)
  const [status, setStatus] = useState('idle') // idle | running | validated | rejected
  const [result, setResult] = useState(null)
  const [searchInfo, setSearchInfo] = useState(null)

  useEffect(() => {
    async function loadManeuverData() {
      try {
        const detail = await getConjunctionById(id)
        const candidates = await optimizeManeuver(id)
        const list = (Array.isArray(candidates) && candidates.length > 0)
          ? candidates
          : (detail?.maneuverCandidates || defaultC.maneuverCandidates || [])

        setC((prev) => ({ ...prev, ...(detail ?? {}), maneuverCandidates: list }))
        setSearchInfo({ evaluated: candidates?.evaluated, recommendedId: candidates?.recommendedId, reason: candidates?.reason })

        const recId = candidates?.recommendedId || list.find((m) => m.status === 'SAFE')?.id || list[0]?.id
        if (recId) {
          setSelectedCandidateId(recId)
        }
      } catch (e) {
        console.warn('Error loading maneuver simulator live data:', e)
      }
    }
    loadManeuverData()
  }, [id])

  const candidatesList = (c.maneuverCandidates && c.maneuverCandidates.length > 0)
    ? c.maneuverCandidates
    : defaultC.maneuverCandidates
  const candidate = candidatesList.find((m) => m.id === selectedCandidateId) || candidatesList[0]

  const displayTimeline = (c.timeline || []).map((pt, idx) => {
    let afterKm = undefined
    if (candidate) {
      if (candidate.postBurnTimeline && candidate.postBurnTimeline[idx]) {
        afterKm = candidate.postBurnTimeline[idx].afterKm
      } else {
        const lead = candidate.leadHours || 2.5
        afterKm = (pt.hours >= -lead)
          ? candidate.newSeparationKm
          : pt.distanceKm
      }
    }
    return {
      ...pt,
      afterKm: afterKm != null ? Number(afterKm.toFixed(2)) : undefined,
    }
  })

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
          {searchInfo?.evaluated != null && (
            <div className="mt-1 text-[11px] text-ink-faint">
              {searchInfo.evaluated} candidates searched across magnitude, direction, and burn timing
              {searchInfo.recommendedId && <> · recommended {searchInfo.recommendedId}</>}
            </div>
          )}
          {searchInfo?.reason && <div className="mt-1 text-[11px] text-ink-faint">{searchInfo.reason}</div>}
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
        <div className="min-h-[360px]">
          <ManeuverViewer conjunction={c} candidate={candidate} />
        </div>
        <ValidationPanel status={status} candidate={candidate} conjunction={c} result={result} />
      </div>

      {/* Physics-Calculated Before / After Trajectory Separation Chart */}
      <RiskTimeline timeline={displayTimeline} afterManeuver={candidate ? displayTimeline : null} />

      {/* AI Risk Copilot Decision Intelligence */}
      <ExplainMyDecision conjunctionId={c.id} candidateId={selectedCandidateId} className="mt-6" />
    </div>
  )
}
