from fastapi import APIRouter, HTTPException, status
from livekit import api
import logging
from typing import List
from models.schemas import CreateRoomRequest, RoomInfo, RoomResponse
from config.livekit_config import get_livekit_api

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/room", response_model=RoomResponse)
async def create_room(request: CreateRoomRequest):
    """
    Create a new LiveKit room
    """
    try:
        logger.info(f"Creating room: {request.roomName}")
        
        async with get_livekit_api() as lk_api:
            room_opts = api.CreateRoomRequest(
                name=request.roomName,
                max_participants=request.maxParticipants or 50,
                metadata=request.metadata or ""
            )
            
            room = await lk_api.room.create_room(room_opts)
            
            logger.info(f"Successfully created room: {request.roomName}")
            
            return RoomResponse(
                roomName=room.name,
                sid=room.sid,
                maxParticipants=room.max_participants,
                creationTime=room.creation_time,
                metadata=room.metadata,
                status="created"
            )
        
    except Exception as e:
        logger.error(f"Error creating room: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create room: {str(e)}"
        )

@router.get("/rooms")
async def list_rooms():
    """
    List all active LiveKit rooms
    """
    try:
        async with get_livekit_api() as lk_api:
            list_request = api.ListRoomsRequest()
            rooms_response = await lk_api.room.list_rooms(list_request)
            
            room_list = []
            for room in rooms_response.rooms:
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

@router.get("/room/{room_name}", response_model=RoomInfo)
async def get_room_info(room_name: str):
    """
    Get detailed information about a specific room
    """
    try:
        async with get_livekit_api() as lk_api:
            list_request = api.ListRoomsRequest()
            rooms_response = await lk_api.room.list_rooms(list_request)
            
            for room in rooms_response.rooms:
                if room.name == room_name:
                    # Get participants
                    participants_request = api.ListParticipantsRequest(room=room_name)
                    participants_response = await lk_api.room.list_participants(participants_request)
                    
                    participant_names = [p.name for p in participants_response.participants]
                    
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

@router.delete("/room/{room_name}")
async def delete_room(room_name: str):
    """
    Delete a LiveKit room
    """
    try:
        async with get_livekit_api() as lk_api:
            delete_request = api.DeleteRoomRequest(room=room_name)
            await lk_api.room.delete_room(delete_request)
            
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