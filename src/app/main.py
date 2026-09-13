"""
ORBITGUARD AI - FastAPI Application Entry Point
Decision-Support Layer for Space Debris Collision Avoidance

Run from the repository root:

    python -m uvicorn app.main:app --app-dir src --port 8000

The Node.js server (backend/, port 5000) forwards the frontend's requests here.
The catalog is screened and every conjunction assessed once at startup, so the
first request is fast; POST /api/v1/screening/refresh rebuilds it.
"""

import sys
import os
import logging
from contextlib import asynccontextmanager

# Add src directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set default groups to load team's 133 real CelesTrak tracked objects (20 stations + 110 iridium-33 + 3 cosmos-1408)
os.environ["ORBITGUARD_GROUPS"] = os.environ.get("ORBITGUARD_GROUPS", "stations,iridium-33-debris,cosmos-1408-debris")

from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import router as api_v1_router
from app.services.world import get_world, rebuild_world


logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(name)s: %(message)s")
logger = logging.getLogger("orbitguard")


import asyncio

async def _auto_refresh_loop():
    interval = float(os.environ.get("ORBITGUARD_AUTO_REFRESH_INTERVAL", "60"))
    enabled = os.environ.get("ORBITGUARD_AUTO_REFRESH", "1") != "0"
    if not enabled:
        return
    logger.info("Auto-refresh background worker initialized (interval: %.1fs)", interval)
    while True:
        try:
            await asyncio.sleep(interval)
            logger.info("Performing scheduled real-time data & screening refresh...")
            rebuild_world()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Auto-refresh worker encountered an error: %s", exc)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    world = get_world()
    logger.info("ORBITGUARD AI ready: %d objects, %d conjunctions, built in %.1f s.",
                len(world.tracks), len(world.events), world.build_seconds)
    refresh_task = asyncio.create_task(_auto_refresh_loop())
    try:
        yield
    finally:
        refresh_task.cancel()
        await asyncio.gather(refresh_task, return_exceptions=True)



app = FastAPI(
    title="ORBITGUARD AI API",
    description="Explainable AI-Assisted Space Debris Collision Detection & Avoidance Decision System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# The browser talks to the Node server, which calls this service server-side, so
# CORS only matters for direct access during development. Origins are listed
# explicitly: a wildcard origin combined with credentials is rejected by browsers.
_origins = os.environ.get(
    "ORBITGUARD_CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5000",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/")
def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "system": "ORBITGUARD AI Decision Support Engine",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/api/v1/health", tags=["System"])
def health():
    """Service status and the provenance of the data being served."""
    world = get_world()
    models = world.uncertainty_models
    return {
        "status": "ok",
        "built_at": world.built_at.isoformat() if world.built_at else None,
        "build_seconds": round(world.build_seconds, 2),
        "objects": len(world.tracks),
        "conjunctions": len(world.events),
        "config": world.config,
        "catalog": world.catalog_snapshots,
        "uncertainty_model": (
            {"learned": True, "regimes": {r: {"source": m.source,
                                              "trained_age_range_days": m.trained_age_range_days}
                                          for r, m in models.items()}}
            if models else {"learned": False, "source": "assumed (no trained model file found)"}
        ),
    }


@app.post("/api/v1/screening/refresh", tags=["System"])
def refresh():
    """Reload the catalog and re-run screening and risk assessment."""
    world = rebuild_world()
    return {"objects": len(world.tracks), "conjunctions": len(world.events),
            "build_seconds": round(world.build_seconds, 2)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
