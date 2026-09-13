import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Legend } from 'recharts'
import { conjunctions, riskLevelMeta, levelFromScore } from '../data/mockData'
import { leoObjects, typeColor } from '../data/leoObjects'

const riskCounts = Object.keys(riskLevelMeta).map((level) => ({
  level: riskLevelMeta[level].label,
  count: conjunctions.filter((c) => levelFromScore(c.riskScore) === level).length,
  color: riskLevelMeta[level].color,
}))

const typeCounts = ['active', 'debris', 'rocket_body'].map((type) => ({
  name: type === 'active' ? 'Active satellites' : type === 'debris' ? 'Debris' : 'Rocket bodies',
  value: leoObjects.filter((o) => o.type === type).length,
  color: typeColor[type],
}))

const trend = [
  { day: 'Mon', conjunctions: 24 },
  { day: 'Tue', conjunctions: 29 },
  { day: 'Wed', conjunctions: 22 },
  { day: 'Thu', conjunctions: 31 },
  { day: 'Fri', conjunctions: 34 },
  { day: 'Sat', conjunctions: 28 },
  { day: 'Sun', conjunctions: 37 },
]

export default function AnalyticsPage() {
  return (
    <div className="space-y-5 p-5">
      <div>
        <h1 className="font-display text-lg font-semibold text-ink">Analytics</h1>
        <p className="mt-1 text-xs text-ink-faint">Trends across the tracked catalog and detected conjunctions.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="panel p-5">
          <div className="mb-3 text-xs font-medium tracking-wide text-ink-muted">CONJUNCTIONS BY RISK LEVEL</div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={riskCounts} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid stroke="#1E2836" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="level" stroke="#576273" fontSize={11} tickLine={false} axisLine={{ stroke: '#1E2836' }} />
                <YAxis stroke="#576273" fontSize={11} tickLine={false} axisLine={{ stroke: '#1E2836' }} allowDecimals={false} />
                <Tooltip contentStyle={{ background: '#0F1520', border: '1px solid #1E2836', fontSize: 12 }} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {riskCounts.map((r) => (
                    <Cell key={r.level} fill={r.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel p-5">
          <div className="mb-3 text-xs font-medium tracking-wide text-ink-muted">TRACKED CATALOG COMPOSITION</div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={typeCounts} dataKey="value" nameKey="name" innerRadius={45} outerRadius={75} paddingAngle={3}>
                  {typeCounts.map((t) => (
                    <Cell key={t.name} fill={t.color} />
                  ))}
                </Pie>
                <Legend wrapperStyle={{ fontSize: 11, color: '#8A96A8' }} />
                <Tooltip contentStyle={{ background: '#0F1520', border: '1px solid #1E2836', fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="panel p-5">
        <div className="mb-3 text-xs font-medium tracking-wide text-ink-muted">CONJUNCTIONS DETECTED — LAST 7 DAYS</div>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={trend} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid stroke="#1E2836" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="day" stroke="#576273" fontSize={11} tickLine={false} axisLine={{ stroke: '#1E2836' }} />
              <YAxis stroke="#576273" fontSize={11} tickLine={false} axisLine={{ stroke: '#1E2836' }} allowDecimals={false} />
              <Tooltip contentStyle={{ background: '#0F1520', border: '1px solid #1E2836', fontSize: 12 }} />
              <Bar dataKey="conjunctions" fill="#3FD7E8" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
