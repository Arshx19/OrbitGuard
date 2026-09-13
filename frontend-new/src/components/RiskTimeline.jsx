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
  const hasAfter = afterManeuver && timeline?.some((p) => p.afterKm != null)

  return (
    <div className="panel p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <span className="text-xs font-medium tracking-wide text-ink-muted">DISTANCE / TCA TIMELINE</span>
          <div className="mt-1 flex items-center gap-4 text-[11px]">
            <div className="flex items-center gap-1.5 font-medium text-[#3FD7E8]">
              <span className="h-0.5 w-4 rounded bg-[#3FD7E8]" />
              <span>Before maneuver (Pre-burn baseline)</span>
            </div>
            {hasAfter && (
              <div className="flex items-center gap-1.5 font-medium text-[#3ED598]">
                <span className="h-0.5 w-4 rounded bg-[#3ED598] stroke-dash" style={{ borderTop: '2px dashed #3ED598', height: 0 }} />
                <span>After maneuver (Post-burn separation)</span>
              </div>
            )}
          </div>
        </div>
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
            <Line type="monotone" dataKey="distanceKm" name="Before maneuver" stroke="#3FD7E8" strokeWidth={2} dot={{ r: 4 }} />
            {hasAfter && (
              <Line
                type="monotone"
                dataKey="afterKm"
                name="After maneuver"
                stroke="#3ED598"
                strokeWidth={2.5}
                strokeDasharray="6 4"
                dot={{ r: 4, fill: '#3ED598' }}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
