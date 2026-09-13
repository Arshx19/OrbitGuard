import { NavLink, useNavigate } from 'react-router-dom'
import { Radar, ListTree, Wrench, BarChart3, Database, Settings, Search, Satellite } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSettings } from '../context/SettingsContext'

const railItems = [
  { icon: Radar, label: 'Live', to: '/' },
  { icon: ListTree, label: 'Conjunctions', to: '/conjunctions' },
  { icon: Wrench, label: 'Maneuvers', to: '/maneuvers' },
  { icon: BarChart3, label: 'Analytics', to: '/analytics' },
  { icon: Database, label: 'Data', to: '/data' },
]

const navItems = [
  { to: '/', label: 'Live Monitor' },
  { to: '/conjunctions', label: 'Conjunctions' },
  { to: '/maneuvers', label: 'Maneuvers' },
  { to: '/analytics', label: 'Analytics' },
  { to: '/data', label: 'Data' },
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
  const { openSettings } = useSettings()
  return (
    <div className="hidden md:flex w-14 shrink-0 flex-col items-center gap-1 border-r border-line bg-void-700 py-4">
      {railItems.map(({ icon: Icon, label, to }) => (
        <NavLink
          key={label}
          to={to}
          end={to === '/'}
          title={label}
          className={({ isActive }) =>
            `group flex h-10 w-10 items-center justify-center rounded-lg transition hover:bg-void-500 hover:text-signal ${
              isActive ? 'bg-void-500 text-signal' : 'text-ink-faint'
            }`
          }
        >
          <Icon size={18} strokeWidth={1.75} />
        </NavLink>
      ))}
      <button
        onClick={openSettings}
        title="Settings"
        className="mt-auto flex h-10 w-10 items-center justify-center rounded-lg text-ink-faint transition hover:bg-void-500 hover:text-signal"
      >
        <Settings size={18} strokeWidth={1.75} />
      </button>
    </div>
  )
}

export default function Navbar() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')

  function handleSearchKeyDown(e) {
    if (e.key === 'Enter' && query.trim()) {
      navigate(`/data?q=${encodeURIComponent(query.trim())}`)
    }
  }

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-line bg-void-700 px-5">
      <div className="flex items-center gap-8">
        <NavLink to="/" className="flex items-center gap-2">
          <Satellite size={18} className="text-signal" strokeWidth={2} />
          <span className="font-display text-sm font-semibold tracking-wide">ORBITGUARD AI</span>
        </NavLink>
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
              end={item.to === '/'}
            >
              {item.label.toUpperCase()}
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="flex items-center gap-5">
        <div className="hidden md:flex items-center gap-2 rounded-md border border-line bg-void-600 px-3 py-1.5">
          <Search size={13} className="text-ink-faint" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            placeholder="Search satellite / NORAD ID... (Enter)"
            className="w-56 bg-transparent text-xs text-ink placeholder:text-ink-faint focus:outline-none"
          />
        </div>
        <Clock />
        <div className="flex items-center gap-1.5">
          <span className="live-dot h-1.5 w-1.5 rounded-full bg-risk-green" />
          <span className="text-xs font-medium text-risk-green">SYSTEM ONLINE</span>
        </div>
      </div>
    </header>
  )
}
