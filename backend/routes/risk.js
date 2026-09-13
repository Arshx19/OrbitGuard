const express = require('express');
const { forward } = require('../lib/forward');

const router = express.Router();

// POST /api/v1/risk/analyze
router.post('/risk/analyze', forward('post', () => '/risk/analyze'));

module.exports = router;
