import { Routes, Route } from 'react-router-dom'
import Navbar, { IconRail } from './components/Navbar'
import Dashboard from './pages/Dashboard'
import Conjunction from './pages/Conjunction'
import RiskAnalysis from './pages/RiskAnalysis'
import ManeuverSimulator from './pages/ManeuverSimulator'

export default function App() {
  return (
    <div className="flex h-screen flex-col bg-void-800">
      <Navbar />
      <div className="flex flex-1 overflow-hidden">
        <IconRail />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/conjunction/:id" element={<Conjunction />} />
            <Route path="/risk/:id" element={<RiskAnalysis />} />
            <Route path="/maneuver/:id" element={<ManeuverSimulator />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
