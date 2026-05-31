import hashlib
import time
from typing import Optional

class ResponseCache:
    """In memory cache with TTL"""

    def __init__(self,ttl_seconds:int=300):
        self.ttl_seconds = ttl_seconds
        self.cache:dict[str, dict] = {}
        self.hits = 0
        self.misses = 0

    def _make_key(self,query:str)-> str:
        """Create a hash key for the normalized query"""
        normalized = query.strip().lower()
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def get(self,query:str)->Optional[str]:
        """Get cached response if valid"""
        key = self._make_key(query)
        
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry['timestamp'] < self.ttl_seconds:
                self.hits += 1
                return entry['response']
            else:
                del self._cache[key]  # Expired
        self.misses += 1
        return None 

    def set(self,query:str,response:str) -> None:
        """Cache a response"""
        key = self._make_key(query)
        self._cache[key] = {
            "response": response,
            "timestamp": time.time(),
            "query": query,
        }

    @property
    def stats(self)->dict:
        """Cache statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0.0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.2f}%",
            "cached_entries": len(self._cache),
        }
