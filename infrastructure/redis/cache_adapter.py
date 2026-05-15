from typing import Optional, Any


class RedisCache:
    """
    Cache adapter pour Redis
    """
    
    def __init__(self):
        # Redis client à initialiser
        self.redis = None
    
    async def get(self, key: str) -> Optional[str]:
        """Gets a value from cache"""
        # TODO: Implémenter avec redis-py
        return None
    
    async def set(self, key: str, value: str, ttl: int = 3600) -> None:
        """Sets a value in cache with TTL"""
        # TODO: Implémenter avec redis-py
        pass
    
    async def delete(self, key: str) -> None:
        """Deletes a value from cache"""
        # TODO: Implémenter avec redis-py
        pass