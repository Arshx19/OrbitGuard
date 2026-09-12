# ORBITGUARD AI

A space debris detection and collision avoidance AI prototype.

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

1. Clone the repository.  
2. Install backend dependencies: `pip install -r requirements.txt`.  
3. (Optional) Install frontend dependencies: `cd frontend && npm install`.  
4. Download sample TLE data into `data/raw/` (or use provided sample).  
5. Run the backend: `uvicorn src.app.main:app --reload`.  
6. Start the frontend: `cd frontend && npm start`.  
7. Open `http://localhost:3000` in your browser.

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