# main.py
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from livekit import api, rtc
import os
from dotenv import load_dotenv
import logging
from typing import Optional, List
import asyncio
import uvicorn
from datetime import timedelta 
from fastapi.responses import JSONResponse

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="LiveKit Video Conference API",
    description="Complete LiveKit integration for video conferencing",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class TokenRequest(BaseModel):
    roomName: str
    participantName: str
    metadata: Optional[str] = None

class TokenResponse(BaseModel):
    token: str
    wsUrl: str
    roomName: str
    participantName: str

class RoomInfo(BaseModel):
    name: str
    numParticipants: int
    participants: List[str]
    creationTime: int
    metadata: Optional[str] = None

class CreateRoomRequest(BaseModel):
    roomName: str
    maxParticipants: Optional[int] = 50
    metadata: Optional[str] = None

# Environment variables validation
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
LIVEKIT_URL = os.getenv("LIVEKIT_URL")

if not all([LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL]):
    raise RuntimeError("Missing required environment variables: LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL")

# Initialize LiveKit API client
lk_api = api.LiveKitAPI(
    url=LIVEKIT_URL,
    api_key=LIVEKIT_API_KEY,
    api_secret=LIVEKIT_API_SECRET,
)

@app.get("/")
async def root():
    return {
        "message": "LiveKit Video Conference API",
        "status": "running",
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
    return {
        "status": "healthy",
        "livekit_configured": bool(LIVEKIT_API_KEY and LIVEKIT_API_SECRET and LIVEKIT_URL)
    }

@app.post("/api/livekit/token", response_model=TokenResponse)
async def generate_livekit_token(request: TokenRequest):
    """
    Generate a LiveKit access token for joining a room
    """
    try:
        logger.info(f"Generating token for user {request.participantName} in room {request.roomName}")
        
        # Validate input
        if not request.roomName or not request.participantName:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Room name and participant name are required"
            )
        
        # Create access token with comprehensive permissions
        token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        token.with_identity(request.participantName)
        token.with_name(request.participantName)
        
        # Create video grants
        grants = api.VideoGrants(
            room_join=True,
            room=request.roomName,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True
        )
        token.with_grants(grants)
        token.with_ttl(timedelta(hours=24))
        
        # Add metadata if provided
        if request.metadata:
            token.with_metadata(request.metadata)
        
        jwt_token = token.to_jwt()
        
        # Debug: Log token details (remove in production)
        import jwt as jwt_lib
        try:
            decoded = jwt_lib.decode(jwt_token, options={"verify_signature": False})
            logger.info(f"Token payload: {decoded}")
        except Exception as e:
            logger.warning(f"Could not decode token for debugging: {e}")
        
        logger.info(f"Successfully generated token for {request.participantName}")
        
        return TokenResponse(
            token=jwt_token,
            wsUrl=LIVEKIT_URL,
            roomName=request.roomName,
            participantName=request.participantName
        )
        
    except Exception as e:
        logger.error(f"Error generating token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate access token: {str(e)}"
        )

@app.post("/api/livekit/room")
async def create_room(request: CreateRoomRequest):
    """
    Create a new LiveKit room
    """
    try:
        logger.info(f"Creating room: {request.roomName}")
        
        room_opts = api.CreateRoomRequest(
            name=request.roomName,
            max_participants=request.maxParticipants or 50,
            metadata=request.metadata or ""
        )
        
        room = await lk_api.room.create_room(room_opts)
        
        logger.info(f"Successfully created room: {request.roomName}")
        
        return {
            "roomName": room.name,
            "sid": room.sid,
            "maxParticipants": room.max_participants,
            "creationTime": room.creation_time,
            "metadata": room.metadata,
            "status": "created"
        }
        
    except Exception as e:
        logger.error(f"Error creating room: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create room: {str(e)}"
        )

@app.get("/api/livekit/rooms")
async def list_rooms():
    """
    List all active LiveKit rooms
    """
    try:
        rooms = await lk_api.room.list_rooms()
        
        room_list = []
        for room in rooms:
            room_list.append({
                "name": room.name,
                "sid": room.sid,
                "numParticipants": room.num_participants,
                "maxParticipants": room.max_participants,
                "creationTime": room.creation_time,
                "metadata": room.metadata
            })
        
        return {
            "rooms": room_list,
            "total": len(room_list)
        }
        
    except Exception as e:
        logger.error(f"Error listing rooms: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list rooms: {str(e)}"
        )

@app.get("/api/livekit/room/{room_name}")
async def get_room_info(room_name: str):
    """
    Get detailed information about a specific room
    """
    try:
        rooms = await lk_api.room.list_rooms()
        
        for room in rooms:
            if room.name == room_name:
                # Get participants
                participants = await lk_api.room.list_participants(
                    api.ListParticipantsRequest(room=room_name)
                )
                
                participant_names = [p.name for p in participants]
                
                return RoomInfo(
                    name=room.name,
                    numParticipants=room.num_participants,
                    participants=participant_names,
                    creationTime=room.creation_time,
                    metadata=room.metadata
                )
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room '{room_name}' not found"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting room info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get room information: {str(e)}"
        )

@app.get("/api/livekit/room/{room_name}/participants")
async def get_room_participants(room_name: str):
    """
    Get list of participants in a room
    """
    try:
        participants = await lk_api.room.list_participants(
            api.ListParticipantsRequest(room=room_name)
        )
        
        participant_list = []
        for p in participants:
            participant_list.append({
                "identity": p.identity,
                "name": p.name,
                "sid": p.sid,
                "state": p.state.name,
                "joinedAt": p.joined_at,
                "metadata": p.metadata,
                "permission": {
                    "canPublish": p.permission.can_publish,
                    "canSubscribe": p.permission.can_subscribe,
                    "canPublishData": p.permission.can_publish_data
                }
            })
        
        return {
            "roomName": room_name,
            "participants": participant_list,
            "total": len(participant_list)
        }
        
    except Exception as e:
        logger.error(f"Error getting participants: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get room participants: {str(e)}"
        )

@app.delete("/api/livekit/room/{room_name}")
async def delete_room(room_name: str):
    """
    Delete a LiveKit room
    """
    try:
        await lk_api.room.delete_room(api.DeleteRoomRequest(room=room_name))
        
        logger.info(f"Successfully deleted room: {room_name}")
        
        return {
            "roomName": room_name,
            "status": "deleted",
            "message": f"Room '{room_name}' has been deleted"
        }
        
    except Exception as e:
        logger.error(f"Error deleting room: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete room: {str(e)}"
        )

@app.post("/api/livekit/room/{room_name}/mute/{participant_identity}")
async def mute_participant(room_name: str, participant_identity: str):
    """
    Mute a participant's audio
    """
    try:
        await lk_api.room.mute_published_track(
            api.MuteRoomTrackRequest(
                room=room_name,
                identity=participant_identity,
                track_sid="",  # Will mute all audio tracks
                muted=True
            )
        )
        
        return {
            "roomName": room_name,
            "participantIdentity": participant_identity,
            "status": "muted"
        }
        
    except Exception as e:
        logger.error(f"Error muting participant: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mute participant: {str(e)}"
        )

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

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )