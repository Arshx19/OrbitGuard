import { riskLevelMeta, levelFromScore } from '../data/mockData'

// Renders Earth at center, two orbit paths, the primary/secondary objects,
// and highlights the closest-approach point. Optionally overlays a dashed
// "predicted" post-maneuver path when `maneuverPreview` is true.
export default function OrbitViewer({ conjunction, candidate = null, maneuverPreview = false }) {
  if (!conjunction) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-ink-faint">
        Select a conjunction to view its orbit
      </div>
    )
  }

  const level = levelFromScore(conjunction.riskScore)
  const color = riskLevelMeta[level].color

  const cx = 250
  const cy = 165
  const primaryR = 95
  const secondaryR = 125
  const offsetRadius = candidate?.newSeparationKm ? Math.min(32, Math.max(12, Math.round(candidate.newSeparationKm * 6))) : 20

  // simple fixed demo angles so the closest-approach marker reads clearly
  const primaryAngle = -20
  const secondaryAngle = 18
  const toXY = (r, deg) => {
    const rad = (deg * Math.PI) / 180
    return [cx + r * Math.cos(rad), cy + r * Math.sin(rad) * 0.55]
  }
  const [px, py] = toXY(primaryR, primaryAngle)
  const [sx, sy] = toXY(secondaryR, secondaryAngle)
  const [cax, cay] = [(px + sx) / 2 + 25, (py + sy) / 2 - 10]

  return (
    <svg viewBox="0 0 500 330" preserveAspectRatio="xMidYMid meet" className="h-full w-full">
      {/* starfield */}
      {Array.from({ length: 40 }).map((_, i) => (
        <circle
          key={i}
          cx={(i * 37) % 500}
          cy={(i * 53) % 330}
          r={i % 5 === 0 ? 1.3 : 0.6}
          fill="#2A3547"
        />
      ))}

      {/* orbit paths */}
      <ellipse cx={cx} cy={cy} rx={primaryR} ry={primaryR * 0.55} fill="none" stroke="#1E5A63" strokeWidth="1" />
      <ellipse cx={cx} cy={cy} rx={secondaryR} ry={secondaryR * 0.55} fill="none" stroke="#3A2530" strokeWidth="1" />

      {maneuverPreview && (
        <ellipse
          cx={cx + 6}
          cy={cy}
          rx={primaryR + offsetRadius}
          ry={(primaryR + offsetRadius) * 0.55}
          fill="none"
          stroke="#3ED598"
          strokeWidth="1.5"
          strokeDasharray="5 4"
        />
      )}

      {/* Earth */}
      <circle cx={cx} cy={cy} r="40" fill="#12314A" stroke="#1E5A63" strokeWidth="1" />
      <circle cx={cx} cy={cy} r="40" fill="url(#earthShade)" opacity="0.7" />
      <defs>
        <radialGradient id="earthShade" cx="35%" cy="30%" r="70%">
          <stop offset="0%" stopColor="#3FD7E8" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#0A0E17" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* closest approach highlight */}
      <line x1={px} y1={py} x2={sx} y2={sy} stroke={color} strokeWidth="1" strokeDasharray="3 3" opacity="0.6" />
      <circle cx={(px + sx) / 2} cy={(py + sy) / 2} r="9" fill="none" stroke={color} strokeWidth="1.5" />

      {/* primary satellite */}
      <circle cx={px} cy={py} r="4" fill="#3FD7E8" />
      <text x={px + 8} y={py - 6} className="font-mono" fontSize="9" fill="#8A96A8">
        {conjunction.primary}
      </text>

      {/* secondary object */}
      <circle cx={sx} cy={sy} r="3.5" fill={color} />
      <text x={sx + 8} y={sy - 6} className="font-mono" fontSize="9" fill="#8A96A8">
        {conjunction.secondary}
      </text>

      {/* TCA callout */}
      <rect x={cax - 4} y={cay - 16} width="118" height="30" rx="4" fill="#0F1520" stroke={color} strokeWidth="1" />
      <text x={cax + 2} y={cay - 4} fontSize="8" fill={color} className="font-mono" fontWeight="600">
        CONJUNCTION
      </text>
      <text x={cax + 2} y={cay + 8} fontSize="8" fill="#8A96A8" className="font-mono">
        TCA {conjunction.tcaIn}
      </text>

      {/* Orbit Trajectory Legend */}
      <g transform="translate(15, 295)">
        <line x1="0" y1="0" x2="16" y2="0" stroke="#1E5A63" strokeWidth="2" />
        <text x="22" y="3" fontSize="9" fill="#8A96A8" className="font-mono">Before Maneuver Path</text>
        {maneuverPreview && (
          <>
            <line x1="140" y1="0" x2="156" y2="0" stroke="#3ED598" strokeWidth="2" strokeDasharray="4 3" />
            <text x="162" y="3" fontSize="9" fill="#3ED598" className="font-mono">After Maneuver Path (+Δv)</text>
          </>
        )}
      </g>
    </svg>
  )
}
