import { createContext, useContext, useState, useMemo } from 'react'

const SettingsContext = createContext(null)

export function SettingsProvider({ children }) {
  const [units, setUnits] = useState('km') // 'km' | 'mi'
  const [reducedMotion, setReducedMotion] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)

  const value = useMemo(
    () => ({
      units,
      toggleUnits: () => setUnits((u) => (u === 'km' ? 'mi' : 'km')),
      reducedMotion,
      toggleReducedMotion: () => setReducedMotion((r) => !r),
      settingsOpen,
      openSettings: () => setSettingsOpen(true),
      closeSettings: () => setSettingsOpen(false),
    }),
    [units, reducedMotion, settingsOpen]
  )

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
}

export function useSettings() {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider')
  return ctx
}

const KM_TO_MI = 0.621371

export function formatDistanceKm(km, units) {
  if (units === 'mi') return `${(km * KM_TO_MI).toFixed(2)} mi`
  return `${km.toFixed(2)} km`
}

export function formatDistanceM(m, units) {
  if (units === 'mi') return `${(m * 0.000621371).toFixed(3)} mi`
  return `${m} m`
}
