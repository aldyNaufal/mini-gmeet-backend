import os
from livekit import api
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)

def validate_environment():
    """Validate that all required environment variables are set"""
    required_vars = ["LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "LIVEKIT_URL"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

@asynccontextmanager
async def get_livekit_api():
    """Get configured LiveKit API client with proper cleanup"""
    lk_api = None
    try:
        lk_api = api.LiveKitAPI(
            url=os.getenv("LIVEKIT_URL"),
            api_key=os.getenv("LIVEKIT_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET"),
        )
        yield lk_api
    except Exception as e:
        logger.error(f"Error with LiveKit API: {e}")
        raise
    finally:
        if lk_api:
            try:
                await lk_api.aclose()  # Properly close the client
            except Exception as e:
                logger.warning(f"Error closing LiveKit API client: {e}")

# Alternative: Create a singleton client that's managed at the app level
class LiveKitManager:
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_client(self):
        if self._client is None:
            self._client = api.LiveKitAPI(
                url=os.getenv("LIVEKIT_URL"),
                api_key=os.getenv("LIVEKIT_API_KEY"),
                api_secret=os.getenv("LIVEKIT_API_SECRET"),
            )
        return self._client
    
    async def close_client(self):
        if self._client:
            await self._client.aclose()
            self._client = None

# Global manager instance
livekit_manager = LiveKitManager()