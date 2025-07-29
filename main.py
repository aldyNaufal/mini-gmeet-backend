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

# Configure CORS for Vercel frontend
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",  # Vite dev server
    "https://*.vercel.app",  # Your Vercel domain
    "https://mini-gmeet-frontend-git-main-aldynaufals-projects.vercel.app/room",  # Replace with your actual domain
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,  
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
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
        "environment": os.getenv("RAILWAY_ENVIRONMENT", "development")
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
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,  # Disable reload in production
        log_level="info"
    )