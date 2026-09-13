"""API v1 router module."""

from fastapi import APIRouter
from app.api.v1.satellites import router as satellites_router
from app.api.v1.conjunctions import router as conjunctions_router
from app.api.v1.risk import router as risk_router
from app.api.v1.maneuver import router as maneuver_router
from app.api.v1.explain import router as explain_router

router = APIRouter()

router.include_router(satellites_router, tags=["Satellites"])
router.include_router(conjunctions_router, tags=["Conjunctions"])
router.include_router(risk_router, tags=["Risk Analysis"])
router.include_router(maneuver_router, tags=["Maneuver Optimization"])
router.include_router(explain_router, tags=["Explain Decision"])
