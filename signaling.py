from fastapi import WebSocket
from room_manager import RoomManager
import json

room_manager = RoomManager()

async def signaling_endpoint(websocket: WebSocket, room_id: str, user_id: str):
    await websocket.accept()
    await room_manager.connect(room_id, user_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            target_id = message.get("target")
            await room_manager.send_to(room_id, target_id, message)
    except Exception:
        pass
    finally:
        await room_manager.disconnect(room_id, user_id)
