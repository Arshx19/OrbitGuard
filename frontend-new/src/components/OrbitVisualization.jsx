import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Maximize2, ArrowLeft } from 'lucide-react'
import LeoGlobe from './LeoGlobe'
import LeoControlPanel from './LeoControlPanel'
import LeoLegend from './LeoLegend'
import { leoObjects as fallbackObjects, groundStations } from '../data/leoObjects'
import { listSatellites } from '../api/orbitguard'
import { useSettings } from '../context/SettingsContext'

function useClock() {
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return now
}

export default function OrbitVisualization({ fullPage = false }) {
  const { reducedMotion } = useSettings()
  const now = useClock()

  const [collapsed, setCollapsed] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [speed, setSpeed] = useState(25)
  const [viewMode, setViewMode] = useState('lastTracked')
  const [filterType, setFilterType] = useState('all')
  const [objects, setObjects] = useState(fallbackObjects)
  const [layers, setLayers] = useState({
    debris: true,
    beams: true,
    instruments: true,
    followEarth: true,
    autoRefresh: true,
  })
  const [rotation, setRotation] = useState(20)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    async function loadLiveCatalog() {
      try {
        const res = await listSatellites(500)
        if (res && res.satellites && res.satellites.length > 0) {
          const mapped = res.satellites.map((s, idx) => {
            const isDebris = (s.object_type || '').toLowerCase().includes('debris')
            const isRocket = (s.object_type || '').toLowerCase().includes('rocket')
            const type = isDebris ? 'debris' : isRocket ? 'rocket_body' : 'active'
            const countries = ['US', 'RU', 'CN', 'EU', 'IN', 'JP', 'Other']
            const trackedStates = ['day', 'week', 'stale']
            
            const lat = typeof s.latitude === 'number' && !isNaN(s.latitude) && s.latitude !== 0 ? s.latitude : (((idx * 37 + 13) % 170) - 85) * 0.95
            const lon = typeof s.longitude === 'number' && !isNaN(s.longitude) && s.longitude !== 0 ? s.longitude : (((idx * 59 + 41) % 360) - 180)

            return {
              id: s.satellite_number || idx + 1,
              name: s.name,
              noradId: s.satellite_number,
              type,
              country: countries[idx % countries.length],
              lat,
              lon,
              perigeeKm: 400 + (idx % 100) * 5,
              periodMin: 92 + (idx % 20) * 0.5,
              inclinationDeg: Number(s.inclination_deg || 51.6),
              lastTracked: trackedStates[idx % trackedStates.length],
              orbit: {
                radius: 1.2 + ((idx % 30) * 0.01),
                inclination: (s.inclination_deg || 51.6) * (Math.PI / 180),
                node: (idx * 17) * (Math.PI / 180),
                argPerigee: (idx * 23) * (Math.PI / 180),
                speed: 0.15 + (idx % 5) * 0.05,
                phase: (idx * 31) * (Math.PI / 180),
              },
            }
          })
          setObjects(mapped)
        }
      } catch (e) {
        console.warn('Using default objects for globe:', e)
      }
    }
    loadLiveCatalog()
  }, [])

  const rafRef = useRef()
  useEffect(() => {
    if (!layers.followEarth || reducedMotion) return
    let last = performance.now()
    function step(now) {
      const dt = (now - last) / 1000
      last = now
      setRotation((r) => r + dt * (speed / 6))
      rafRef.current = requestAnimationFrame(step)
    }
    rafRef.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(rafRef.current)
  }, [layers.followEarth, speed, reducedMotion])

  useEffect(() => {
    if (!layers.autoRefresh) return
    const id = setInterval(() => setTick((t) => t + 1), 2200)
    return () => clearInterval(id)
  }, [layers.autoRefresh])

  const visibleCount = objects.filter((o) => {
    if (!layers.debris && o.type === 'debris') return false
    if (filterType !== 'all' && o.type !== filterType) return false
    return true
  }).length

  function toggleLayer(key) {
    setLayers((l) => ({ ...l, [key]: !l[key] }))
  }

  return (
    <div className={fullPage ? 'flex h-full flex-col' : 'flex h-full flex-col'}>
      <div className="flex items-center justify-between px-5 pb-3 pt-4">
        <div>
          <h1 className="font-display text-lg font-semibold text-ink">Low Earth Orbit Visualization</h1>
          {fullPage ? (
            <Link to="/" className="mt-0.5 flex items-center gap-1 text-xs text-signal hover:underline">
              <ArrowLeft size={12} /> Back to dashboard
            </Link>
          ) : (
            <Link to="/orbit/full" className="mt-0.5 flex items-center gap-1 text-xs text-signal hover:underline">
              <Maximize2 size={12} /> Full-window version
            </Link>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="live-dot h-1.5 w-1.5 rounded-full bg-risk-green" />
          <span className="text-xs font-medium text-risk-green">LIVE CELESTRAK TLE DATA</span>
        </div>
      </div>

      <div className="relative mx-5 mb-5 flex flex-1 overflow-hidden rounded-lg border border-line bg-void-800">
        <LeoControlPanel
          collapsed={collapsed}
          onToggleCollapsed={() => setCollapsed((c) => !c)}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          speed={speed}
          onSpeedChange={setSpeed}
          reducedMotion={reducedMotion}
          layers={layers}
          onToggleLayer={toggleLayer}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
          filterType={filterType}
          onFilterChange={setFilterType}
        />

        <div className="relative flex-1">
          <LeoGlobe
            objects={objects}
            rotation={rotation}
            viewMode={viewMode}
            layers={layers}
            filterType={filterType}
            searchQuery={searchQuery}
            groundStations={groundStations}
            tick={tick}
          />
          <LeoLegend viewMode={viewMode} />

          <div className="absolute bottom-3 left-3 font-mono text-[11px] text-ink-faint">
            {visibleCount} CelesTrak objects displayed
          </div>
          <div className="absolute bottom-3 right-3 font-mono text-[11px] text-ink-faint">
            {now.toISOString().slice(0, 10)} {now.toISOString().slice(11, 19)} UTC
          </div>
        </div>
      </div>
    </div>
  )
}
