import redis.asyncio as redis
import json
import os
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class RedisCache:
    """Cache adapter pour Redis"""
    
    def __init__(self):
        self.redis_url = os.getenv(
            "REDIS_URL",
            "redis://localhost:6379/0"
        )
        self.client = None
    
    async def connect(self):
        """Connecte à Redis"""
        try:
            self.client = await redis.from_url(self.redis_url)
            await self.client.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self):
        """Déconnecte de Redis"""
        if self.client:
            await self.client.close()
    
    async def get(self, key: str) -> Optional[str]:
        """Récupère une valeur du cache"""
        try:
            if not self.client:
                await self.connect()
            
            value = await self.client.get(key)
            if value:
                return value.decode('utf-8')
            return None
        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            return None
    
    async def set(self, key: str, value: str, ttl: int = 3600) -> bool:
        """Définit une valeur dans le cache"""
        try:
            if not self.client:
                await self.connect()
            
            await self.client.setex(key, ttl, value)
            return True
        except Exception as e:
            logger.error(f"Error setting cache: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Supprime une valeur du cache"""
        try:
            if not self.client:
                await self.connect()
            
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting from cache: {e}")
            return False
    
    async def clear(self) -> bool:
        """Vide tout le cache"""
        try:
            if not self.client:
                await self.connect()
            
            await self.client.flushdb()
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False


# Singleton instance
_cache_instance = None


async def get_cache() -> RedisCache:
    """Récupère l'instance de cache (singleton)"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache()
        await _cache_instance.connect()
    return _cache_instance