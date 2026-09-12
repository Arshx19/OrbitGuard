"""
ORBITGUARD AI -- FastAPI application.

Run from the repository root:

    .venv/Scripts/python.exe -m uvicorn app.main:app --app-dir src --reload

Then open http://localhost:8000/docs for the interactive API, and start the
frontend with VITE_API_BASE_URL=http://localhost:8000 to see live results.

The catalog is screened and every conjunction assessed once, at startup, so the
first request is not slow. POST /api/v1/screening/refresh rebuilds it.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import conjunctions, maneuver, risk, satellites
from app.services.world import get_world, rebuild_world

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(name)s: %(message)s")
logger = logging.getLogger("orbitguard")

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    world = get_world()
    logger.info(
        "ORBITGUARD AI ready: %d objects, %d conjunctions, built in %.1f s.",
        len(world.tracks), len(world.events), world.build_seconds,
    )
    yield


app = FastAPI(
    title="ORBITGUARD AI",
    description=(
        "Conjunction screening, collision probability, explainable risk, and "
        "avoidance-maneuver planning over public TLE data."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("ORBITGUARD_CORS_ORIGINS", _default_origins).split(",")],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

for module in (satellites, conjunctions, risk, maneuver):
    app.include_router(module.router, prefix=API_PREFIX)


@app.get(f"{API_PREFIX}/health", tags=["system"])
def health():
    """Service status and the provenance of the data being served."""
    world = get_world()
    return {
        "status": "ok",
        "built_at": world.built_at.isoformat() if world.built_at else None,
        "build_seconds": round(world.build_seconds, 2),
        "objects": len(world.tracks),
        "conjunctions": len(world.events),
        "config": world.config,
        "catalog": world.catalog_snapshots,
    }


@app.post(f"{API_PREFIX}/screening/refresh", tags=["system"])
def refresh():
    """Reload the catalog and re-run screening and risk assessment."""
    world = rebuild_world()
    return {"objects": len(world.tracks), "conjunctions": len(world.events),
            "build_seconds": round(world.build_seconds, 2)}
