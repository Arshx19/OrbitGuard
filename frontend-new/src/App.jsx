import { Routes, Route, Outlet } from 'react-router-dom'
import Navbar, { IconRail } from './components/Navbar'
import SettingsModal from './components/SettingsModal'
import { SettingsProvider } from './context/SettingsContext'
import OrbitVisualization from './components/OrbitVisualization'
import Dashboard from './pages/Dashboard'
import ConjunctionsPage from './pages/ConjunctionsPage'
import ManeuversPage from './pages/ManeuversPage'
import AnalyticsPage from './pages/AnalyticsPage'
import DataPage from './pages/DataPage'
import Conjunction from './pages/Conjunction'
import RiskAnalysis from './pages/RiskAnalysis'
import ManeuverSimulator from './pages/ManeuverSimulator'

function Layout() {
  return (
    <div className="flex h-screen flex-col bg-void-800">
      <Navbar />
      <div className="flex flex-1 overflow-hidden">
        <IconRail />
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
      <SettingsModal />
    </div>
  )
}

export default function App() {
  return (
    <SettingsProvider>
      <Routes>
        {/* Full-window globe: no navbar/sidebar chrome, matching the reference's own "Full-window version" link */}
        <Route path="/orbit/full" element={<div className="h-screen bg-void-800"><OrbitVisualization fullPage /></div>} />

        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/conjunctions" element={<ConjunctionsPage />} />
          <Route path="/maneuvers" element={<ManeuversPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/data" element={<DataPage />} />
          <Route path="/conjunction/:id" element={<Conjunction />} />
          <Route path="/risk/:id" element={<RiskAnalysis />} />
          <Route path="/maneuver/:id" element={<ManeuverSimulator />} />
        </Route>
      </Routes>
    </SettingsProvider>
  )
}
