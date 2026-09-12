import { CheckCircle2, XCircle, Loader2 } from 'lucide-react'

// Each check reads from the backend's validation result when one is present.
// Mock data has no checks, so the panel falls back to the original behaviour:
// the first two steps pass, and the rest follow the overall verdict.
function checklist(validated, checks) {
  if (!checks) {
    return [
      ['Original conjunction resolved', true],
      ['Post-maneuver trajectory calculated', true],
      ['Full environment re-screened', validated],
      ['No new critical conjunctions', validated],
      ['Minimum safe Δv confirmed', validated],
    ]
  }
  return [
    ['Original conjunction resolved', checks.originalResolved],
    ['Post-maneuver trajectory calculated', checks.trajectoryPropagated],
    [
      checks.catalogRescreened
        ? `Full environment re-screened (${checks.objectsScreened} objects, ${checks.horizonHours} h)`
        : 'Full environment re-screened',
      checks.catalogRescreened,
    ],
    ['No new critical conjunctions', checks.catalogRescreened && checks.newConjunctions === 0],
    ['Minimum safe Δv confirmed', validated],
  ]
}

function formatPc(pc, belowFloor) {
  if (pc == null) return '—'
  if (belowFloor || pc < 1e-12) return '< 1e-12'
  return pc.toExponential(2)
}

export default function ValidationPanel({ status, candidate, conjunction, result }) {
  // status: 'idle' | 'running' | 'validated' | 'rejected'

  if (status === 'idle') {
    return (
      <div className="panel p-5 text-xs text-ink-faint">
        Select a candidate and run validation to re-propagate the trajectory and re-screen the
        full environment. A maneuver that fixes one collision must not create another.
      </div>
    )
  }

  if (status === 'running') {
    return (
      <div className="panel flex items-center gap-2 p-5 text-xs text-ink-muted">
        <Loader2 size={14} className="animate-spin text-signal" />
        Re-propagating trajectory and re-screening full environment…
      </div>
    )
  }

  const validated = status === 'validated'
  const live = Boolean(result?.checks)
  const shown = result?.candidate ?? candidate

  return (
    <div className="panel p-5">
      <div className="mb-3 space-y-2">
        {checklist(validated, result?.checks).map(([label, ok]) => (
          <div key={label} className="flex items-center gap-2 text-xs">
            {ok ? (
              <CheckCircle2 size={14} className="text-risk-green shrink-0" />
            ) : (
              <XCircle size={14} className="text-risk-critical shrink-0" />
            )}
            <span className={ok ? 'text-ink-muted' : 'text-ink-faint line-through'}>{label}</span>
          </div>
        ))}
      </div>

      <div
        className="mt-4 rounded-lg border px-4 py-3 text-center text-sm font-semibold tracking-wide"
        style={
          validated
            ? { borderColor: '#3ED59850', backgroundColor: '#3ED59815', color: '#3ED598' }
            : { borderColor: '#F0475A50', backgroundColor: '#F0475A15', color: '#F0475A' }
        }
      >
        {validated ? 'MANEUVER VALIDATED' : 'REJECTED'}
      </div>
      {!validated && (
        <p className="mt-2 text-center text-[11px] text-ink-faint">
          {result?.reason ?? shown?.reason ?? 'Creates another unsafe conjunction.'}
        </p>
      )}

      {shown && (
        <div className="mt-4 grid grid-cols-2 gap-y-2 border-t border-line pt-3 text-xs">
          <span className="text-ink-faint">Δv</span>
          <span className="text-right font-mono text-ink">{shown.deltaV.toFixed(2)} m/s</span>
          <span className="text-ink-faint">Direction</span>
          <span className="text-right font-mono text-ink">{shown.direction}</span>
          {shown.leadHours != null && (
            <>
              <span className="text-ink-faint">Burn before TCA</span>
              <span className="text-right font-mono text-ink">{shown.leadHours.toFixed(2)} h</span>
            </>
          )}
          <span className="text-ink-faint">Current separation</span>
          <span className="text-right font-mono text-ink">
            {(conjunction.minDistanceM / 1000).toFixed(2)} km
          </span>
          <span className="text-ink-faint">Predicted separation</span>
          <span className="text-right font-mono text-risk-green">{shown.newSeparationKm.toFixed(2)} km</span>
          {live ? (
            <>
              <span className="text-ink-faint">Collision probability</span>
              <span className="text-right font-mono text-ink">
                {formatPc(result.pcBefore)} →{' '}
                <span className={validated ? 'text-risk-green' : 'text-risk-critical'}>
                  {formatPc(result.pcAfter, result.pcAfterBelowFloor)}
                </span>
              </span>
              {shown.propellantKg != null && (
                <>
                  <span className="text-ink-faint">Propellant cost</span>
                  <span className="text-right font-mono text-ink">{shown.propellantKg.toFixed(1)} kg</span>
                </>
              )}
            </>
          ) : (
            <>
              <span className="text-ink-faint">Risk score</span>
              <span className="text-right font-mono text-ink">
                {conjunction.riskScore} →{' '}
                <span className="text-risk-green">{validated ? 18 : conjunction.riskScore}</span>
              </span>
            </>
          )}
        </div>
      )}
    </div>
  )
}
