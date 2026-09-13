import { colorForView } from '../data/leoObjects'

const DEG2RAD = Math.PI / 180

function project(lat, lon, rotationDeg, radius, cx, cy) {
  const phi = lat * DEG2RAD
  const lambda = (lon - rotationDeg) * DEG2RAD
  const x = radius * Math.cos(phi) * Math.sin(lambda)
  const y = -radius * Math.sin(phi)
  const z = Math.cos(phi) * Math.cos(lambda)
  return { x: cx + x, y: cy + y, z }
}

export default function LeoGlobe({
  objects,
  rotation,
  viewMode,
  layers,
  filterType,
  searchQuery,
  groundStations,
  tick,
}) {
  const W = 700
  const H = 520
  const cx = W / 2
  const cy = H / 2
  const earthR = 150
  const fieldR = earthR + 4

  const query = searchQuery.trim().toLowerCase()

  const visibleObjects = objects.filter((o) => {
    if (!layers.debris && o.type === 'debris') return false
    if (filterType !== 'all' && o.type !== filterType) return false
    return true
  })

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full select-none">
      {/* starfield */}
      {Array.from({ length: 90 }).map((_, i) => (
        <circle key={i} cx={(i * 53) % W} cy={(i * 71) % H} r={i % 6 === 0 ? 1.2 : 0.6} fill="#232C3C" />
      ))}

      {/* Earth */}
      <defs>
        <radialGradient id="earthFill" cx="35%" cy="30%" r="75%">
          <stop offset="0%" stopColor="#1C4560" />
          <stop offset="60%" stopColor="#0E2C42" />
          <stop offset="100%" stopColor="#081A28" />
        </radialGradient>
        <radialGradient id="earthGlow" cx="50%" cy="50%" r="50%">
          <stop offset="85%" stopColor="#3FD7E8" stopOpacity="0" />
          <stop offset="100%" stopColor="#3FD7E8" stopOpacity="0.18" />
        </radialGradient>
      </defs>
      <circle cx={cx} cy={cy} r={earthR} fill="url(#earthFill)" />
      <circle cx={cx} cy={cy} r={earthR} fill="none" stroke="#1E5A63" strokeWidth="1" />
      <circle cx={cx} cy={cy} r={earthR + 10} fill="url(#earthGlow)" />

      {/* graticule */}
      {[-60, -30, 0, 30, 60].map((lat) => {
        const pts = Array.from({ length: 61 }).map((_, i) => {
          const lon = -180 + i * 6
          return project(lat, lon, rotation, earthR, cx, cy)
        })
        const path = pts
          .filter((p) => p.z > 0.05)
          .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
          .join(' ')
        return <path key={lat} d={path} stroke="#1E5A63" strokeWidth="0.5" fill="none" opacity="0.5" />
      })}

      {/* ground station beams */}
      {layers.beams &&
        groundStations.map((gs) => {
          const p = project(gs.lat, gs.lon, rotation, earthR, cx, cy)
          if (p.z < 0.1) return null
          const heading = (gs.beamHeadingDeg + rotation * 0.3) * DEG2RAD
          const len = 70
          const spread = 18 * DEG2RAD
          const tipX = p.x + Math.cos(heading) * len
          const tipY = p.y + Math.sin(heading) * len
          const leftX = p.x + Math.cos(heading - spread) * len * 0.55
          const leftY = p.y + Math.sin(heading - spread) * len * 0.55
          const rightX = p.x + Math.cos(heading + spread) * len * 0.55
          const rightY = p.y + Math.sin(heading + spread) * len * 0.55
          return (
            <polygon
              key={gs.name}
              points={`${p.x},${p.y} ${leftX},${leftY} ${tipX},${tipY} ${rightX},${rightY}`}
              fill="#F0475A"
              opacity="0.28"
              stroke="#F0475A"
              strokeOpacity="0.4"
              strokeWidth="0.5"
            />
          )
        })}

      {/* ground station instrument markers */}
      {layers.instruments &&
        groundStations.map((gs) => {
          const p = project(gs.lat, gs.lon, rotation, earthR, cx, cy)
          if (p.z < 0.05) return null
          return (
            <g key={gs.name}>
              <rect x={p.x - 3} y={p.y - 3} width="6" height="6" fill="#F2C94C" opacity="0.9" transform={`rotate(45 ${p.x} ${p.y})`} />
            </g>
          )
        })}

      {/* tracked object field */}
      {visibleObjects.map((o) => {
        const p = project(o.lat, o.lon, rotation, fieldR, cx, cy)
        const behindEarth = p.z < 0 && (p.x - cx) ** 2 + (p.y - cy) ** 2 < earthR ** 2
        if (behindEarth) return null

        // deterministic pseudo-refresh flicker for a small rotating subset of objects
        const flicker = tick > 0 && o.id % 11 === tick % 11
        const opacity = p.z > 0 ? (flicker ? 1 : 0.85) : 0.32
        const color = colorForView(o, viewMode)
        const matches = query && o.name.toLowerCase().includes(query)

        return (
          <g key={o.id}>
            <circle cx={p.x} cy={p.y} r={matches ? 3.2 : 1.4} fill={color} opacity={opacity} />
            {matches && (
              <circle cx={p.x} cy={p.y} r="7" fill="none" stroke="#3FD7E8" strokeWidth="1.2">
                <animate attributeName="r" values="6;10;6" dur="1.6s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.9;0.1;0.9" dur="1.6s" repeatCount="indefinite" />
              </circle>
            )}
          </g>
        )
      })}
    </svg>
  )
}
