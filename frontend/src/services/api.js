/**
 * API Service for ORBITGUARD AI Frontend
 * Connects React UI to the FastAPI backend running on http://localhost:8000
 */

const BASE_URL = 'http://localhost:5000/api/v1';

/**
 * Fetch list of tracked satellites and debris objects
 */
export async function getSatellites() {
  const response = await fetch(`${BASE_URL}/satellites`);
  if (!response.ok) throw new Error('Failed to fetch satellites');
  return response.json();
}

/**
 * Fetch list of active conjunctions ranked by risk
 */
export async function getConjunctions() {
  const response = await fetch(`${BASE_URL}/conjunctions`);
  if (!response.ok) throw new Error('Failed to fetch conjunctions');
  return response.json();
}

/**
 * Fetch detail for a specific conjunction event
 */
export async function getConjunctionDetail(id) {
  const response = await fetch(`${BASE_URL}/conjunctions/${id}`);
  if (!response.ok) throw new Error(`Failed to fetch conjunction ${id}`);
  return response.json();
}

/**
 * Calculate AI risk score & SHAP feature attribution
 */
export async function analyzeRisk(params) {
  const response = await fetch(`${BASE_URL}/risk/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  if (!response.ok) throw new Error('Failed to analyze risk');
  return response.json();
}

/**
 * Generate candidate maneuvers and validate safety against secondary collisions
 */
export async function validateManeuver(params) {
  const response = await fetch(`${BASE_URL}/maneuver/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  if (!response.ok) throw new Error('Failed to validate maneuver');
  return response.json();
}
