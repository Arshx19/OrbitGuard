import { trackedColor, typeColor, countryColor } from '../data/leoObjects'

const LEGENDS = {
  lastTracked: {
    title: 'Last Tracked',
    items: [
      { label: 'Tracked in the last day', color: trackedColor.day },
      { label: 'Tracked in the last week', color: trackedColor.week },
      { label: 'Untracked in the last week', color: trackedColor.stale },
    ],
  },
  objectType: {
    title: 'Object Type',
    items: [
      { label: 'Active satellite', color: typeColor.active },
      { label: 'Debris', color: typeColor.debris },
      { label: 'Rocket body', color: typeColor.rocket_body },
    ],
  },
  country: {
    title: 'Country of Origin',
    items: Object.entries(countryColor).map(([label, color]) => ({ label, color })),
  },
  perigee: {
    title: 'Perigee (km)',
    items: [
      { label: 'Low altitude (~300 km)', color: '#F0475A' },
      { label: 'High altitude (~1700 km)', color: '#3FD7E8' },
    ],
  },
  period: {
    title: 'Orbital Period',
    items: [
      { label: 'Short (~88 min)', color: '#3ED598' },
      { label: 'Long (~133 min)', color: '#9B7EDE' },
    ],
  },
  inclination: {
    title: 'Inclination',
    items: [
      { label: 'Low (~0°)', color: '#F2C94C' },
      { label: 'High (~180°)', color: '#3FD7E8' },
    ],
  },
}

export default function LeoLegend({ viewMode }) {
  const legend = LEGENDS[viewMode] ?? LEGENDS.lastTracked
  return (
    <div className="panel absolute right-3 top-3 w-52 p-3">
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">{legend.title}</div>
      <div className="space-y-1.5">
        {legend.items.map((item) => (
          <div key={item.label} className="flex items-center gap-2 text-[11px] text-ink-muted">
            <span className="h-2 w-2 shrink-0 rounded-sm" style={{ backgroundColor: item.color }} />
            {item.label}
          </div>
        ))}
      </div>
    </div>
  )
}
