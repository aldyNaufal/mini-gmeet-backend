# main.py - Production Updates

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv
import logging
import uvicorn

# Import route modules
from routes.room_management import router as room_router
from routes.participant_management import router as participant_router
from config.livekit_config import validate_environment, livekit_manager

# Load environment variables
load_dotenv()

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle app startup and shutdown"""
    # Startup
    logger.info("Starting up LiveKit Video Conference API")
    try:
        validate_environment()
        logger.info("Environment validation passed")
    except Exception as e:
        logger.error(f"Environment validation failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down LiveKit Video Conference API")
    try:
        await livekit_manager.close_client()
        logger.info("LiveKit client closed successfully")
    except Exception as e:
        logger.warning(f"Error closing LiveKit client: {e}")

app = FastAPI(
    title="LiveKit Video Conference API",
    description="Complete LiveKit integration for video conferencing",
    version="1.0.0",
    lifespan=lifespan,
    # PRODUCTION: Disable docs in production for security
    docs_url="/docs" if os.getenv("RAILWAY_ENVIRONMENT") != "production" else None,
    redoc_url="/redoc" if os.getenv("RAILWAY_ENVIRONMENT") != "production" else None,
)

# PRODUCTION CORS Configuration
def get_allowed_origins():
    """Get allowed origins based on environment"""
    # Default development origins
    default_origins = [
        "http://localhost:3000",
        "http://localhost:5173",  # Vite dev server
    ]
    
    # Add production origins from environment variable
    env_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
    env_origins = [origin.strip() for origin in env_origins if origin.strip()]
    
    # If production origins are set, use them; otherwise use defaults
    if env_origins:
        return env_origins
    else:
        return default_origins + [
            "https://mini-gmeet-frontend.vercel.app",
            "https://mini-gmeet-frontend-git-main-aldynaufals-projects.vercel.app",
        ]

ALLOWED_ORIGINS = get_allowed_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,  
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# PRODUCTION: Add security headers middleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# Add trusted host middleware for production
if os.getenv("RAILWAY_ENVIRONMENT_NAME") == "production":
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").replace("https://", "")
    if railway_domain:
        app.add_middleware(
            TrustedHostMiddleware, 
            allowed_hosts=[railway_domain, "localhost"]
        )

# Include routers
app.include_router(room_router, prefix="/api", tags=["Room Management"])
app.include_router(participant_router, prefix="/api", tags=["Participant Management"])

@app.get("/")
async def root():
    return {
        "message": "LiveKit Video Conference API",
        "status": "running",
        "version": "1.0.0",
        "environment": os.getenv("RAILWAY_ENVIRONMENT_NAME", "development"),
        "endpoints": {
            "generate_token": "/api/token",
            "create_room": "/api/room",
            "list_rooms": "/api/rooms",
            "room_info": "/api/room/{room_name}",
            "participants": "/api/room/{room_name}/participants",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "livekit_configured": bool(
            os.getenv("LIVEKIT_API_KEY") and 
            os.getenv("LIVEKIT_API_SECRET") and 
            os.getenv("LIVEKIT_URL")
        ),
        "environment": os.getenv("RAILWAY_ENVIRONMENT_NAME", "development"),
        "railway_url": os.getenv("RAILWAY_PUBLIC_DOMAIN", "not_set")
    }

# PRODUCTION: Add better error handlers
@app.exception_handler(500)
async def internal_server_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred"
        }
    )

@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Endpoint not found",
            "message": "The requested endpoint does not exist",
            "available_endpoints": [
                "/api/token",
                "/api/room",
                "/api/rooms",
                "/api/room/{room_name}",
                "/api/room/{room_name}/participants", 
                "/health"
            ]
        }
    )

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    # PRODUCTION: Optimized uvicorn settings
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,  # Always False in production
        log_level="info",
        access_log=True,
        # PRODUCTION: Add process management
        workers=1 if os.getenv("RAILWAY_ENVIRONMENT_NAME") == "production" else 1,
    )