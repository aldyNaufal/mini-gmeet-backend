# models/schemas.py
from pydantic import BaseModel
from typing import Optional, List

# Token-related models
class TokenRequest(BaseModel):
    roomName: str
    participantName: str
    metadata: Optional[str] = None
    maxParticipants: Optional[int] = 100  # Added this field!

class TokenResponse(BaseModel):
    token: str
    wsUrl: str
    roomName: str
    participantName: str

# Room-related models
class CreateRoomRequest(BaseModel):
    roomName: str
    maxParticipants: Optional[int] = 100  # Updated default
    metadata: Optional[str] = None

class RoomInfo(BaseModel):
    name: str
    numParticipants: int
    participants: List[str]
    creationTime: int
    metadata: Optional[str] = None

class RoomResponse(BaseModel):
    roomName: str
    sid: str
    maxParticipants: int
    creationTime: int
    metadata: Optional[str] = None
    status: str

# Participant-related models
class ParticipantInfo(BaseModel):
    identity: str
    name: str
    sid: str
    state: str
    joinedAt: int
    metadata: Optional[str] = None
    permission: dict