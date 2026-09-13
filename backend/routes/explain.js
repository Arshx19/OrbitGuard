const express = require('express');
const { forward } = require('../lib/forward');

const router = express.Router();

// POST /api/v1/explain/decision
router.post('/explain/decision', forward('post', () => '/explain/decision'));

module.exports = router;
