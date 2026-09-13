const express = require('express');
const { forward } = require('../lib/forward');

const router = express.Router();

// GET /api/v1/conjunctions
router.get('/conjunctions', forward('get', () => '/conjunctions'));

// GET /api/v1/conjunctions/:id
router.get('/conjunctions/:id', forward('get', (req) => `/conjunctions/${encodeURIComponent(req.params.id)}`));

module.exports = router;
