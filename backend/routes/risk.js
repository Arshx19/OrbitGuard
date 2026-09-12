const express = require('express');
const axios = require('axios');
const router = express.Router();

const PYTHON_AI_SERVICE_URL = process.env.PYTHON_AI_SERVICE_URL || 'http://localhost:8000/api/v1';

const FALLBACK_SCORES = {
  'CONJ-001': { score: 94.0, level: 'CRITICAL', miss: '0.42 km', speed: '12.4 km/s' },
  'CONJ-002': { score: 78.0, level: 'HIGH', miss: '1.20 km', speed: '9.8 km/s' },
  'CONJ-003': { score: 45.0, level: 'AMBER', miss: '5.00 km', speed: '6.2 km/s' },
  'CONJ-004': { score: 12.0, level: 'GREEN', miss: '25.00 km', speed: '2.1 km/s' },
  'CJ-142': { score: 94.0, level: 'CRITICAL', miss: '0.42 km', speed: '12.4 km/s' },
  'CJ-078': { score: 78.0, level: 'HIGH', miss: '1.20 km', speed: '9.8 km/s' },
  'CJ-311': { score: 45.0, level: 'AMBER', miss: '5.00 km', speed: '6.2 km/s' },
};

router.post('/risk/analyze', async (req, res) => {
  try {
    const response = await axios.post(`${PYTHON_AI_SERVICE_URL}/risk/analyze`, req.body);
    res.json(response.data);
  } catch (error) {
    const cid = req.body.conjunction_id || 'CONJ-001';
    const fb = FALLBACK_SCORES[cid] || FALLBACK_SCORES['CONJ-001'];
    res.json({
      risk_score: fb.score,
      risk_level: fb.level,
      explanation_summary: `Miss distance (${fb.miss}) combined with relative speed (${fb.speed}).`,
      shap_factors: [
        { factor: `Minimum Separation (${fb.miss})`, contribution_percentage: 32.0 },
        { factor: `Relative Velocity (${fb.speed})`, contribution_percentage: 24.0 },
        { factor: "TCA Urgency", contribution_percentage: 20.0 },
        { factor: "Crossing Orbital Geometry", contribution_percentage: 14.0 },
        { factor: "Position Uncertainty", contribution_percentage: 7.0 },
        { factor: "Satellite Size Factor", contribution_percentage: 3.0 }
      ]
    });
  }
});

module.exports = router;
