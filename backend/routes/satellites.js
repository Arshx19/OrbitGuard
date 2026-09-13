const express = require('express');
const { forward } = require('../lib/forward');

const router = express.Router();

// GET /api/v1/satellites
router.get('/satellites', forward('get', () => '/satellites'));

module.exports = router;
