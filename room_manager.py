from typing import Dict
from fastapi import WebSocket
import json

class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, room_id: str, user_id: str, websocket: WebSocket):
        if room_id not in self.rooms:
            self.rooms[room_id] = {}
        self.rooms[room_id][user_id] = websocket
        # Notify others
        await self.broadcast(room_id, {
            "type": "user-joined",
            "from": user_id
        }, exclude=user_id)

    async def disconnect(self, room_id: str, user_id: str):
        if room_id in self.rooms and user_id in self.rooms[room_id]:
            del self.rooms[room_id][user_id]
            # Notify others
            await self.broadcast(room_id, {
                "type": "user-left",
                "from": user_id
            })

    async def send_to(self, room_id: str, user_id: str, message: dict):
        if room_id in self.rooms and user_id in self.rooms[room_id]:
            websocket = self.rooms[room_id][user_id]
            await websocket.send_text(json.dumps(message))

    async def broadcast(self, room_id: str, message: dict, exclude: str = None):
        if room_id in self.rooms:
            for uid, ws in self.rooms[room_id].items():
                if uid != exclude:
                    await ws.send_text(json.dumps(message))
