/**
 * Forward a request to the Python AI service and relay its answer faithfully.
 *
 * The routes used to answer with hardcoded conjunctions, risk scores and
 * maneuvers whenever the Python service was unreachable. That made an outage
 * indistinguishable from real results: the dashboard would show a CRITICAL
 * event that no computation had produced. Now the client gets the Python
 * service's own status code and body, or an explicit 503 saying the service is
 * down, and decides for itself what to show.
 */

const axios = require('axios');

const PYTHON_AI_SERVICE_URL = process.env.PYTHON_AI_SERVICE_URL || 'http://127.0.0.1:8000/api/v1';

// Long enough for a maneuver search with a whole-catalog re-screen; short
// enough that a hung service does not hang the dashboard.
const TIMEOUT_MS = Number(process.env.PYTHON_AI_TIMEOUT_MS || 20000);

function forward(method, path) {
  return async (req, res) => {
    try {
      const response = await axios({
        method,
        url: `${PYTHON_AI_SERVICE_URL}${path(req)}`,
        data: method === 'get' ? undefined : req.body,
        params: req.query,
        timeout: TIMEOUT_MS,
        // Relay every status, including 4xx, instead of throwing on them.
        validateStatus: () => true,
      });
      res.status(response.status).json(response.data);
    } catch (error) {
      res.status(503).json({
        error: 'python_ai_service_unavailable',
        detail: `The Python AI service at ${PYTHON_AI_SERVICE_URL} did not respond: ${error.message}`,
      });
    }
  };
}

module.exports = { forward, PYTHON_AI_SERVICE_URL };
