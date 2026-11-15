"""
FastAPI backend for TerraShift ("Every shift tells a story.")
Wraps existing Python analysis modules with REST API
"""
import os
import sys
from pathlib import Path

# Add parent directory to path to import modules
backend_dir = Path(__file__).parent.parent
project_root = backend_dir.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables from backend/.env
load_dotenv(backend_dir / ".env")

# Import route modules
from api.routes import analysis, auth, config_routes, data, discovery, geo, globe, maps

# Initialize FastAPI app
app = FastAPI(
    title="TerraShift API",
    description="TerraShift: explore and understand Earth's environmental changes through NASA data. Statistical trend detection on NASA Earth observation data.",
    version="3.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Configure CORS: which websites may call this API from a browser.
# Local development origins are always allowed. Deployed frontends are added with
# ALLOWED_ORIGINS (comma-separated, e.g. "https://terrashift-ptsw.vercel.app").
LOCAL_ORIGINS = [
    "http://localhost:5173",  # Vite default port
    "http://localhost:5174",  # Vite alternate port
    "http://localhost:3000",  # Alternative React port
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:3000",
    "https://terrashift-ptsw.vercel.app",  # the public TerraShift website
]
DEPLOYED_ORIGINS = [
    o.strip().rstrip("/") for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_ORIGINS + DEPLOYED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(config_routes.router, prefix="/api/config", tags=["Configuration"])
app.include_router(data.router, prefix="/api/data", tags=["Data"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(globe.router, prefix="/api/globe", tags=["Globe"])
app.include_router(discovery.router, prefix="/api/discovery", tags=["Discovery"])
app.include_router(maps.router, prefix="/api/maps", tags=["Globe maps"])
app.include_router(geo.router, prefix="/api/geo", tags=["Geocoding"])


@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "name": "TerraShift API",
        "version": "3.0.0",
        "status": "running",
        "docs": "/api/docs",
        "frontend": "React + TypeScript + Three.js",
        "backend": "FastAPI + Python",
        "data": "NASA GES DISC (GPM IMERG, MERRA-2)"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
