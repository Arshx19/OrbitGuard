import { NavLink } from 'react-router-dom'
import { Radar, ListTree, Wrench, BarChart3, Database, Settings, Search, Satellite, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { triggerRefresh } from '../api/orbitguard'

const railItems = [
  { icon: Radar, label: 'Live' },
  { icon: ListTree, label: 'Filters' },
  { icon: Wrench, label: 'Maneuvers' },
  { icon: BarChart3, label: 'Analytics' },
  { icon: Database, label: 'Data' },
  { icon: Settings, label: 'Settings' },
]

const navItems = [
  { to: '/', label: 'LIVE MONITOR' },
  { to: '/conjunction/CONJ-001', label: 'CONJUNCTIONS' },
  { to: '/maneuver/CONJ-001', label: 'MANEUVERS' },
  { to: '/risk/CONJ-001', label: 'ANALYTICS' },
  { to: '/', label: 'DATA' },
]

function Clock() {
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  const utc = now.toUTCString().split(' ')[4]
  return <span className="font-mono text-ink-muted text-xs">{utc} UTC</span>
}

export function IconRail() {
  return (
    <div className="hidden md:flex w-14 shrink-0 flex-col items-center gap-1 border-r border-line bg-void-700 py-4">
      {railItems.map(({ icon: Icon, label }) => (
        <button
          key={label}
          title={label}
          className="group flex h-10 w-10 items-center justify-center rounded-lg text-ink-faint transition hover:bg-void-500 hover:text-signal"
        >
          <Icon size={18} strokeWidth={1.75} />
        </button>
      ))}
    </div>
  )
}

export default function Navbar() {
  const [isRefreshing, setIsRefreshing] = useState(false)

  const handleManualRefresh = async () => {
    setIsRefreshing(true)
    await triggerRefresh()
    setTimeout(() => {
      setIsRefreshing(false)
      window.dispatchEvent(new CustomEvent('orbitguard-data-refreshed'))
    }, 600)
  }

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-line bg-void-700 px-5">
      <div className="flex items-center gap-8">
        <div className="flex items-center gap-2">
          <Satellite size={18} className="text-signal" strokeWidth={2} />
          <span className="font-display text-sm font-semibold tracking-wide">ORBITGUARD AI</span>
        </div>
        <nav className="hidden lg:flex items-center gap-6">
          {navItems.map((item) => (
            <NavLink
              key={item.label}
              to={item.to}
              className={({ isActive }) =>
                `text-xs font-medium tracking-wide transition ${
                  isActive ? 'text-ink' : 'text-ink-faint hover:text-ink-muted'
                }`
              }
              end
            >
              {item.label.toUpperCase()}
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="flex items-center gap-4">
        <div className="hidden md:flex items-center gap-2 rounded-md border border-line bg-void-600 px-3 py-1.5">
          <Search size={13} className="text-ink-faint" />
          <input
            placeholder="Search satellite / NORAD ID..."
            className="w-44 bg-transparent text-xs text-ink placeholder:text-ink-faint focus:outline-none"
          />
        </div>
        <button
          onClick={handleManualRefresh}
          disabled={isRefreshing}
          title="Trigger live catalog & conjunction re-screening"
          className="flex items-center gap-1.5 rounded-md border border-line bg-void-600 px-2.5 py-1 text-xs text-ink-muted transition hover:bg-void-500 hover:text-ink disabled:opacity-50"
        >
          <RefreshCw size={12} className={isRefreshing ? 'animate-spin text-signal' : ''} />
          <span className="hidden sm:inline font-mono text-[11px]">{isRefreshing ? 'SYNCING...' : 'LIVE REFRESH'}</span>
        </button>
        <Clock />
        <div className="flex items-center gap-1.5">
          <span className="live-dot h-1.5 w-1.5 rounded-full bg-risk-green" />
          <span className="text-xs font-medium text-risk-green">AUTO-SYNC ACTIVE</span>
        </div>
      </div>
    </header>
  )
}
