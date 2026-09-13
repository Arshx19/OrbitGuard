# ORBITGUARD AI — Frontend

Operator dashboard for explainable AI-assisted space debris collision detection
and avoidance, built from the project's Frontend Specification.

## Stack
React + Vite, Tailwind CSS, Recharts, react-router-dom, lucide-react icons.

## Getting started
```bash
npm install
npm run dev
```
Open the printed local URL (default `http://localhost:5173`).

## Structure
```
src/
  api/orbitguard.js       -> API contract (mocked). Point at FastAPI backend later.
  context/SettingsContext -> global units (km/mi) + reduced-motion, opened from the icon rail.
  data/mockData.js        -> Sample conjunctions/risk/maneuver data.
  data/leoObjects.js       -> Mock tracked-object catalog + ground stations for the globe.
  components/
    Navbar / IconRail      -> top bar + left icon rail, both fully routed.
    OrbitVisualization      -> the LEO tracking globe (search, speed, layers, views, filters).
    LeoGlobe / LeoControlPanel / LeoLegend -> pieces of the globe view.
    ConjunctionList, RiskScore, RiskFactors, RiskTimeline,
    ManeuverTable, ManeuverViewer, ValidationPanel, SettingsModal.
  pages/
    Dashboard.jsx          /              LEO tracking globe (home)
    ConjunctionsPage.jsx   /conjunctions  full prioritized event queue
    ManeuversPage.jsx      /maneuvers     picker for events needing a maneuver
    AnalyticsPage.jsx      /analytics     risk/catalog trend charts
    DataPage.jsx           /data          searchable/sortable object catalog
    Conjunction.jsx        /conjunction/:id
    RiskAnalysis.jsx       /risk/:id
    ManeuverSimulator.jsx  /maneuver/:id
    (standalone, no chrome) /orbit/full   full-window globe
```

## What's interactive right now
- **Top navbar & icon rail** route to real pages (Live Monitor, Conjunctions, Maneuvers,
  Analytics, Data) and highlight the active one.
- **Navbar search box**: type a name/NORAD ID and press Enter — jumps to the Data page
  pre-filtered to that query.
- **Globe view (home page)**: search highlights a matching object with a pulsing ring;
  Speed slider drives rotation; Debris/Beams/Instruments/Follow Earth/Auto Refresh
  checkboxes toggle real layers; the six Views switch the dot color-coding; the
  Filters dropdown hides non-matching object types; Hide Menu collapses the sidebar;
  "Full-window version" opens the same globe with no navbar chrome at `/orbit/full`.
- **Settings (gear icon in the rail)**: toggling units (km/mi) updates every distance
  shown across Conjunctions, Conjunction detail, and the Maneuver simulator/validation
  panel. Reduced motion pauses the globe's rotation everywhere.

## Wiring up the real backend
Everything currently reads from `src/data/mockData.js` through
`src/api/orbitguard.js`. Once the FastAPI endpoints from the spec are live
(`/satellites`, `/conjunctions`, `/risk/analyze`, `/maneuver/optimize`,
`/maneuver/validate`), replace the function bodies in `orbitguard.js` with
real `fetch()` calls returning the same shapes — no component changes needed.
Set `VITE_API_BASE_URL` in a `.env` file to point at your backend.

## Demo flow
Dashboard → select the CRITICAL conjunction → Analyze Risk (see the 94/100
score and factor breakdown) → Find Safe Maneuver → see rejected candidates →
select the minimum safe Δv candidate → Validate Maneuver → green
"MANEUVER VALIDATED" result. This matches the recommended demo sequence in
the spec (section 12).
