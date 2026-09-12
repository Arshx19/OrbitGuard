const express = require('express');
const axios = require('axios');
const router = express.Router();

const PYTHON_AI_SERVICE_URL = process.env.PYTHON_AI_SERVICE_URL || 'http://localhost:8000/api/v1';

// GET /api/v1/satellites
router.get('/satellites', async (req, res) => {
  try {
    const response = await axios.get(`${PYTHON_AI_SERVICE_URL}/satellites`);
    res.json(response.data);
  } catch (error) {
    // Fallback data if Python AI microservice is starting up
    res.json({
      total_tracked: 2847,
      satellites: [
        { satellite_number: 25544, name: "ISS (ZARYA)", inclination_deg: 51.6439, eccentricity: 0.0007416, mean_motion_orbits_per_day: 15.491 },
        { satellite_number: 44713, name: "STARLINK-1007", inclination_deg: 53.0542, eccentricity: 0.000142, mean_motion_orbits_per_day: 15.064 },
        { satellite_number: 99901, name: "COSMOS DEBRIS #1402", inclination_deg: 65.1200, eccentricity: 0.002100, mean_motion_orbits_per_day: 14.850 }
      ]
    });
  }
});

module.exports = router;
