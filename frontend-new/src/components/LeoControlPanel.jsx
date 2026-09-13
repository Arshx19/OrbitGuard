import { ChevronLeft, ChevronRight } from 'lucide-react'

const VIEWS = [
  { id: 'lastTracked', label: 'Last Tracked' },
  { id: 'perigee', label: 'Perigee' },
  { id: 'period', label: 'Period' },
  { id: 'inclination', label: 'Inclination' },
  { id: 'country', label: 'Country of Origin' },
  { id: 'objectType', label: 'Object Type' },
]

const FILTERS = [
  { id: 'all', label: 'All objects' },
  { id: 'active', label: 'Active satellites' },
  { id: 'debris', label: 'Debris' },
  { id: 'rocket_body', label: 'Rocket bodies' },
]

export default function LeoControlPanel({
  collapsed,
  onToggleCollapsed,
  searchQuery,
  onSearchChange,
  speed,
  onSpeedChange,
  reducedMotion,
  layers,
  onToggleLayer,
  viewMode,
  onViewModeChange,
  filterType,
  onFilterChange,
}) {
  if (collapsed) {
    return (
      <button
        onClick={onToggleCollapsed}
        className="flex h-full w-8 shrink-0 items-center justify-center border-r border-line bg-void-700 text-ink-faint transition hover:text-signal"
        title="Show menu"
      >
        <ChevronRight size={14} />
      </button>
    )
  }

  return (
    <div className="flex h-full w-60 shrink-0 flex-col overflow-y-auto border-r border-line bg-void-700 text-xs">
      <div className="space-y-3 border-b border-line p-3">
        <label className="block">
          <span className="mb-1 block text-[10px] uppercase tracking-wide text-ink-faint">Search</span>
          <input
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Enter a satellite name"
            className="w-full rounded border border-line bg-void-600 px-2 py-1.5 text-ink placeholder:text-ink-faint focus:border-signal/50 focus:outline-none"
          />
        </label>

        <label className="block">
          <div className="mb-1 flex items-center justify-between text-[10px] uppercase tracking-wide text-ink-faint">
            <span>Speed</span>
            <span className="font-mono text-ink-muted">{speed}</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={speed}
            disabled={reducedMotion}
            onChange={(e) => onSpeedChange(Number(e.target.value))}
            className="w-full accent-signal disabled:opacity-40"
          />
          {reducedMotion && <p className="mt-1 text-[10px] text-ink-faint">Paused — reduced motion is on in Settings.</p>}
        </label>

        <Checkbox label="Debris" checked={layers.debris} onChange={() => onToggleLayer('debris')} />
        <Checkbox label="Beams" checked={layers.beams} onChange={() => onToggleLayer('beams')} />
        <Checkbox label="Instruments" checked={layers.instruments} onChange={() => onToggleLayer('instruments')} />
        <Checkbox label="Follow Earth" checked={layers.followEarth} onChange={() => onToggleLayer('followEarth')} />
        <Checkbox label="Auto Refresh" checked={layers.autoRefresh} onChange={() => onToggleLayer('autoRefresh')} />
      </div>

      <div className="border-b border-line p-3">
        <div className="mb-1.5 text-[10px] uppercase tracking-wide text-ink-faint">Views</div>
        <div className="space-y-0.5">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              onClick={() => onViewModeChange(v.id)}
              className={`block w-full rounded px-2 py-1.5 text-left transition ${
                viewMode === v.id ? 'bg-signal/15 text-signal' : 'text-ink-muted hover:bg-void-500'
              }`}
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>

      <div className="p-3">
        <div className="mb-1.5 text-[10px] uppercase tracking-wide text-ink-faint">Filters</div>
        <select
          value={filterType}
          onChange={(e) => onFilterChange(e.target.value)}
          className="w-full rounded border border-line bg-void-600 px-2 py-1.5 text-ink focus:border-signal/50 focus:outline-none"
        >
          {FILTERS.map((f) => (
            <option key={f.id} value={f.id}>
              {f.label}
            </option>
          ))}
        </select>
      </div>

      <button
        onClick={onToggleCollapsed}
        className="mt-auto flex items-center justify-center gap-1.5 border-t border-line py-2.5 text-ink-faint transition hover:bg-void-500 hover:text-ink-muted"
      >
        <ChevronLeft size={13} />
        Hide menu
      </button>
    </div>
  )
}

function Checkbox({ label, checked, onChange }) {
  return (
    <label className="flex cursor-pointer items-center justify-between py-0.5">
      <span className="text-ink-muted">{label}</span>
      <input type="checkbox" checked={checked} onChange={onChange} className="accent-signal" />
    </label>
  )
}
