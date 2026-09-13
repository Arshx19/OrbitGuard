import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded border border-line bg-void-700 px-3 py-2 text-xs">
      <div className="font-mono text-ink-muted">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="font-mono" style={{ color: p.color }}>
          {p.name}: {p.value} km
        </div>
      ))}
    </div>
  )
}

export default function RiskTimeline({ timeline, afterManeuver }) {
  return (
    <div className="panel p-5">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-medium tracking-wide text-ink-muted">DISTANCE / TCA TIMELINE</span>
        <span className="font-mono text-[10px] text-ink-faint">closing distance (km)</span>
      </div>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={timeline} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
            <CartesianGrid stroke="#1E2836" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="t" stroke="#576273" fontSize={11} tickLine={false} axisLine={{ stroke: '#1E2836' }} />
            <YAxis stroke="#576273" fontSize={11} tickLine={false} axisLine={{ stroke: '#1E2836' }} />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine x="T-0" stroke="#F0475A" strokeDasharray="4 4" label={{ value: 'TCA', fill: '#F0475A', fontSize: 10, position: 'top' }} />
            <Line type="monotone" dataKey="distanceKm" name="Before maneuver" stroke="#3FD7E8" strokeWidth={2} dot={{ r: 3 }} />
            {afterManeuver && (
              <Line
                type="monotone"
                dataKey="afterKm"
                name="After maneuver"
                stroke="#3ED598"
                strokeWidth={2}
                strokeDasharray="5 4"
                dot={{ r: 3 }}
                data={afterManeuver}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
