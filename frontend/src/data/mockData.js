// Mock data shaped exactly like the /satellites, /conjunctions, /risk/analyze,
// and /maneuver/optimize responses described in the API contract (spec section 11).
// Swap `api/orbitguard.js` for real fetch calls later without touching components.

export const stats = {
  objectsTracked: 2847,
  objectsTrackedDelta: '+2.6%',
  activeConjunctions: 4,
  activeConjunctionsDelta: '+6.1%',
  highRiskEvents: 2,
  highRiskEventsDelta: '+25%',
  satellitesMonitored: 1284,
  satellitesMonitoredDelta: '+0.3%',
}

export const riskLevelMeta = {
  critical: { label: 'Critical', color: '#F0475A' },
  high: { label: 'High', color: '#F5924A' },
  amber: { label: 'Amber', color: '#F2C94C' },
  green: { label: 'Green', color: '#3ED598' },
}

function levelFromScore(score) {
  if (score >= 80) return 'critical'
  if (score >= 55) return 'high'
  if (score >= 30) return 'amber'
  return 'green'
}

export const conjunctions = [
  {
    id: 'CONJ-001',
    primary: 'ISS (ZARYA)',
    primaryType: 'Active Space Station',
    secondary: 'COSMOS DEBRIS #1402',
    secondaryType: 'Debris',
    tca: '2026-09-13T04:12:00Z',
    tcaIn: '4 hr 12 min',
    minDistanceM: 420,
    relVelocityKms: 12.4,
    probability: 8.7e-2,
    riskScore: 94,
    geometry: 'Crossing',
    uncertainty: 'High',
    factors: [
      { label: 'Minimum separation', pct: 32 },
      { label: 'Relative velocity', pct: 24 },
      { label: 'TCA urgency', pct: 20 },
      { label: 'Orbital geometry', pct: 14 },
      { label: 'Uncertainty', pct: 7 },
      { label: 'Object characteristics', pct: 3 },
    ],
    timeline: [
      { t: 'T-48', hours: -48, distanceKm: 85 },
      { t: 'T-36', hours: -36, distanceKm: 70 },
      { t: 'T-24', hours: -24, distanceKm: 55 },
      { t: 'T-12', hours: -12, distanceKm: 43 },
      { t: 'T-6', hours: -6, distanceKm: 35 },
      { t: 'T-0', hours: 0, distanceKm: 0.42 },
    ],
    maneuverCandidates: [
      { id: 1, deltaV: 0.10, direction: 'Radial', newSeparationKm: 0.60, newRisk: 'ISS (ZARYA) ↔ COSMOS DEBRIS #1402', status: 'REJECT', reason: 'Fixes original conjunction but creates a new unsafe pass at 0.18 km.' },
      { id: 2, deltaV: 0.20, direction: 'Along-track', newSeparationKm: 1.90, newRisk: 'None detected', status: 'REJECT', reason: 'Residual probability still above the safety threshold after re-screening.' },
      { id: 3, deltaV: 0.30, direction: 'Along-track', newSeparationKm: 4.50, newRisk: 'None detected', status: 'SAFE', reason: 'Clears the original event and no new conjunction is introduced on re-screen.' },
      { id: 4, deltaV: 0.50, direction: 'Cross-track', newSeparationKm: 6.10, newRisk: 'None detected', status: 'SAFE', reason: 'Safe, but uses more propellant than candidate #3 for no added margin.' },
    ],
  },
  {
    id: 'CONJ-002',
    primary: 'STARLINK-1007',
    primaryType: 'Active Constellation',
    secondary: 'FENGYUN DEBRIS #312',
    secondaryType: 'Debris',
    tca: '2026-09-13T07:40:00Z',
    tcaIn: '7 hr 40 min',
    minDistanceM: 1200,
    relVelocityKms: 9.8,
    probability: 3.2e-3,
    riskScore: 78,
    geometry: 'Near-crossing',
    uncertainty: 'Moderate',
    factors: [
      { label: 'Minimum separation', pct: 26 },
      { label: 'Relative velocity', pct: 22 },
      { label: 'TCA urgency', pct: 18 },
      { label: 'Orbital geometry', pct: 19 },
      { label: 'Uncertainty', pct: 11 },
      { label: 'Object characteristics', pct: 4 },
    ],
    timeline: [
      { t: 'T-48', hours: -48, distanceKm: 140 },
      { t: 'T-36', hours: -36, distanceKm: 110 },
      { t: 'T-24', hours: -24, distanceKm: 80 },
      { t: 'T-12', hours: -12, distanceKm: 40 },
      { t: 'T-6', hours: -6, distanceKm: 12 },
      { t: 'T-0', hours: 0, distanceKm: 1.2 },
    ],
    maneuverCandidates: [
      { id: 1, deltaV: 0.08, direction: 'Radial', newSeparationKm: 2.4, newRisk: 'None detected', status: 'SAFE', reason: 'Small correction is sufficient; no new conjunctions on re-screen.' },
      { id: 2, deltaV: 0.15, direction: 'Along-track', newSeparationKm: 3.9, newRisk: 'None detected', status: 'SAFE', reason: 'Larger margin, higher propellant cost than candidate #1.' },
    ],
  },
  {
    id: 'CONJ-003',
    primary: 'WEATHER-SAT B',
    primaryType: 'Earth Observation',
    secondary: 'SL-12 ROCKET BODY',
    secondaryType: 'Rocket Body',
    tca: '2026-09-13T18:00:00Z',
    tcaIn: '18 hr 00 min',
    minDistanceM: 5000,
    relVelocityKms: 6.2,
    probability: 6.8e-4,
    riskScore: 45,
    geometry: 'Parallel',
    uncertainty: 'Low',
    factors: [
      { label: 'Minimum separation', pct: 18 },
      { label: 'Relative velocity', pct: 15 },
      { label: 'TCA urgency', pct: 12 },
      { label: 'Orbital geometry', pct: 10 },
      { label: 'Uncertainty', pct: 5 },
      { label: 'Object characteristics', pct: 40 },
    ],
    timeline: [
      { t: 'T-48', hours: -48, distanceKm: 210 },
      { t: 'T-36', hours: -36, distanceKm: 180 },
      { t: 'T-24', hours: -24, distanceKm: 150 },
      { t: 'T-12', hours: -12, distanceKm: 90 },
      { t: 'T-6', hours: -6, distanceKm: 40 },
      { t: 'T-0', hours: 0, distanceKm: 5.0 },
    ],
    maneuverCandidates: [],
  },
  {
    id: 'CONJ-004',
    primary: 'ENVISAT',
    primaryType: 'Defunct Satellite',
    secondary: 'ISS (ZARYA)',
    secondaryType: 'Active Space Station',
    tca: '2026-09-14T02:30:00Z',
    tcaIn: '26 hr 30 min',
    minDistanceM: 25000,
    relVelocityKms: 2.1,
    probability: 1.2e-5,
    riskScore: 12,
    geometry: 'Parallel',
    uncertainty: 'Low',
    factors: [
      { label: 'Minimum separation', pct: 10 },
      { label: 'Relative velocity', pct: 10 },
      { label: 'TCA urgency', pct: 5 },
      { label: 'Orbital geometry', pct: 5 },
      { label: 'Uncertainty', pct: 5 },
      { label: 'Object characteristics', pct: 65 },
    ],
    timeline: [
      { t: 'T-48', hours: -48, distanceKm: 300 },
      { t: 'T-36', hours: -36, distanceKm: 250 },
      { t: 'T-24', hours: -24, distanceKm: 200 },
      { t: 'T-12', hours: -12, distanceKm: 120 },
      { t: 'T-6', hours: -6, distanceKm: 60 },
      { t: 'T-0', hours: 0, distanceKm: 25.0 },
    ],
    maneuverCandidates: [],
  },
]

export function getConjunction(id) {
  return conjunctions.find((c) => String(c.id) === String(id))
}

export { levelFromScore }
