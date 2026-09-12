// Frontend <-> Backend API contract (spec section 11).
// Every function currently resolves from local mock data. Once the FastAPI
// backend is live, replace each body with a fetch() to the matching endpoint
// and the rest of the app (pages/components) does not need to change.

import { stats, conjunctions, getConjunction } from '../data/mockData'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export async function getStats() {
  // GET /satellites  (aggregated counts)
  return Promise.resolve(stats)
}

export async function listConjunctions() {
  // GET /conjunctions
  return Promise.resolve(conjunctions)
}

export async function getConjunctionById(id) {
  // GET /conjunctions/{id}
  return Promise.resolve(getConjunction(id))
}

export async function analyzeRisk(id) {
  // POST /risk/analyze
  const c = getConjunction(id)
  return Promise.resolve({ riskScore: c?.riskScore, factors: c?.factors, timeline: c?.timeline })
}

export async function optimizeManeuver(id) {
  // POST /maneuver/optimize
  const c = getConjunction(id)
  return Promise.resolve(c?.maneuverCandidates ?? [])
}

export async function validateManeuver(id, candidateId) {
  // POST /maneuver/validate
  const c = getConjunction(id)
  const candidate = c?.maneuverCandidates.find((m) => m.id === candidateId)
  return new Promise((resolve) =>
    setTimeout(() => resolve({ validated: candidate?.status === 'SAFE', candidate }), 900)
  )
}

export const __base = BASE_URL
