// Renders the counterfactual breakdown of a risk score.
//
// Two things differ from a plain feature-importance chart:
//
// - A factor can REDUCE the probability. Large ephemeris uncertainty spreads
//   the position distribution out, and past a point that lowers the collision
//   probability rather than raising it. Those arrive with direction ===
//   'reduces' and a negative pct. Bar widths therefore use `magnitude`, because
//   a negative CSS width renders as nothing and the finding would vanish.
//
// - Each factor carries an `explanation`: a concrete counterfactual such as
//   "with both elements fresh at epoch, the probability would be 4.86e-04".
//   It is surfaced as a tooltip.
//
// Mock data supplies only { label, pct }, so magnitude and direction both fall
// back safely and this renders unchanged against it.

function FactorRow({ factor, tone }) {
  const width = factor.magnitude ?? Math.abs(factor.pct ?? 0)
  const barColor = tone === 'reduces' ? 'bg-risk-green' : 'bg-signal'

  return (
    <div title={factor.explanation || undefined}>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-ink-muted">{factor.label}</span>
        <span className="font-mono text-ink-faint">
          {tone === 'reduces' ? '' : ''}
          {factor.pct}%
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-void-500">
        <div className={`h-1.5 rounded-full ${barColor}`} style={{ width: `${width}%` }} />
      </div>
    </div>
  )
}

export default function RiskFactors({ factors = [] }) {
  const raising = factors.filter((f) => (f.direction ?? 'raises') === 'raises')
  const reducing = factors.filter((f) => f.direction === 'reduces')

  return (
    <div className="panel p-5">
      <div className="mb-4 text-xs font-medium tracking-wide text-ink-muted">
        WHY IS THIS EVENT DANGEROUS?
      </div>

      <div className="space-y-3">
        {raising.length === 0 && (
          <div className="text-xs text-ink-faint">No risk-elevating factors identified.</div>
        )}
        {raising.map((f) => (
          <FactorRow key={f.label} factor={f} tone="raises" />
        ))}
      </div>

      {reducing.length > 0 && (
        <>
          <div className="mb-3 mt-5 text-xs font-medium tracking-wide text-ink-muted">
            CURRENTLY LOWERING THE PROBABILITY
          </div>
          <div className="space-y-3">
            {reducing.map((f) => (
              <FactorRow key={f.label} factor={f} tone="reduces" />
            ))}
          </div>
          <p className="mt-3 text-[11px] leading-relaxed text-ink-faint">
            Uncertainty dilution: when a position is poorly known, the probability
            spreads out and less of it lands on the target. Tighter tracking data would
            raise this score, not lower it.
          </p>
        </>
      )}
    </div>
  )
}
