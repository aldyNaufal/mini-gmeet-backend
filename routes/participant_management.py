# routes/participant_management.py
from fastapi import APIRouter, HTTPException, status
from livekit import api
import logging
from datetime import timedelta
import jwt as jwt_lib
import os
from models.schemas import TokenRequest, TokenResponse
from config.livekit_config import get_livekit_api, livekit_manager

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/token", response_model=TokenResponse)
async def generate_livekit_token(request: TokenRequest):
    """
    Generate a LiveKit access token for joining a room
    Auto-creates room if it doesn't exist
    """
    try:
        logger.info(f"Generating token for user {request.participantName} in room {request.roomName}")
        
        if not request.roomName or not request.participantName:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Room name and participant name are required"
            )
        
        # Read API key & secret from environment at runtime
        api_key = os.getenv("LIVEKIT_API_KEY")
        api_secret = os.getenv("LIVEKIT_API_SECRET")
        ws_url = os.getenv("LIVEKIT_URL")
        
        if not api_key or not api_secret or ws_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="LiveKit credentials are not set"
            )
        
        # Auto-create room if it doesn't exist with configurable max participants
        max_participants = getattr(request, 'maxParticipants', 100)  # Default to 100
        await ensure_room_exists(request.roomName, max_participants)
        
        # Create access token
        token = api.AccessToken(api_key, api_secret)
        token.with_identity(request.participantName)
        token.with_name(request.participantName)
        
        grants = api.VideoGrants(
            room_join=True,
            room=request.roomName,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True
        )
        token.with_grants(grants)
        token.with_ttl(timedelta(hours=24))
        
        if request.metadata:
            token.with_metadata(request.metadata)
        
        jwt_token = token.to_jwt()
        
        # Debug: log token payload
        try:
            decoded = jwt_lib.decode(jwt_token, options={"verify_signature": False})
            logger.info(f"Token payload: {decoded}")
        except Exception as e:
            logger.warning(f"Could not decode token for debugging: {e}")
        
        return TokenResponse(
            token=jwt_token,
            wsUrl=ws_url,
            roomName=request.roomName,
            participantName=request.participantName
        )
        
    except Exception as e:
        logger.error(f"Error generating token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate access token: {str(e)}"
        )

async def ensure_room_exists(room_name: str, max_participants: int = 100):
    """Ensure a room exists, create it if it doesn't"""
    try:
        # Use the context manager for proper cleanup
        async with get_livekit_api() as lk_api:
            # Check if room exists
            list_request = api.ListRoomsRequest()
            rooms_response = await lk_api.room.list_rooms(list_request)
            
            # Check if room already exists
            for room in rooms_response.rooms:
                if room.name == room_name:
                    logger.info(f"Room {room_name} already exists")
                    return
            
            # Create room if it doesn't exist
            room_opts = api.CreateRoomRequest(
                name=room_name,
                max_participants=max_participants,  # Now configurable!
                metadata=""
            )
            
            room = await lk_api.room.create_room(room_opts)
            logger.info(f"Successfully created room: {room_name} with SID: {room.sid} (max: {max_participants} participants)")
            
    except Exception as e:
        logger.error(f"Error ensuring room exists: {str(e)}")
        # Don't raise here - room might exist but listing failed
        # The token will still work if the room exists

# Rest of your existing code remains the same...
@router.get("/room/{room_name}/participants")
async def get_room_participants(room_name: str):
    """
    Get list of participants in a room
    """
    try:
        async with get_livekit_api() as lk_api:
            participants_request = api.ListParticipantsRequest(room=room_name)
            participants_response = await lk_api.room.list_participants(participants_request)
            
            participant_list = []
            for p in participants_response.participants:
                participant_list.append({
                    "identity": p.identity,
                    "name": p.name,
                    "sid": p.sid,
                    "state": p.state.name if hasattr(p.state, 'name') else str(p.state),
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

@router.post("/room/{room_name}/mute/{participant_identity}")
async def mute_participant(room_name: str, participant_identity: str):
    """
    Mute a participant's audio
    """
    try:
        async with get_livekit_api() as lk_api:
            mute_request = api.MuteRoomTrackRequest(
                room=room_name,
                identity=participant_identity,
                track_sid="",  # Will mute all audio tracks
                muted=True
            )
            await lk_api.room.mute_published_track(mute_request)
            
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

@router.post("/room/{room_name}/unmute/{participant_identity}")
async def unmute_participant(room_name: str, participant_identity: str):
    """
    Unmute a participant's audio  
    """
    try:
        async with get_livekit_api() as lk_api:
            unmute_request = api.MuteRoomTrackRequest(
                room=room_name,
                identity=participant_identity,
                track_sid="",  # Will unmute all audio tracks
                muted=False
            )
            await lk_api.room.mute_published_track(unmute_request)
            
            return {
                "roomName": room_name,
                "participantIdentity": participant_identity,
                "status": "unmuted"
            }
        
    except Exception as e:
        logger.error(f"Error unmuting participant: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unmute participant: {str(e)}"
        )

@router.post("/room/{room_name}/kick/{participant_identity}")
async def kick_participant(room_name: str, participant_identity: str):
    """
    Remove a participant from the room
    """
    try:
        async with get_livekit_api() as lk_api:
            remove_request = api.RoomParticipantIdentity(
                room=room_name,
                identity=participant_identity
            )
            await lk_api.room.remove_participant(remove_request)
            
            return {
                "roomName": room_name,
                "participantIdentity": participant_identity,
                "status": "removed"
            }
        
    except Exception as e:
        logger.error(f"Error removing participant: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove participant: {str(e)}"
        )