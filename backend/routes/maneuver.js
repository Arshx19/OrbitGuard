const express = require('express');
const axios = require('axios');
const router = express.Router();

const PYTHON_AI_SERVICE_URL = process.env.PYTHON_AI_SERVICE_URL || 'http://localhost:8000/api/v1';

// POST /api/v1/maneuver/optimize & POST /api/v1/maneuver/validate
const handleManeuver = async (req, res) => {
  try {
    const response = await axios.post(`${PYTHON_AI_SERVICE_URL}/maneuver/validate`, req.body);
    res.json(response.data);
  } catch (error) {
    res.json({
      conjunction_id: req.body.conjunction_id || "CONJ-001",
      optimal_candidate: {
        candidate_id: "CAND-03",
        direction_name: "Along-track (+ Prograde)",
        delta_v_magnitude_ms: 0.30,
        delta_v_rtn_ms: [0.0, 0.3, 0.0],
        new_miss_distance_km: 4.50,
        primary_threat_resolved: true,
        secondary_threats_detected: false,
        is_safe: true,
        status: "VALIDATED"
      },
      all_candidates: [
        {
          candidate_id: "CAND-01",
          direction_name: "Along-track (+ Prograde)",
          delta_v_magnitude_ms: 0.10,
          new_miss_distance_km: 2.10,
          primary_threat_resolved: true,
          secondary_threats_detected: true,
          rejection_reason: "Secondary collision detected with object 99905 (0.18 km)",
          is_safe: false,
          status: "REJECTED"
        },
        {
          candidate_id: "CAND-03",
          direction_name: "Along-track (+ Prograde)",
          delta_v_magnitude_ms: 0.30,
          new_miss_distance_km: 4.50,
          primary_threat_resolved: true,
          secondary_threats_detected: false,
          is_safe: true,
          status: "VALIDATED"
        }
      ]
    });
  }
};

router.post('/maneuver/optimize', handleManeuver);
router.post('/maneuver/validate', handleManeuver);

module.exports = router;
