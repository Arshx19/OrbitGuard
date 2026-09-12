import { riskLevelMeta, levelFromScore } from '../data/mockData'

// `level` should come from the backend, which keys severity to collision
// probability. Bucketing the score is only a fallback for mock data.
export default function RiskScore({ score, level, probability }) {
  const meta = riskLevelMeta[level ?? levelFromScore(score)]
  const circumference = 2 * Math.PI * 54

  return (
    <div className="panel flex flex-col items-center gap-3 p-6">
      <div className="relative h-36 w-36">
        <svg viewBox="0 0 130 130" className="h-full w-full -rotate-90">
          <circle cx="65" cy="65" r="54" fill="none" stroke="#1E2836" strokeWidth="10" />
          <circle
            cx="65"
            cy="65"
            r="54"
            fill="none"
            stroke={meta.color}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - score / 100)}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-4xl font-bold text-ink">{score}</span>
          <span className="text-[10px] text-ink-faint">/ 100</span>
        </div>
      </div>
      <span
        className="rounded px-3 py-1 text-xs font-semibold tracking-wide"
        style={{ color: meta.color, backgroundColor: `${meta.color}1A`, border: `1px solid ${meta.color}40` }}
      >
        {meta.label.toUpperCase()}
      </span>
      {probability != null && (
        <span className="font-mono text-[11px] text-ink-faint">
          Pc {probability < 1e-12 ? '< 1e-12' : probability.toExponential(2)}
        </span>
      )}
    </div>
  )
}
