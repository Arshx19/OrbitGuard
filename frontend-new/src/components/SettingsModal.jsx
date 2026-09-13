import { X } from 'lucide-react'
import { useSettings } from '../context/SettingsContext'

export default function SettingsModal() {
  const { settingsOpen, closeSettings, units, toggleUnits, reducedMotion, toggleReducedMotion } = useSettings()
  if (!settingsOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={closeSettings}>
      <div
        className="panel w-80 p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <span className="font-display text-sm font-semibold text-ink">Settings</span>
          <button onClick={closeSettings} className="text-ink-faint hover:text-ink">
            <X size={16} />
          </button>
        </div>

        <div className="space-y-4">
          <ToggleRow
            label="Distance units"
            value={units === 'km' ? 'Kilometers' : 'Miles'}
            onClick={toggleUnits}
          />
          <ToggleRow
            label="Reduced motion"
            value={reducedMotion ? 'On' : 'Off'}
            onClick={toggleReducedMotion}
          />
        </div>

        <p className="mt-5 border-t border-line pt-3 text-[11px] leading-relaxed text-ink-faint">
          Reduced motion pauses the orbit globe's auto-rotation everywhere in the app.
        </p>
      </div>
    </div>
  )
}

function ToggleRow({ label, value, onClick }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-ink-muted">{label}</span>
      <button
        onClick={onClick}
        className="rounded-md border border-line bg-void-600 px-3 py-1.5 font-mono text-signal transition hover:bg-void-500"
      >
        {value}
      </button>
    </div>
  )
}
