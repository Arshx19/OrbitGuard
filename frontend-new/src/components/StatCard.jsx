export default function StatCard({ label, value, delta, accent = 'text-signal' }) {
  return (
    <div className="panel px-4 py-3">
      <div className="text-[11px] uppercase tracking-wide text-ink-faint">{label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="font-mono text-2xl font-semibold text-ink">{value}</span>
        {delta && <span className={`font-mono text-[11px] ${accent}`}>{delta}</span>}
      </div>
    </div>
  )
}
