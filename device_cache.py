import logging
import asyncio
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class DeviceCache:
    def __init__(self, cache_duration: int = 300):  # 5 minutes default
        self.devices: Dict[str, Dict] = {}
        self.last_discovery: Optional[datetime] = None
        self.cache_duration = timedelta(seconds=cache_duration)
        self._lock = asyncio.Lock()
        self._connections: Dict[str, tuple[asyncio.StreamReader, asyncio.StreamWriter]] = {}
        
    async def get_cached_devices(self) -> Optional[List[Dict]]:
        """Get cached devices if they're still valid."""
        async with self._lock:
            if (self.last_discovery and 
                datetime.now() - self.last_discovery < self.cache_duration and 
                self.devices):
                # Check if devices are still reachable
                devices = []
                for device in self.devices.values():
                    try:
                        if await self._check_device_reachable(device['ip']):
                            devices.append(device)
                        else:
                            logger.info(f"Device {device['ip']} no longer reachable")
                    except Exception as e:
                        logger.debug(f"Error checking device {device['ip']}: {e}")
                
                if devices:
                    return devices
                
                # If no devices are reachable, clear cache
                self.devices.clear()
                self.last_discovery = None
                
        return None
        
    async def _check_device_reachable(self, ip: str) -> bool:
        """Check if a device is still reachable."""
        try:
            # Try to open a connection
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, 1255),
                timeout=1.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False
            
    async def update_cache(self, devices: List[Dict]):
        """Update the device cache with new device information."""
        async with self._lock:
            # Close all existing connections
            await self.clear_all_connections()
            
            # Update devices
            self.devices.clear()
            for device in devices:
                if 'ip' in device:
                    self.devices[device['ip']] = device
            self.last_discovery = datetime.now()
            
    async def get_device(self, ip: str) -> Optional[Dict]:
        """Get a specific device from cache if it exists."""
        async with self._lock:
            return self.devices.get(ip)
            
    async def store_connection(self, ip: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Store a connection for reuse."""
        async with self._lock:
            # Close existing connection if any
            await self.clear_connection(ip)
            
            # Store new connection
            self._connections[ip] = (reader, writer)
            logger.debug(f"Stored new connection for {ip}")
    
    # Alias for store_connection to maintain compatibility
    set_connection = store_connection
            
    async def get_connection(self, ip: str) -> Optional[tuple[asyncio.StreamReader, asyncio.StreamWriter]]:
        """Get an existing connection if it's still valid."""
        async with self._lock:
            if ip in self._connections:
                reader, writer = self._connections[ip]
                try:
                    # Test if connection is still valid
                    writer.write(b"heos://system/heart_beat\r\n")
                    await writer.drain()
                    response = await asyncio.wait_for(reader.readuntil(b"\r\n"), timeout=2.0)
                    if b"success" in response:
                        return reader, writer
                    raise ConnectionError("Invalid response")
                except Exception as e:
                    logger.debug(f"Connection test failed for {ip}: {str(e)}")
                    # Connection is dead, remove it
                    await self.clear_connection(ip)
            return None
            
    async def clear_connection(self, ip: str):
        """Close and remove a stored connection."""
        async with self._lock:
            if ip in self._connections:
                reader, writer = self._connections[ip]
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
                del self._connections[ip]
                logger.debug(f"Cleared connection for {ip}")
                
    async def clear_all_connections(self):
        """Close and remove all stored connections."""
        async with self._lock:
            for ip in list(self._connections.keys()):
                await self.clear_connection(ip)
                
    def __del__(self):
        """Cleanup when object is destroyed."""
        for reader, writer in self._connections.values():
            writer.close()
