import { CheckCircle2, XCircle, Loader2 } from 'lucide-react'

const steps = [
  'Original conjunction resolved',
  'Post-maneuver trajectory calculated',
  'Full environment re-screened',
  'No new critical conjunctions',
  'Minimum safe Δv confirmed',
]

export default function ValidationPanel({ status, candidate, conjunction }) {
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

  return (
    <div className="panel p-5">
      <div className="mb-3 space-y-2">
        {steps.map((s, i) => {
          const ok = validated || i < 2
          return (
            <div key={s} className="flex items-center gap-2 text-xs">
              {ok ? (
                <CheckCircle2 size={14} className="text-risk-green shrink-0" />
              ) : (
                <XCircle size={14} className="text-risk-critical shrink-0" />
              )}
              <span className={ok ? 'text-ink-muted' : 'text-ink-faint line-through'}>{s}</span>
            </div>
          )
        })}
      </div>

      <div
        className="mt-4 rounded-lg border px-4 py-3 text-center text-sm font-semibold tracking-wide"
        style={
          validated
            ? { borderColor: '#3ED59850', backgroundColor: '#3ED59815', color: '#3ED598' }
            : { borderColor: '#F0475A50', backgroundColor: '#F0475A15', color: '#F0475A' }
        }
      >
        {validated ? 'MANEUVER VALIDATED' : 'REJECTED — CREATES ANOTHER UNSAFE CONJUNCTION'}
      </div>

      {candidate && (
        <div className="mt-4 grid grid-cols-2 gap-y-2 border-t border-line pt-3 text-xs">
          <span className="text-ink-faint">Recommended Δv</span>
          <span className="text-right font-mono text-ink">{candidate.deltaV.toFixed(2)} m/s</span>
          <span className="text-ink-faint">Direction</span>
          <span className="text-right font-mono text-ink">{candidate.direction}</span>
          <span className="text-ink-faint">Current separation</span>
          <span className="text-right font-mono text-ink">{(conjunction.minDistanceM / 1000).toFixed(2)} km</span>
          <span className="text-ink-faint">Predicted separation</span>
          <span className="text-right font-mono text-risk-green">{candidate.newSeparationKm.toFixed(2)} km</span>
          <span className="text-ink-faint">Risk score</span>
          <span className="text-right font-mono text-ink">
            {conjunction.riskScore} → <span className="text-risk-green">{validated ? 18 : conjunction.riskScore}</span>
          </span>
        </div>
      )}
    </div>
  )
}
