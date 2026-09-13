# ORBITGUARD AI

A space debris detection and collision avoidance AI prototype.

## Running

ORBITGUARD AI is three services: the React frontend (port 5173) talks to a
Node.js server (port 5000), which forwards to the Python AI service (port 8000).
Start them in this order, each in its own terminal, from the repository root.

**1. Python AI service** (Python 3.12; the first line is one-time setup)

```bash
python -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir src --port 8000
```

On macOS/Linux use `.venv/bin/python`. Startup screens the committed TLE
catalog and assesses every close approach, which takes a couple of seconds.

**2. Node.js server**

```bash
cd backend && npm install && npm start
```

**3. Frontend**

```bash
cd frontend && npm install && npm run dev
```

Then open http://localhost:5173. The dashboard footer says whether it is
showing live results or mock data. Check the services with
`GET http://localhost:5000/api/v1/health`; the Python API's interactive docs are
at http://localhost:8000/docs.

**Configuration.** Copy `.env.example`, `backend/.env.example` and
`frontend/.env.example` to `.env` files next to them. `.env` files are
gitignored: never commit credentials.

**Tests**

```bash
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe tests/test_problem_statement_compliance.py   # requirement-by-requirement report
```

**Data and models.** TLE snapshots from CelesTrak are cached in `data/raw/` so the
system runs offline. Refresh them with `scripts/fetch_catalog.py`. The learned
position-uncertainty model in `models/tle_uncertainty.json` is retrained with
`scripts/train_uncertainty_model.py`.

## Project Structure

### Root Directories

- **`.claude/`**  
  Claude Code specific configurations (settings, hooks, etc.).  
  Contains `settings.json` for Ruflo integration.

- **`config/`**  
  Application configuration files (environment configs, feature flags, etc.).

- **`data/`**  
  Storage for orbital data.  
  - `raw/` – Public TLE files downloaded from sources like CelesTrak.  
  - `processed/` – Parsed, cleaned, or aggregated data ready for propagation.

- **`docs/`**  
  Documentation files (design docs, API specs, user guides).

- **`frontend/`**  
  React-based web application.  
  - `public/` – Static assets served directly (HTML entry point, favicon).  
  - `src/` – React source code.  
    - `App.js` – Root component.  
    - `index.js` – Entry point for ReactDOM.  
    - `components/` – Reusable UI components (charts, tables, 3D view).  
    - `pages/` – Page-level views (Dashboard, Risk Analysis, Maneuver Simulator).  
    - `services/` – API service layers communicating with the backend.  
    - `styles/` – CSS/Tailwind files and theme definitions.

- **`models/`**  
  Persisted machine learning models (risk scoring models, etc.).

- **`scripts/`**  
  Utility scripts (data download, model training helpers, deployment scripts).

- **`src/`**  
  Backend source code (Python/FastAPI).  
  - `app/` – Main application package.  
    - `__init__.py` – Package initializer.  
    - `main.py` – FastAPI application entry point.  
    - `api/` – REST API route definitions.  
      - `__init__.py` – API package initializer.  
      - `v1/` – Versioned API routes.  
        - `__init__.py` – v1 package initializer.  
        - `satellites.py` – Endpoints for satellite metadata and TLE management.  
        - `conjunctions.py` – Endpoints for detected close approaches.  
        - `risk.py` – Endpoints for risk scoring and explainability.  
        - `maneuver.py` – Endpoints for maneuver generation and optimization.  
    - `core/` – Business logic and domain services.  
      - `__init__.py` – Core package initializer.  
      - `data_ingestion.py` – Loads and parses TLE files from `data/raw/`.  
      - `propagation.py` – Implements SGP4 orbital propagation.  
      - `conjunction.py` – Pairwise conjunction detection and miss distance/TCA calculation.  
      - `risk_engine.py` – Feature extraction, ML model inference, risk scoring, and SHAP explanations.  
      - `maneuver_optimizer.py` – Generates Δv candidates, propagates maneuvers, and selects minimum-safe Δv.  
      - `validation.py` – Post-maneuver re‑screening to ensure no new conjunctions are introduced.  
    - `models/` – SQLAlchemy/Pydantic models representing domain entities.  
      - `__init__.py` – Models package initializer.  
      - `satellite.py` – Satellite/TLE model.  
      - `conjunction.py` – Conjunction event model.  
    - `utils/` – Helper functions and shared utilities.  
      - `__init__.py` – Utils package initializer.  
      - `helpers.py` – Common utilities (unit conversions, date handling, logging helpers).  

- **`tests/`**  
  Automated test suite.  
  - `unit/` – Unit tests for individual functions/classes.  
    - `test_data_ingestion.py` – Tests for TLE loading/parsing.  
    - `test_propagation.py` – Tests for SGP4 propagation correctness.  
    - `test_conjunction.py` – Tests for distance/TCA calculations.  
    - `test_risk_engine.py` – Tests for feature extraction and risk scoring.  
    - `test_maneuver_optimizer.py` – Tests for maneuver generation and validation logic.  
    - `test_validation.py` – Tests for post-maneuver re‑screening.  
  - `integration/` – End‑to‑end API tests.  
    - `test_api.py` – Tests exercising the full request/response cycle.  

- **`Dockerfile`**  
  Container definition for building a reproducible runtime image.

- **`requirements.txt`**  
  Python package dependencies for the backend.

- **`README.md`**  
  This file – overview of the project and its structure.

## Getting Started

See [Running](#running) above.

## Development Guidelines

- Follow the existing code style and naming conventions.  
- Write unit tests for new logic; aim for high test coverage.  
- Keep files under 500 lines where possible.  
- Validate all inputs at system boundaries.  
- Never commit secrets, credentials, or `.env` files.  
- Use the provided `.claude/settings.json` for Ruflo‑enabled Claude Code assistance.  
- Run `npm run build && npm test` (or equivalent) before committing.  

## License

License information to be added.