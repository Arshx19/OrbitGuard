// Frontend <-> Backend API contract (spec section 11).
// Connects to Node.js Express server (Port 5000) with fallback to local mock data.

import { stats, conjunctions, getConjunction } from '../data/mockData'

const BASE_URL = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api/v1'

export async function getStats() {
  try {
    const res = await fetch(`${BASE_URL}/satellites`)
    if (res.ok) {
      const data = await res.json()
      const totalSats = data.total_tracked || data.total || (data.satellites ? data.satellites.length : 2847)
      return {
        objectsTracked: totalSats,
        objectsTrackedDelta: '+2.6%',
        activeConjunctions: 4,
        activeConjunctionsDelta: '+6.1%',
        highRiskEvents: 2,
        highRiskEventsDelta: '+25%',
        satellitesMonitored: Math.round(totalSats * 0.45),
        satellitesMonitoredDelta: '+0.3%'
      }
    }
  } catch (e) {
    console.warn("Using fallback data for getStats:", e)
  }
  return Promise.resolve(stats)
}

export async function listConjunctions() {
  try {
    const res = await fetch(`${BASE_URL}/conjunctions`)
    if (res.ok) {
      const data = await res.json()
      const list = Array.isArray(data) ? data : (data.conjunctions || [])
      if (list.length > 0) {
        return list.map((item, idx) => ({
          id: item.id || item.conjunction_id || `CONJ-00${idx+1}`,
          primary: item.satellite1_name || item.primary || 'ISS (ZARYA)',
          primaryType: 'Active Satellite',
          secondary: item.satellite2_name || item.secondary || 'COSMOS DEBRIS #1402',
          secondaryType: 'Debris',
          tca: item.tca || '2026-09-13T04:12:00Z',
          tcaIn: item.tcaIn || '4 hr 12 min',
          minDistanceM: item.miss_distance_km !== undefined ? Math.round(item.miss_distance_km * 1000) : (item.minDistanceM || 420),
          relVelocityKms: item.relative_speed_kms || item.relVelocityKms || 12.4,
          probability: item.probability || 8.7e-2,
          riskScore: item.risk_score || item.riskScore || 94,
          geometry: item.geometry || 'Crossing',
          uncertainty: item.uncertainty || 'High',
          factors: item.factors || [
            { label: 'Minimum separation', pct: 32 },
            { label: 'Relative velocity', pct: 24 },
            { label: 'TCA urgency', pct: 20 },
            { label: 'Orbital geometry', pct: 14 },
            { label: 'Uncertainty', pct: 7 },
            { label: 'Object characteristics', pct: 3 }
          ],
          timeline: item.timeline || [
            { t: 'T-48', hours: -48, distanceKm: 85 },
            { t: 'T-36', hours: -36, distanceKm: 70 },
            { t: 'T-24', hours: -24, distanceKm: 55 },
            { t: 'T-12', hours: -12, distanceKm: 43 },
            { t: 'T-6', hours: -6, distanceKm: 35 },
            { t: 'T-0', hours: 0, distanceKm: item.miss_distance_km || 0.42 }
          ],
          maneuverCandidates: item.maneuverCandidates || [
            { id: 1, deltaV: 0.10, direction: 'Radial', newSeparationKm: 0.60, newRisk: 'ISS (ZARYA) ↔ COSMOS DEBRIS #1402', status: 'REJECT', reason: 'Fixes original conjunction but creates a new unsafe pass at 0.18 km.' },
            { id: 2, deltaV: 0.20, direction: 'Along-track', newSeparationKm: 1.90, newRisk: 'None detected', status: 'REJECT', reason: 'Residual probability still above the safety threshold after re-screening.' },
            { id: 3, deltaV: 0.30, direction: 'Along-track', newSeparationKm: 4.50, newRisk: 'None detected', status: 'SAFE', reason: 'Clears the original event and no new conjunction is introduced on re-screen.' },
            { id: 4, deltaV: 0.50, direction: 'Cross-track', newSeparationKm: 6.10, newRisk: 'None detected', status: 'SAFE', reason: 'Safe, but uses more propellant than candidate #3 for no added margin.' }
          ]
        }))
      }
    }
  } catch (e) {
    console.warn("Using fallback mock data for listConjunctions:", e)
  }
  return Promise.resolve(conjunctions)
}

export async function getConjunctionById(id) {
  try {
    const list = await listConjunctions()
    const item = list.find(c => c.id === id || c.conjunction_id === id)
    if (item) return item
  } catch (e) {
    console.warn("Using fallback data for getConjunctionById:", e)
  }
  return Promise.resolve(getConjunction(id) || conjunctions[0])
}

export async function analyzeRisk(id) {
  try {
    const res = await fetch(`${BASE_URL}/risk/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conjunction_id: id })
    })
    if (res.ok) {
      const data = await res.json()
      const mock = getConjunction(id)
      return {
        riskScore: data.risk_score ?? mock?.riskScore ?? 94,
        factors: data.shap_factors ?? mock?.factors ?? [],
        explanation: data.explanation_summary,
        timeline: mock?.timeline ?? []
      }
    }
  } catch (e) {
    console.warn("Using fallback mock data for analyzeRisk:", e)
  }
  const c = getConjunction(id)
  return Promise.resolve({ riskScore: c?.riskScore, factors: c?.factors, timeline: c?.timeline })
}

export async function optimizeManeuver(id) {
  try {
    const res = await fetch(`${BASE_URL}/maneuver/optimize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conjunction_id: id })
    })
    if (res.ok) {
      const data = await res.json()
      if (data.all_candidates && data.all_candidates.length > 0) {
        return data.all_candidates
      }
    }
  } catch (e) {
    console.warn("Using fallback mock data for optimizeManeuver:", e)
  }
  const c = getConjunction(id)
  return Promise.resolve(c?.maneuverCandidates ?? [])
}

export async function validateManeuver(id, candidateId) {
  try {
    const res = await fetch(`${BASE_URL}/maneuver/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conjunction_id: id, candidate_id: candidateId })
    })
    if (res.ok) {
      const data = await res.json()
      const opt = data.optimal_candidate
      return {
        validated: opt?.is_safe ?? true,
        candidate: opt
      }
    }
  } catch (e) {
    console.warn("Using fallback mock data for validateManeuver:", e)
  }
  const c = getConjunction(id)
  const candidate = c?.maneuverCandidates.find((m) => m.id === candidateId)
  return new Promise((resolve) =>
    setTimeout(() => resolve({ validated: candidate?.status === 'SAFE', candidate }), 900)
  )
}

export const __base = BASE_URL
