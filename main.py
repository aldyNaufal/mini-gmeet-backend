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

# Configure logging
logging.basicConfig(level=logging.INFO)
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
    lifespan=lifespan
)

# Configure CORS for production deployment
allowed_origins = [
    "http://localhost:5173",  # Keep for local development
    "https://localhost:5173",  # HTTPS local development
]

# Add production frontend URL from environment variable
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    allowed_origins.append(frontend_url)
    logger.info(f"Added frontend URL to CORS: {frontend_url}")

# Allow all Vercel preview deployments
allowed_origins.extend([
    "https://*.vercel.app",
    "https://*.vercel.com"
])

# In development, allow all origins for easier testing
if os.getenv("ENVIRONMENT") == "development":
    allowed_origins = ["*"]
    logger.info("Development mode: allowing all CORS origins")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,  
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(room_router, prefix="/api/livekit", tags=["Room Management"])
app.include_router(participant_router, prefix="/api/livekit", tags=["Participant Management"])

@app.get("/")
async def root():
    return {
        "message": "LiveKit Video Conference API",
        "status": "running",
        "environment": os.getenv("ENVIRONMENT", "production"),
        "frontend_url": os.getenv("FRONTEND_URL", "not set"),
        "endpoints": {
            "generate_token": "/api/livekit/token",
            "create_room": "/api/livekit/room",
            "list_rooms": "/api/livekit/rooms",
            "room_info": "/api/livekit/room/{room_name}",
            "participants": "/api/livekit/room/{room_name}/participants",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for Railway deployment"""
    livekit_configured = bool(
        os.getenv("LIVEKIT_API_KEY") and 
        os.getenv("LIVEKIT_API_SECRET") and 
        os.getenv("LIVEKIT_URL")
    )
    
    return {
        "status": "healthy",
        "livekit_configured": livekit_configured,
        "environment": os.getenv("ENVIRONMENT", "production"),
        "frontend_url": os.getenv("FRONTEND_URL", "not set"),
        "cors_origins": len(allowed_origins) if allowed_origins != ["*"] else "all"
    }

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Endpoint not found",
            "message": "The requested endpoint does not exist",
            "available_endpoints": [
                "/api/livekit/token",
                "/api/livekit/room",
                "/api/livekit/rooms",
                "/api/livekit/room/{room_name}",
                "/api/livekit/room/{room_name}/participants", 
                "/health"
            ]
        }
    )

@app.exception_handler(500)
async def internal_server_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later."
        }
    )

if __name__ == "__main__":
    # Railway provides PORT environment variable
    port = int(os.getenv("PORT", 8000))
    
    # Use reload=False in production
    reload_mode = os.getenv("ENVIRONMENT") == "development"
    
    logger.info(f"Starting server on port {port} with reload={reload_mode}")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=reload_mode,
        log_level="info"
    )