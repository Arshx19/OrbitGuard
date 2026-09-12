// Frontend <-> Backend API contract (spec section 11).
//
// Each function returns data in the camelCase shape the components already
// consume. When VITE_API_BASE_URL is set, the data comes from the FastAPI
// backend and is translated here; when it is not set, or when a request fails,
// the local mock data is used instead. That keeps the UI runnable with no
// backend at all, which matters on demo day.
//
// WHY A TRANSLATION LAYER EXISTS
//
// The backend risk engine speaks snake_case, works in kilometres, and returns a
// different set of risk factors than the original mock data assumed. Rather
// than push those differences into every component, they are resolved once,
// here. The mapping functions are exported so they can be tested directly
// against a real backend response.
//
// THREE DIFFERENCES WORTH KNOWING ABOUT
//
// 1. There are three risk factors, not six. The backend computes collision
//    probability with Foster's method, in which relative velocity and orbital
//    geometry are not separate contributors -- they define the encounter plane
//    the probability is integrated over. They are absorbed, not discarded. Time
//    to closest approach is also excluded: it changes how long an operator has
//    to react, not how likely the collision is.
//
// 2. A factor's percentage can be negative. Large ephemeris uncertainty spreads
//    the probability distribution out, and past a point that *lowers* the
//    probability rather than raising it -- the dilution effect. Such factors
//    arrive with direction === 'reduces'. Use `magnitude` for bar widths, since
//    a negative CSS width silently renders as nothing at all.
//
// 3. Severity comes from the backend and should not be recomputed. It is keyed
//    to collision-probability thresholds (1e-4 critical, 1e-5 high, 1e-6
//    amber), which is what operators actually act on. Deriving a band from the
//    0-100 score instead gives a different answer for mid-range events.

import { stats, conjunctions, getConjunction, levelFromScore } from '../data/mockData'

const BASE_URL =
  (typeof import.meta !== 'undefined' &&
    import.meta.env &&
    import.meta.env.VITE_API_BASE_URL) ||
  ''

/** Whether the app is wired to a live backend. */
export const isLive = () => Boolean(BASE_URL)

// ---------------------------------------------------------------------------
// Mapping helpers (pure -- exported for testing)
// ---------------------------------------------------------------------------

/**
 * Render hours-to-TCA as the short human string the UI shows.
 * @param {number} hours
 * @returns {string} e.g. "4 hr 12 min", "42 min"
 */
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

/**
 * Bucket an along-track uncertainty into the label the detail panel shows.
 *
 * The thresholds are presentational. The underlying number is carried through
 * as sigmaAlongTrackKm so the UI can show it wherever there is room.
 *
 * @param {number} sigmaAlongTrackKm
 * @returns {'Low'|'Moderate'|'High'|'Unknown'}
 */
export function uncertaintyBand(sigmaAlongTrackKm) {
  if (sigmaAlongTrackKm == null) return 'Unknown'
  if (sigmaAlongTrackKm < 0.75) return 'Low'
  if (sigmaAlongTrackKm < 2.5) return 'Moderate'
  return 'High'
}

/**
 * Translate one backend factor into the shape RiskFactors renders.
 *
 * `pct` keeps its sign, so a risk-reducing factor is never silently presented
 * as risk-raising. `magnitude` is the absolute value, which is what a bar width
 * needs.
 *
 * @param {object} f Backend factor object.
 * @returns {{label: string, pct: number, magnitude: number, direction: string, explanation: string}}
 */
export function mapFactor(f) {
  const pct = Number(f.contribution_percent ?? 0)
  const rounded = Number(pct.toFixed(1))
  return {
    label: f.display_name ?? f.name ?? 'Unknown factor',
    pct: rounded,
    magnitude: Math.abs(rounded),
    direction: f.direction ?? 'raises',
    explanation: f.explanation ?? '',
  }
}

/**
 * Display a collision probability, respecting the reporting floor.
 *
 * The backend returns the raw integral, which for a distant pass can be 1e-123
 * or underflow to zero. Figures that far into a Gaussian tail are not credible
 * estimates of anything, so -- matching the risk engine's own reporting -- they
 * are shown as a bound rather than as a number.
 *
 * @param {number} pc
 * @param {number} digits
 * @returns {string}
 */
export function formatProbability(pc, digits = 1) {
  if (pc == null || Number.isNaN(pc)) return '—'
  if (pc < 1e-12) return '< 1e-12'
  return pc.toExponential(digits)
}

/**
 * Severity band for a conjunction, preferring the backend's value.
 *
 * Live data carries `level`, derived from collision-probability thresholds.
 * Mock data has only a score, so fall back to bucketing that.
 *
 * @param {object} conjunction
 * @returns {'critical'|'high'|'amber'|'green'}
 */
export function levelOf(conjunction) {
  return conjunction?.level ?? levelFromScore(conjunction?.riskScore ?? 0)
}

/**
 * Translate a backend conjunction or risk assessment into the frontend shape.
 *
 * Fields the backend does not provide are left undefined rather than invented,
 * so a gap surfaces as a gap in the UI instead of as plausible-looking fiction.
 *
 * @param {object} payload A conjunction from /conjunctions or /risk/analyze.
 * @returns {object|null} Conjunction-shaped object for the components.
 */
export function mapRiskAnalysis(payload) {
  if (!payload) return null

  const factors = Array.isArray(payload.factors) ? payload.factors.map(mapFactor) : []
  const sigma = payload.uncertainty?.primary_sigma_along_track_km

  return {
    id: payload.conjunction_id ?? `CJ-${payload.primary_id ?? '?'}`,
    primaryId: payload.primary_id,
    secondaryId: payload.secondary_id,
    primary: payload.primary_name ?? payload.primary_id,
    secondary: payload.secondary_name ?? payload.secondary_id,
    primaryType: payload.primary_type,
    secondaryType: payload.secondary_type,
    maneuverable: payload.maneuverable,

    // A constructed demonstration event, not a screening result. The UI must
    // label it as such.
    simulated: Boolean(payload.simulated),

    tca: payload.tca,
    geometry: payload.geometry,
    timeline: Array.isArray(payload.timeline)
      ? payload.timeline.map((p) => ({ t: p.t, hours: p.hours, distanceKm: p.distance_km }))
      : undefined,

    // Severity is authoritative from the backend; do not recompute from score.
    severity: payload.severity,
    level: typeof payload.severity === 'string' ? payload.severity.toLowerCase() : undefined,
    riskScore: Math.round(Number(payload.risk_score ?? 0)),

    probability: payload.collision_probability,

    // The backend works in kilometres; the detail panel displays metres.
    minDistanceM: Math.round(Number(payload.miss_distance_km ?? 0) * 1000),
    missDistanceKm: payload.miss_distance_km,
    relVelocityKms:
      payload.relative_speed_kms == null ? undefined : Number(payload.relative_speed_kms.toFixed(2)),

    tcaHours: payload.time_to_tca_hours,
    tcaIn: formatTcaIn(payload.time_to_tca_hours),

    uncertainty: uncertaintyBand(sigma),
    sigmaAlongTrackKm: sigma,
    tleAgeDays: payload.uncertainty?.primary_tle_age_days,
    // Provenance of the position uncertainty behind the probability: either the
    // assumed default or a model learned from measured element-set errors.
    uncertaintySource: payload.uncertainty?.primary_model_source,
    uncertaintyExtrapolated: Boolean(payload.uncertainty?.extrapolated),

    combinedHbrM: payload.combined_hbr_m,
    factors,
    narrative: payload.narrative,
  }
}

// ---------------------------------------------------------------------------
// Transport
// ---------------------------------------------------------------------------

/**
 * Issue a request, falling back to mock data if the backend is unreachable.
 *
 * Falling back rather than throwing is deliberate: a half-loaded dashboard is
 * worse than a mock one, and the demo should survive the backend going down
 * mid-presentation. Every fallback is logged, so it is never silent.
 */
// Long enough for the slowest legitimate call (a maneuver search takes one to
// two seconds), short enough that a hung backend cannot freeze the dashboard.
const REQUEST_TIMEOUT_MS = 10000

async function request(path, options, fallback, label) {
  if (!BASE_URL) return fallback()

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  try {
    const response = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
      signal: controller.signal,
    })
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} ${response.statusText}`)
    }
    return await response.json()
  } catch (error) {
    const reason = error.name === 'AbortError' ? `no response in ${REQUEST_TIMEOUT_MS / 1000} s` : error.message
    console.warn(
      `[orbitguard] ${label} failed (${reason}); using mock data. ` +
        `Backend expected at ${BASE_URL}${path}`
    )
    return fallback()
  } finally {
    clearTimeout(timer)
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function getStats() {
  const payload = await request(
    '/api/v1/satellites/stats',
    { method: 'GET' },
    () => null,
    'getStats'
  )
  if (!payload) return stats

  return {
    objectsTracked: payload.objects_tracked ?? stats.objectsTracked,
    objectsTrackedDelta: payload.objects_tracked_delta ?? '',
    activeConjunctions: payload.active_conjunctions ?? stats.activeConjunctions,
    activeConjunctionsDelta: payload.active_conjunctions_delta ?? '',
    highRiskEvents: payload.high_risk_events ?? stats.highRiskEvents,
    highRiskEventsDelta: payload.high_risk_events_delta ?? '',
    satellitesMonitored: payload.satellites_monitored ?? stats.satellitesMonitored,
    satellitesMonitoredDelta: payload.satellites_monitored_delta ?? '',
  }
}

export async function listConjunctions() {
  const payload = await request(
    '/api/v1/conjunctions',
    { method: 'GET' },
    () => null,
    'listConjunctions'
  )
  if (!payload) return conjunctions

  // The backend returns assessments already ranked by risk score. Tag the
  // array so the UI can say where its data came from: isLive() only reports
  // that a backend is configured, not that it answered.
  const rows = payload.map(mapRiskAnalysis)
  rows.live = true
  return rows
}

export async function getConjunctionById(id) {
  const payload = await request(
    `/api/v1/conjunctions/${encodeURIComponent(id)}`,
    { method: 'GET' },
    () => null,
    'getConjunctionById'
  )
  return payload ? mapRiskAnalysis(payload) : getConjunction(id)
}

export async function analyzeRisk(id) {
  const payload = await request(
    '/api/v1/risk/analyze',
    { method: 'POST', body: JSON.stringify({ conjunction_id: id }) },
    () => null,
    'analyzeRisk'
  )

  // Both paths return a full conjunction, so the risk page can render its
  // header, score, factors, and timeline from a single call.
  if (!payload) return getConjunction(id) ?? null
  return mapRiskAnalysis(payload)
}

/** Translate one backend maneuver candidate into the ManeuverTable row shape. */
export function mapCandidate(candidate, recommendedId) {
  return {
    id: candidate.candidate_id ?? candidate.id,
    deltaV: candidate.delta_v_magnitude_ms,
    direction: candidate.direction_name,
    leadHours: candidate.burn_lead_hours,
    burnTime: candidate.burn_time,
    newSeparationKm: candidate.new_miss_distance_km,
    pcBefore: candidate.pc_before,
    pcAfter: candidate.pc_after,
    propellantKg: candidate.propellant_kg,
    newRisk: candidate.secondary_threats_detected
      ? candidate.secondary_threat_details?.find((t) => !t.is_original_threat)?.secondary_name ??
        'Original object, later pass'
      : 'None detected',
    status: candidate.is_safe ? 'SAFE' : 'REJECT',
    recommended: recommendedId != null && candidate.candidate_id === recommendedId,
    reason:
      candidate.rejection_reason ??
      'Clears the event with no new conjunction introduced on re-screen.',
  }
}

/**
 * Candidate maneuvers for a conjunction.
 *
 * Returns the row array ManeuverTable renders. When live, the array also
 * carries the search metadata -- how many candidates were evaluated and which
 * was recommended -- as properties, so existing callers that expect a plain
 * array keep working.
 */
export async function optimizeManeuver(id) {
  const payload = await request(
    '/api/v1/maneuver/optimize',
    { method: 'POST', body: JSON.stringify({ conjunction_id: id }) },
    () => null,
    'optimizeManeuver'
  )
  if (!payload) return getConjunction(id)?.maneuverCandidates ?? []

  const rows = (payload.candidates ?? []).map((c) => mapCandidate(c, payload.recommended_candidate_id))
  rows.recommendedId = payload.recommended_candidate_id
  rows.evaluated = payload.candidates_evaluated
  rows.safetyTarget = payload.safety_target
  rows.reason = payload.reason
  return rows
}

export async function validateManeuver(id, candidateId) {
  const payload = await request(
    '/api/v1/maneuver/validate',
    { method: 'POST', body: JSON.stringify({ conjunction_id: id, candidate_id: candidateId }) },
    () => null,
    'validateManeuver'
  )

  if (!payload) {
    const c = getConjunction(id)
    const candidate = c?.maneuverCandidates.find((m) => m.id === candidateId)
    return new Promise((resolve) =>
      setTimeout(() => resolve({ validated: candidate?.status === 'SAFE', candidate }), 900)
    )
  }

  return {
    validated: Boolean(payload.is_safe),
    candidate: mapCandidate(payload),
    pcBefore: payload.pc_before,
    pcAfter: payload.pc_after,
    pcAfterBelowFloor: payload.pc_after_below_floor,
    reason: payload.rejection_reason,
    checks: payload.checks
      ? {
          originalResolved: payload.checks.original_conjunction_resolved,
          trajectoryPropagated: payload.checks.post_maneuver_trajectory_propagated,
          catalogRescreened: payload.checks.catalog_rescreened,
          horizonHours: payload.checks.rescreen_horizon_hours,
          objectsScreened: payload.checks.catalog_objects_screened,
          newConjunctions: payload.checks.new_conjunctions,
        }
      : undefined,
  }
}

export const __base = BASE_URL
