const express = require('express');
const { forward } = require('../lib/forward');

const router = express.Router();

// Each route goes to its own Python endpoint. Previously both were sent to
// /maneuver/validate, so "optimize" never ran the search it names.

// POST /api/v1/maneuver/optimize
router.post('/maneuver/optimize', forward('post', () => '/maneuver/optimize'));

// POST /api/v1/maneuver/validate
router.post('/maneuver/validate', forward('post', () => '/maneuver/validate'));

module.exports = router;
