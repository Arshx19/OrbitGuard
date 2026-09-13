import { useState, useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { listSatellites } from '../api/orbitguard'

const COLUMNS = [
  { key: 'name', label: 'Name' },
  { key: 'noradId', label: 'NORAD ID' },
  { key: 'type', label: 'Object Type' },
  { key: 'designator', label: 'Designator' },
  { key: 'inclination', label: 'Inclination (°)' },
  { key: 'meanMotion', label: 'Mean Motion (rev/day)' },
  { key: 'maneuverable', label: 'Propulsion' },
]

export default function DataPage() {
  const [searchParams] = useSearchParams()
  const [query, setQuery] = useState(searchParams.get('q') ?? '')
  const [sortKey, setSortKey] = useState('name')
  const [sortDir, setSortDir] = useState('asc')
  const [page, setPage] = useState(1)
  const [catalog, setCatalog] = useState([])
  const [totalTracked, setTotalTracked] = useState(0)
  const [loading, setLoading] = useState(true)
  const pageSize = 25

  useEffect(() => {
    async function loadCatalog() {
      try {
        const res = await listSatellites(3000)
        if (res && res.satellites) {
          const mapped = res.satellites.map((s) => ({
            id: s.satellite_number,
            name: s.name,
            noradId: s.satellite_number,
            type: s.object_type || 'Active Satellite',
            designator: s.international_designator || 'N/A',
            inclination: s.inclination_deg ? s.inclination_deg.toFixed(2) : '0.00',
            meanMotion: s.mean_motion_orbits_per_day ? s.mean_motion_orbits_per_day.toFixed(4) : '0.0000',
            maneuverable: s.maneuverable ? 'Maneuverable' : 'Passive / Debris',
          }))
          setCatalog(mapped)
          setTotalTracked(res.total_tracked || mapped.length)
        }
      } catch (e) {
        console.warn('Error loading CelesTrak catalog:', e)
      } finally {
        setLoading(false)
      }
    }
    loadCatalog()
  }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    let rows = catalog
    if (q) rows = rows.filter((o) => o.name.toLowerCase().includes(q) || String(o.noradId).includes(q))
    rows = [...rows].sort((a, b) => {
      const av = a[sortKey] ?? ''
      const bv = b[sortKey] ?? ''
      const cmp = typeof av === 'string' ? av.localeCompare(bv) : av - bv
      return sortDir === 'asc' ? cmp : -cmp
    })
    return rows
  }, [query, sortKey, sortDir, catalog])

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const page_ = Math.min(page, totalPages)
  const rows = filtered.slice((page_ - 1) * pageSize, page_ * pageSize)

  function handleSort(key) {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
    setPage(1)
  }

  return (
    <div className="space-y-4 p-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-lg font-semibold text-ink">CelesTrak Orbital Catalog</h1>
          <p className="mt-1 text-xs text-ink-faint">
            Live CelesTrak TLE Catalog — {totalTracked || catalog.length} active objects tracked.
          </p>
        </div>
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setPage(1)
          }}
          placeholder="Search satellite name or NORAD ID..."
          className="w-64 rounded-md border border-line bg-void-600 px-3 py-1.5 text-xs text-ink placeholder:text-ink-faint focus:border-signal/50 focus:outline-none"
        />
      </div>

      {loading ? (
        <div className="p-6 text-xs text-ink-faint animate-pulse">Loading live CelesTrak satellite catalog...</div>
      ) : (
        <>
          <div className="panel overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-[10px] uppercase tracking-wide text-ink-faint">
                  {COLUMNS.map((c) => (
                    <th
                      key={c.key}
                      onClick={() => handleSort(c.key)}
                      className="cursor-pointer select-none px-4 py-2 font-normal hover:text-ink-muted"
                    >
                      {c.label} {sortKey === c.key ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((o) => (
                  <tr key={o.id} className="border-t border-line hover:bg-void-700/50">
                    <td className="px-4 py-2 font-mono text-signal">{o.name}</td>
                    <td className="px-4 py-2 font-mono text-ink-muted">{o.noradId}</td>
                    <td className="px-4 py-2">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${o.type.includes('Debris') ? 'bg-rose-500/20 text-rose-300' : 'bg-emerald-500/20 text-emerald-300'}`}>
                        {o.type}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-ink-muted font-mono">{o.designator}</td>
                    <td className="px-4 py-2 font-mono text-ink-muted">{o.inclination}°</td>
                    <td className="px-4 py-2 font-mono text-ink-muted">{o.meanMotion}</td>
                    <td className="px-4 py-2 text-ink-muted">{o.maneuverable}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between text-xs text-ink-faint">
            <span>
              Page {page_} of {totalPages} ({filtered.length} objects)
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page_ === 1}
                className="rounded border border-line px-3 py-1 disabled:opacity-30"
              >
                Prev
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page_ === totalPages}
                className="rounded border border-line px-3 py-1 disabled:opacity-30"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
