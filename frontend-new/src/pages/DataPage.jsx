import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { leoObjects, typeColor, trackedColor } from '../data/leoObjects'

const COLUMNS = [
  { key: 'name', label: 'Name' },
  { key: 'noradId', label: 'NORAD ID' },
  { key: 'type', label: 'Type' },
  { key: 'country', label: 'Country' },
  { key: 'perigeeKm', label: 'Perigee (km)' },
  { key: 'periodMin', label: 'Period (min)' },
  { key: 'inclinationDeg', label: 'Inclination (°)' },
  { key: 'lastTracked', label: 'Last tracked' },
]

export default function DataPage() {
  const [searchParams] = useSearchParams()
  const [query, setQuery] = useState(searchParams.get('q') ?? '')
  const [sortKey, setSortKey] = useState('name')
  const [sortDir, setSortDir] = useState('asc')
  const [page, setPage] = useState(1)
  const pageSize = 20

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    let rows = leoObjects
    if (q) rows = rows.filter((o) => o.name.toLowerCase().includes(q) || String(o.noradId).includes(q))
    rows = [...rows].sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      const cmp = typeof av === 'string' ? av.localeCompare(bv) : av - bv
      return sortDir === 'asc' ? cmp : -cmp
    })
    return rows
  }, [query, sortKey, sortDir])

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
          <h1 className="font-display text-lg font-semibold text-ink">Data</h1>
          <p className="mt-1 text-xs text-ink-faint">Full tracked object catalog — {leoObjects.length} objects.</p>
        </div>
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setPage(1)
          }}
          placeholder="Search name or NORAD ID..."
          className="w-64 rounded-md border border-line bg-void-600 px-3 py-1.5 text-xs text-ink placeholder:text-ink-faint focus:border-signal/50 focus:outline-none"
        />
      </div>

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
              <tr key={o.id} className="border-t border-line">
                <td className="px-4 py-2 font-mono text-ink">{o.name}</td>
                <td className="px-4 py-2 font-mono text-ink-muted">{o.noradId}</td>
                <td className="px-4 py-2">
                  <span className="inline-flex items-center gap-1.5 text-ink-muted">
                    <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: typeColor[o.type] }} />
                    {o.type.replace('_', ' ')}
                  </span>
                </td>
                <td className="px-4 py-2 text-ink-muted">{o.country}</td>
                <td className="px-4 py-2 font-mono text-ink-muted">{o.perigeeKm}</td>
                <td className="px-4 py-2 font-mono text-ink-muted">{o.periodMin}</td>
                <td className="px-4 py-2 font-mono text-ink-muted">{o.inclinationDeg}</td>
                <td className="px-4 py-2">
                  <span className="inline-flex items-center gap-1.5 text-ink-muted">
                    <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: trackedColor[o.lastTracked] }} />
                    {o.lastTracked}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-xs text-ink-faint">
        <span>
          Page {page_} of {totalPages}
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
    </div>
  )
}
