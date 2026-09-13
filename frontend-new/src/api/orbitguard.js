// Frontend <-> Backend API contract (spec section 11).
// Connects to Node.js Express server (Port 5000) with fallback to local mock data.
//
// Every function returns data in the shape the pages and components use. When
// the backend answers, the data is the computed result: screened conjunctions,
// collision probabilities, counterfactual risk factors, searched maneuvers. When
// it does not, the local mock data is used so the UI still renders -- and the
// result is tagged `source: 'mock'` so the page can say so instead of passing
// mock numbers off as real ones.
//
// Two things to know when rendering live data:
//
// 1. Zero is a real value. A distant, safe conjunction has a risk score of 0
//    and can have a collision probability that underflows to 0. Fallbacks must
//    use `??`, not `||`: `0 || 94` is 94, which would show a safe event as
//    CRITICAL.
//
// 2. A risk factor can have a negative contribution (direction 'reduces').
//    Large position uncertainty spreads the probability out and can lower it.
//    Use `magnitude` for bar widths.

import { stats, conjunctions, getConjunction, levelFromScore } from '../data/mockData'

const BASE_URL = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api/v1'

// Long enough for a maneuver search with a whole-catalog re-screen.
const REQUEST_TIMEOUT_MS = 25000

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

/** Severity band, preferring the backend's probability-keyed level over bucketing the score. */
export function levelOf(conjunction) {
  return conjunction?.level ?? levelFromScore(conjunction?.riskScore ?? 0)
}

/**
 * Display a collision probability. Values below 1e-12 are shown as a bound:
 * that far into a Gaussian tail the figure is not a credible estimate.
 */
export function formatProbability(pc, digits = 1) {
  if (pc == null || Number.isNaN(pc)) return '—'
  if (pc < 1e-12) return '< 1e-12'
  return pc.toExponential(digits)
}

export function formatTcaIn(hours) {
  if (hours == null || Number.isNaN(hours)) return 'unknown'
  if (hours < 0) return 'elapsed'
  const totalMinutes = Math.round(hours * 60)
  const h = Math.floor(totalMinutes / 60)
  const m = totalMinutes % 60
  if (h === 0) return `${m} min`
  if (m === 0) return `${h} hr`
  return `${h} hr ${m} min`
}

function uncertaintyBand(sigmaAlongTrackKm) {
  if (sigmaAlongTrackKm == null) return 'Unknown'
  if (sigmaAlongTrackKm < 0.75) return 'Low'
  if (sigmaAlongTrackKm < 2.5) return 'Moderate'
  return 'High'
}

// ---------------------------------------------------------------------------
// Mapping from the API contract to the UI shape (pure; exported for testing)
// ---------------------------------------------------------------------------

export function mapFactor(f) {
  const pct = Number(f.contribution_percentage ?? f.pct ?? 0)
  const rounded = Number(pct.toFixed(1))
  return {
    label: f.factor ?? f.label ?? 'Unknown factor',
    pct: rounded,
    magnitude: Math.abs(rounded),
    direction: f.direction ?? 'raises',
    explanation: f.explanation ?? '',
  }
}

export function mapConjunction(item) {
  if (!item) return null
  const sigma = item.uncertainty?.primary_sigma_along_track_km
  return {
    id: item.id,
    primaryId: item.satellite1_id,
    secondaryId: item.satellite2_id,
    primary: item.satellite1_name,
    secondary: item.satellite2_name,
    primaryType: item.satellite1_type ?? 'Unknown',
    secondaryType: item.satellite2_type ?? 'Unknown',
    maneuverable: item.maneuverable,
    simulated: Boolean(item.simulated),
    tca: item.tca,
    tcaHours: item.time_to_tca_hours,
    tcaIn: formatTcaIn(item.time_to_tca_hours),
    minDistanceM: Math.round(Number(item.miss_distance_km) * 1000),
    missDistanceKm: item.miss_distance_km,
    relVelocityKms: item.relative_speed_kms == null ? undefined : Number(item.relative_speed_kms.toFixed(2)),
    probability: item.collision_probability,
    riskScore: Math.round(Number(item.risk_score ?? 0)),
    level: typeof item.risk_level === 'string' ? item.risk_level.toLowerCase() : undefined,
    geometry: item.geometry,
    uncertainty: uncertaintyBand(sigma),
    uncertaintySource: item.uncertainty?.primary_model_source,
    uncertaintyExtrapolated: Boolean(item.uncertainty?.extrapolated),
    narrative: item.narrative,
    timeline: Array.isArray(item.timeline)
      ? item.timeline.map((p) => ({ t: p.t, hours: p.hours, distanceKm: p.distance_km }))
      : [],
  }
}

export function mapCandidate(c) {
  return {
    id: c.candidate_id,
    deltaV: c.delta_v_magnitude_ms,
    direction: c.direction_name,
    leadHours: c.burn_lead_hours,
    newSeparationKm: c.new_miss_distance_km,
    pcBefore: c.pc_before,
    pcAfter: c.pc_after,
    propellantKg: c.propellant_kg,
    postBurnTimeline: Array.isArray(c.post_burn_timeline)
      ? c.post_burn_timeline.map((p) => ({ t: p.t, hours: p.hours, distanceKm: p.distance_km, afterKm: p.after_km }))
      : [],
    newRisk: c.secondary_threats_detected
      ? c.secondary_threat_details?.find((t) => !t.is_original_threat)?.secondary_name ?? 'Original object, later pass'
      : 'None detected',
    status: c.is_safe ? 'SAFE' : 'REJECT',
    recommended: Boolean(c.recommended),
    reason: c.rejection_reason ?? 'Clears the event with no new conjunction introduced on re-screen.',
  }
}

// ---------------------------------------------------------------------------
// Transport
// ---------------------------------------------------------------------------

async function request(path, options = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
      signal: controller.signal,
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } finally {
    clearTimeout(timer)
  }
}

function tagged(value, source) {
  if (value && typeof value === 'object') value.source = source
  return value
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function getStats() {
  try {
    const data = await request('/satellites?limit=0')
    return tagged({
      objectsTracked: data.total_tracked,
      activeConjunctions: data.active_conjunctions,
      highRiskEvents: data.high_risk_events,
      satellitesMonitored: data.satellites_monitored,
      objectsTrackedDelta: '',
      activeConjunctionsDelta: '',
      highRiskEventsDelta: '',
      satellitesMonitoredDelta: '',
    }, 'live')
  } catch (e) {
    console.warn('Using mock data for getStats:', e)
    return tagged({ ...stats }, 'mock')
  }
}

export async function listSatellites(limit = 3000) {
  try {
    const data = await request(`/satellites?limit=${limit}`)
    return tagged(data, 'live')
  } catch (e) {
    console.warn('Error fetching live CelesTrak satellites:', e)
    return tagged({ total_tracked: 0, satellites: [] }, 'mock')
  }
}

export async function listConjunctions() {
  try {
    const data = await request('/conjunctions')
    return tagged((Array.isArray(data) ? data : []).map(mapConjunction), 'live')
  } catch (e) {
    console.warn('Using mock data for listConjunctions:', e)
    return tagged([...conjunctions], 'mock')
  }
}

export async function getConjunctionById(id) {
  try {
    const data = await request(`/conjunctions/${encodeURIComponent(id)}`)
    return tagged(mapConjunction(data), 'live')
  } catch (e) {
    console.warn('Using mock data for getConjunctionById:', e)
    const mock = getConjunction(id)
    return mock ? tagged({ ...mock }, 'mock') : null
  }
}

export async function analyzeRisk(id) {
  try {
    const data = await request('/risk/analyze', {
      method: 'POST',
      body: JSON.stringify({ conjunction_id: id }),
    })
    const conjunction = mapConjunction(data.conjunction)
    return tagged({
      ...(conjunction ?? {}),
      riskScore: Math.round(Number(data.risk_score ?? 0)),
      level: typeof data.risk_level === 'string' ? data.risk_level.toLowerCase() : undefined,
      probability: data.collision_probability,
      factors: (data.shap_factors ?? []).map(mapFactor),
      explanation: data.explanation_summary,
      uncertaintySource: data.uncertainty?.primary_model_source,
      uncertaintyExtrapolated: Boolean(data.uncertainty?.extrapolated),
    }, 'live')
  } catch (e) {
    console.warn('Using mock data for analyzeRisk:', e)
    const c = getConjunction(id)
    return c ? tagged({ ...c }, 'mock') : null
  }
}

export async function optimizeManeuver(id) {
  try {
    const data = await request('/maneuver/optimize', {
      method: 'POST',
      body: JSON.stringify({ conjunction_id: id }),
    })
    const rows = (data.all_candidates ?? []).map(mapCandidate)
    rows.evaluated = data.candidates_evaluated
    rows.recommendedId = data.optimal_candidate?.candidate_id ?? null
    rows.reason = data.reason
    return tagged(rows, 'live')
  } catch (e) {
    console.warn('Using mock data for optimizeManeuver:', e)
    return tagged([...(getConjunction(id)?.maneuverCandidates ?? [])], 'mock')
  }
}

export async function validateManeuver(id, candidateId) {
  try {
    const data = await request('/maneuver/validate', {
      method: 'POST',
      body: JSON.stringify({ conjunction_id: id, candidate_id: candidateId }),
    })
    const validated = data.validated_candidate
    const checks = data.checks
    return tagged({
      validated: Boolean(validated?.is_safe),
      candidate: validated ? mapCandidate(validated) : undefined,
      pcBefore: data.pc_before,
      pcAfter: validated?.pc_after,
      pcAfterBelowFloor: validated?.pc_after != null && validated.pc_after < 1e-12,
      reason: validated?.rejection_reason,
      checks: checks && {
        originalResolved: checks.original_conjunction_resolved,
        trajectoryPropagated: checks.post_maneuver_trajectory_propagated,
        catalogRescreened: checks.catalog_rescreened,
        horizonHours: checks.rescreen_horizon_hours,
        objectsScreened: checks.catalog_objects_screened,
        newConjunctions: checks.new_conjunctions,
      },
    }, 'live')
  } catch (e) {
    console.warn('Using mock data for validateManeuver:', e)
    const c = getConjunction(id)
    const candidate = c?.maneuverCandidates?.find((m) => String(m.id) === String(candidateId))
    const isSafe = candidate ? (candidate.status === 'SAFE' || candidate.is_safe === true) : true
    return new Promise((resolve) =>
      setTimeout(() => resolve(tagged({ validated: isSafe, candidate }, 'mock')), 500)
    )
  }
}

export async function triggerRefresh() {
  try {
    const data = await request('/screening/refresh', { method: 'POST' })
    return tagged(data, 'live')
  } catch (e) {
    console.warn('Error triggering data refresh:', e)
    return null
  }
}

export async function getDecisionExplanation(id, candidateId = null) {
  try {
    const data = await request('/explain/decision', {
      method: 'POST',
      body: JSON.stringify({ conjunction_id: id, candidate_id: candidateId }),
    })
    return tagged(data, 'live')
  } catch (e) {
    console.warn('Using fallback data for getDecisionExplanation:', e)
    const c = getConjunction(id) || conjunctions[0]
    return tagged({
      conjunction_id: id,
      primary_name: c?.primary || 'ISS (ZARYA)',
      secondary_name: c?.secondary || 'COSMOS 2251 DEBRIS',
      tca: c?.tca || '2026-09-14 18:42:00 UTC',
      risk_level: c?.level || 'critical',
      risk_score: c?.riskScore || 94,
      pc_before: c?.probability || 2.31e-4,
      summary: `Conjunction ${id} evaluated. Initial collision risk is ${c?.level || 'critical'} (Pc = ${(c?.probability || 2.31e-4).toExponential(2)}). Recommended action: Execute In-Track Posigrade burn.`,
      questions: {
        why_high_risk: `The predicted collision probability (Pc = ${(c?.probability || 2.31e-4).toExponential(2)}) exceeds the emergency action threshold (1.00e-04). Miss distance is ${c?.minDistanceM || 420} meters under high along-track position covariance.`,
        why_selected_maneuver: `The system selected In-Track Posigrade (+1.20 m/s, 2.40 kg fuel) because it achieves required separation at TCA while minimizing propellant cost, dropping Pc to < 1.00e-12.`,
        why_others_rejected: `Alternative candidate burns across radial and cross-track directions were rejected due to 3.5x higher fuel consumption or insufficient clearance along covariance axis.`,
        post_maneuver_impact: `Executing the burn alters mean anomaly, expanding TCA clearance to 3,850 meters and achieving a > 1e8x risk reduction.`,
        was_validated: `YES — Validated across 133 space catalog objects over a 24-hour horizon with 0 secondary threats detected.`,
      },
      shap_attributions: [
        { feature: 'Miss Distance', impact: 'HIGH', weight_pct: 45.0, description: `Encounter miss distance is ${c?.minDistanceM || 420} m.` },
        { feature: 'Orbit Uncertainty', impact: 'HIGH', weight_pct: 25.0, description: 'Position covariance based on SGP4 TLE uncertainty.' },
        { feature: 'TCA Proximity', impact: 'HIGH', weight_pct: 15.0, description: 'Time to close approach is within critical 24h window.' },
        { feature: 'Relative Speed', impact: 'MEDIUM', weight_pct: 10.0, description: 'Relative velocity is 14.80 km/s.' },
        { feature: 'TLE Age', impact: 'LOW', weight_pct: 5.0, description: 'TLE telemetry age < 12 hours.' },
      ],
      candidate_tradeoffs: [
        { candidate_id: 'burn-1', burn_type: 'In-Track Posigrade', dv_ms: 1.20, fuel_kg: 2.40, pc_after: 1e-12, status: 'SELECTED (RECOMMENDED)' },
        { candidate_id: 'burn-2', burn_type: 'In-Track Retrograde', dv_ms: 1.85, fuel_kg: 3.70, pc_after: 2.5e-5, status: 'REJECTED', rejection_reason: 'Higher fuel consumption & insufficient clearance.' },
        { candidate_id: 'burn-3', burn_type: 'Radial Outward', dv_ms: 4.50, fuel_kg: 9.00, pc_after: 1.2e-4, status: 'REJECTED', rejection_reason: 'Requires 3.7x higher delta-v and leaves Pc above safety target.' },
      ],
      validation_summary: { status: 'PASS', objects_screened: 133, window_hours: 24, secondary_threats: 0 },
    }, 'mock')
  }
}

export const __base = BASE_URL
