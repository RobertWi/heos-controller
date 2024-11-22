import time
import logging
from typing import List, Dict, Any, Optional
from threading import Lock

logger = logging.getLogger(__name__)

class DeviceCache:
    def __init__(self, cache_duration: int = 300):  # 5 minutes default
        self._devices: List[Dict[str, Any]] = []
        self._last_update: float = 0
        self._cache_duration: int = cache_duration
        self._lock = Lock()

    def update_devices(self, devices: List[Dict[str, Any]]) -> None:
        """Update the cache with new devices."""
        with self._lock:
            self._devices = sorted(devices, key=lambda x: x['name'])
            self._last_update = time.time()
            logger.info(f"Cache updated with {len(devices)} devices")

    def get_devices(self) -> Optional[List[Dict[str, Any]]]:
        """Get devices from cache if not expired."""
        with self._lock:
            if not self._devices:
                logger.debug("Cache empty")
                return None
                
            if time.time() - self._last_update > self._cache_duration:
                logger.debug("Cache expired")
                return None
                
            logger.debug(f"Returning {len(self._devices)} devices from cache")
            return self._devices.copy()

    def clear(self) -> None:
        """Clear the cache."""
        with self._lock:
            self._devices = []
            self._last_update = 0
            logger.debug("Cache cleared")
