export default function RiskFactors({ factors = [] }) {
  return (
    <div className="panel p-5">
      <div className="mb-4 text-xs font-medium tracking-wide text-ink-muted">WHY IS THIS EVENT DANGEROUS?</div>
      <div className="space-y-3">
        {(factors || []).map((f) => (
          <div key={f.label}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="text-ink-muted">{f.label}</span>
              <span className="font-mono text-ink-faint">{f.pct}%</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-void-500">
              <div
                className="h-1.5 rounded-full bg-signal"
                style={{ width: `${f.pct}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
