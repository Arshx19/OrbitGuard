const express = require('express');
const axios = require('axios');
const router = express.Router();

const PYTHON_AI_SERVICE_URL = process.env.PYTHON_AI_SERVICE_URL || 'http://localhost:8000/api/v1';

// GET /api/v1/conjunctions
router.get('/conjunctions', async (req, res) => {
  try {
    const response = await axios.get(`${PYTHON_AI_SERVICE_URL}/conjunctions`);
    res.json(response.data);
  } catch (error) {
    res.json([
      {
        id: "CONJ-001",
        satellite1_id: 25544,
        satellite1_name: "ISS (ZARYA)",
        satellite2_id: 99901,
        satellite2_name: "COSMOS DEBRIS #1402",
        risk_score: 94.0,
        risk_level: "CRITICAL",
        miss_distance_km: 0.42,
        relative_speed_kms: 12.4,
        tca: "2026-09-13T04:12:00Z"
      },
      {
        id: "CONJ-002",
        satellite1_id: 44713,
        satellite1_name: "STARLINK-1007",
        satellite2_id: 99902,
        satellite2_name: "FENGYUN DEBRIS #312",
        risk_score: 78.0,
        risk_level: "HIGH",
        miss_distance_km: 1.20,
        relative_speed_kms: 9.8,
        tca: "2026-09-13T07:40:00Z"
      }
    ]);
  }
});

module.exports = router;
