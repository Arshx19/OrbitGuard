/**
 * ORBITGUARD AI Node.js Express Main API Server
 * Acts as the primary REST API backend (Port 5000) and communicates with the Python AI Microservice (Port 8000)
 */

const express = require('express');
const cors = require('cors');
require('dotenv').config();

const satellitesRouter = require('./routes/satellites');
const conjunctionsRouter = require('./routes/conjunctions');
const riskRouter = require('./routes/risk');
const maneuverRouter = require('./routes/maneuver');
const explainRouter = require('./routes/explain');
const { forward, PYTHON_AI_SERVICE_URL } = require('./lib/forward');

const app = express();
const PORT = process.env.PORT || 5000;

// Enable CORS and JSON body parser
app.use(cors());
app.use(express.json());

// Root Health Check
app.get('/', (req, res) => {
  res.json({
    status: "online",
    system: "ORBITGUARD AI Node.js Express Backend",
    version: "1.0.0",
    python_ai_service: PYTHON_AI_SERVICE_URL
  });
});

// Python service health, relayed. Returns 503 if the service is unreachable.
app.get('/api/v1/health', forward('get', () => '/health'));

// Register API v1 routes
app.use('/api/v1', satellitesRouter);
app.use('/api/v1', conjunctionsRouter);
app.use('/api/v1', riskRouter);
app.use('/api/v1', maneuverRouter);
app.use('/api/v1', explainRouter);

// Start Node.js Express server
app.listen(PORT, () => {
  console.log(`====================================================`);
  console.log(`🚀 Node.js Express Backend running on http://localhost:${PORT}`);
  console.log(`🤖 Forwarding to Python AI Service at ${PYTHON_AI_SERVICE_URL}`);
  console.log(`   (check it is up: GET http://localhost:${PORT}/api/v1/health)`);
  console.log(`====================================================`);
});
