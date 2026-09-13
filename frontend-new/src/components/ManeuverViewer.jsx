import OrbitViewer from './OrbitViewer'

export default function ManeuverViewer({ conjunction, candidate }) {
  return (
    <div className="panel flex h-full flex-col p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-medium tracking-wide text-ink-muted">PREDICTED TRAJECTORY</span>
        {candidate && (
          <span className="font-mono text-[11px] text-risk-green">
            Δv {candidate.deltaV.toFixed(2)} m/s · {candidate.direction}
          </span>
        )}
      </div>
      <div className="flex-1">
        <OrbitViewer conjunction={conjunction} maneuverPreview={!!candidate} />
      </div>
      {candidate && (
        <p className="mt-2 border-t border-line pt-2 text-[11px] leading-relaxed text-ink-faint">
          {candidate.reason}
        </p>
      )}
    </div>
  )
}
