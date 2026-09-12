"""
ORBITGUARD AI - FastAPI Application Entry Point
Decision-Support Layer for Space Debris Collision Avoidance
"""

import sys
import os

# Add src directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import router as api_v1_router

app = FastAPI(
    title="ORBITGUARD AI API",
    description="Explainable AI-Assisted Space Debris Collision Detection & Avoidance Decision System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows React dev server (http://localhost:5173, etc.)
    allow_credentials=True,
    allow_methods=["*"],
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
