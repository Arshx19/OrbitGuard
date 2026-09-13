// Deterministic mock catalog for the LEO tracking globe + Data page.
// Seeded so the field of objects looks the same on every load/render.

function mulberry32(seed) {
  return function () {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const rand = mulberry32(42)

const TYPES = ['active', 'debris', 'rocket_body']
const TYPE_WEIGHTS = [0.42, 0.48, 0.10]
const COUNTRIES = ['US', 'RU', 'CN', 'EU', 'IN', 'JP', 'Other']
const COUNTRY_WEIGHTS = [0.28, 0.22, 0.2, 0.1, 0.06, 0.05, 0.09]
const TRACKED = ['day', 'week', 'stale']
const TRACKED_WEIGHTS = [0.62, 0.27, 0.11]

function weightedPick(arr, weights) {
  const r = rand()
  let acc = 0
  for (let i = 0; i < arr.length; i++) {
    acc += weights[i]
    if (r <= acc) return arr[i]
  }
  return arr[arr.length - 1]
}

export const leoObjects = Array.from({ length: 260 }).map((_, i) => {
  const type = weightedPick(TYPES, TYPE_WEIGHTS)
  const lat = (rand() * 2 - 1) * 90
  const lon = (rand() * 2 - 1) * 180
  return {
    id: i + 1,
    noradId: 40000 + Math.floor(rand() * 9000),
    name: `${type === 'active' ? 'SAT' : type === 'debris' ? 'DEB' : 'RB'}-${(1000 + i).toString()}`,
    type,
    country: weightedPick(COUNTRIES, COUNTRY_WEIGHTS),
    lat,
    lon,
    perigeeKm: Math.round(300 + rand() * 1400),
    periodMin: Math.round(88 + rand() * 45),
    inclinationDeg: Math.round(rand() * 180),
    lastTracked: weightedPick(TRACKED, TRACKED_WEIGHTS),
  }
})

export const groundStations = [
  { name: 'Fairbanks, AK', lat: 64.8, lon: -147.7, beamHeadingDeg: 40 },
  { name: 'Kiwi Space, NZ', lat: -43.5, lon: 172.6, beamHeadingDeg: 210 },
  { name: 'Midland, TX', lat: 31.9, lon: -102.0, beamHeadingDeg: 320 },
  { name: 'Costa Rica', lat: 10.0, lon: -84.0, beamHeadingDeg: 100 },
  { name: 'W. Australia', lat: -31.9, lon: 115.9, beamHeadingDeg: 260 },
]

export const trackedColor = { day: '#3ED598', week: '#E8C547', stale: '#E8763C' }
export const typeColor = { active: '#3FD7E8', debris: '#F0475A', rocket_body: '#9B7EDE' }
export const countryColor = {
  US: '#3FD7E8', RU: '#F0475A', CN: '#F2C94C', EU: '#3ED598', IN: '#9B7EDE', JP: '#F5924A', Other: '#8A96A8',
}

function hexToRgb(hex) {
  const v = hex.replace('#', '')
  return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)]
}
function rgbToHex([r, g, b]) {
  return '#' + [r, g, b].map((n) => Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, '0')).join('')
}
export function colorScale(value, min, max, lowHex, highHex) {
  const t = Math.max(0, Math.min(1, (value - min) / (max - min)))
  const low = hexToRgb(lowHex)
  const high = hexToRgb(highHex)
  return rgbToHex(low.map((c, i) => c + (high[i] - c) * t))
}

export function colorForView(obj, view) {
  switch (view) {
    case 'lastTracked':
      return trackedColor[obj.lastTracked]
    case 'objectType':
      return typeColor[obj.type]
    case 'country':
      return countryColor[obj.country]
    case 'perigee':
      return colorScale(obj.perigeeKm, 300, 1700, '#F0475A', '#3FD7E8')
    case 'period':
      return colorScale(obj.periodMin, 88, 133, '#3ED598', '#9B7EDE')
    case 'inclination':
      return colorScale(obj.inclinationDeg, 0, 180, '#F2C94C', '#3FD7E8')
    default:
      return '#3FD7E8'
  }
}
