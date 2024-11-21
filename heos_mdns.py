#!/usr/bin/env python3

import asyncio
import logging
from zeroconf.asyncio import AsyncZeroconf, AsyncServiceBrowser
from typing import List, Dict, Set, Optional
import socket
import time
import json
from device_cache import DeviceCache
import aiohttp
import xml.etree.ElementTree as ET
import async_upnp_client.aiohttp
from async_upnp_client.search import async_search

# Configure logging
logging.basicConfig(level=logging.DEBUG)  # Changed from INFO to DEBUG
logger = logging.getLogger(__name__)

# Global device cache instance
device_cache = DeviceCache()

# Discovery timeouts
DISCOVERY_TIMEOUT = 10  # 10 seconds for complete discovery
DEVICE_INFO_TIMEOUT = 5.0  # 5 seconds for device info fetch
CONNECTION_TIMEOUT = 10.0  # 10 seconds for connection operations
MAX_RETRIES = 3
BACKOFF_FACTOR = 2.0

# HEOS service types
HEOS_SERVICE_TYPES = [
    "_heos._tcp.local.",
    "_raop._tcp.local.",
    "_airplay._tcp.local.",
    "_spotify-connect._tcp.local.",
]

class HeosListener:
    def __init__(self):
        self.discovered_event = asyncio.Event()
        self.services_found = set()
        self.devices = {}

    def remove_service(self, zc: AsyncZeroconf, type_: str, name: str) -> None:
        """Handle service removal."""
        logger.info(f"Service {name} removed")
        self.services_found.discard(name)

    def add_service(self, zc: AsyncZeroconf, type_: str, name: str) -> None:
        """Non-async callback for service discovery."""
        asyncio.create_task(self._async_add_service(zc, type_, name))

    async def _async_add_service(self, zc: AsyncZeroconf, type_: str, name: str) -> None:
        """Async handler for service discovery."""
        info = await zc.async_get_service_info(type_, name)
        if info:
            logger.info(f"Found device: {name} (type: {type_})")
            # Get IP address (first IPv4 address)
            ip = None
            for addr in info.addresses:
                ip_str = socket.inet_ntoa(addr)
                if not ip_str.startswith('169.254'):  # Skip link-local addresses
                    ip = ip_str
                    break
            
            if ip:
                # Only add if we haven't seen this IP before
                if ip not in self.devices:
                    self.devices[ip] = {
                        'name': info.name.split('.')[0],
                        'ip': ip,
                        'port': info.port,
                        'model': info.properties.get(b'model', b'Unknown').decode(),
                        'version': info.properties.get(b'vers', b'Unknown').decode(),
                        'network': info.properties.get(b'networkid', b'Unknown').decode(),
                        'serial': info.properties.get(b'did', b'Unknown').decode()
                    }
                    logger.info(f"Found device: {name} at {ip} (type: {type_})")
                    self.services_found.add(name)
                    self.discovered_event.set()

    def update_service(self, zc: AsyncZeroconf, type_: str, name: str) -> None:
        """Handle service updates."""
        asyncio.create_task(self._async_add_service(zc, type_, name))

async def discover_heos_mdns(timeout: int = DISCOVERY_TIMEOUT) -> List[Dict]:
    """Discover HEOS devices using mDNS."""
    logger.info("Starting HEOS device discovery via mDNS...")
    
    aiozc = AsyncZeroconf()
    listener = HeosListener()
    browsers = []
    
    try:
        # Start mDNS discovery
        for service_type in HEOS_SERVICE_TYPES:
            browser = AsyncServiceBrowser(aiozc.zeroconf, service_type, listener)
            browsers.append(browser)
        
        # Wait for discovery results
        await asyncio.sleep(timeout)
        
        # Query each discovered device for additional info
        devices = []
        for ip, device_info in listener.devices.items():
            try:
                # Try to connect and get player info
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, 1255),
                    timeout=CONNECTION_TIMEOUT
                )
                
                try:
                    # Store connection in cache
                    await device_cache.store_connection(ip, reader, writer)
                    
                    # Get player info
                    player_info = await get_detailed_player_info(ip, reader, writer, device_info)
                    if player_info:
                        devices.append(player_info)
                    else:
                        devices.append(create_error_device(ip, "Failed to get player info"))
                except Exception as e:
                    logger.error(f"Error getting player info for {ip}: {str(e)}")
                    devices.append(create_error_device(ip, str(e)))
            except Exception as e:
                logger.error(f"Error connecting to {ip}: {str(e)}")
                devices.append(create_error_device(ip, str(e)))
        
        # Update device cache with discovered devices
        if devices:
            await device_cache.update_cache(devices)
            
        return devices
    finally:
        await aiozc.async_close()

# HEOS CLI Protocol commands based on official specification
HEOS_COMMANDS = {
    # System commands (Section 5.1)
    'system/heart_beat': 'heos://system/heart_beat',  # Keep alive
    'system/register_for_change_events': 'heos://system/register_for_change_events?enable=on',  # Subscribe to change events
    'system/check_account': 'heos://system/check_account',  # Account status
    'system/sign_in': 'heos://system/sign_in?un={un}&pw={pw}',  # Sign in
    'system/sign_out': 'heos://system/sign_out',  # Sign out
    'system/reboot': 'heos://system/reboot',  # Reboot player
    'system/prettify': 'heos://system/prettify_json_response?enable=on',  # Enable pretty JSON

    # Player commands (Section 5.2)
    'player/get_players': 'heos://player/get_players',  # Get available players
    'player/get_player_info': 'heos://player/get_player_info?pid={pid}',  # Get player info
    'player/get_play_state': 'heos://player/get_play_state?pid={pid}',  # Get play state
    'player/set_play_state': 'heos://player/set_play_state?pid={pid}&state={state}',  # Set play state
    'player/get_now_playing_media': 'heos://player/get_now_playing_media?pid={pid}',  # Get now playing
    'player/get_volume': 'heos://player/get_volume?pid={pid}',  # Get volume
    'player/set_volume': 'heos://player/set_volume?pid={pid}&level={level}',  # Set volume
    'player/volume_up': 'heos://player/volume_up?pid={pid}&step={step}',  # Volume up
    'player/volume_down': 'heos://player/volume_down?pid={pid}&step={step}',  # Volume down
    'player/get_mute': 'heos://player/get_mute?pid={pid}',  # Get mute
    'player/set_mute': 'heos://player/set_mute?pid={pid}&state={state}',  # Set mute
    'player/toggle_mute': 'heos://player/toggle_mute?pid={pid}',  # Toggle mute
    'player/get_play_mode': 'heos://player/get_play_mode?pid={pid}',  # Get play mode
    'player/set_play_mode': 'heos://player/set_play_mode?pid={pid}&repeat={repeat}&shuffle={shuffle}',  # Set play mode
    'player/get_queue': 'heos://player/get_queue?pid={pid}&range={range}',  # Get queue
    
    # Group commands (Section 5.3)
    'group/get_groups': 'heos://group/get_groups',  # Get groups
    'group/get_group_info': 'heos://group/get_group_info?gid={gid}',  # Get group info
    'group/set_group': 'heos://group/set_group?pid={pid}&gid={gid}',  # Set group
    'group/get_volume': 'heos://group/get_volume?gid={gid}',  # Get group volume
    'group/set_volume': 'heos://group/set_volume?gid={gid}&level={level}',  # Set group volume
    'group/get_mute': 'heos://group/get_mute?gid={gid}',  # Get group mute
    'group/set_mute': 'heos://group/set_mute?gid={gid}&state={state}',  # Set group mute
    'group/toggle_mute': 'heos://group/toggle_mute?gid={gid}',  # Toggle group mute
    'group/volume_up': 'heos://group/volume_up?gid={gid}&step={step}',  # Group volume up
    'group/volume_down': 'heos://group/volume_down?gid={gid}&step={step}',  # Group volume down

    # Browse commands (Section 5.4)
    'browse/get_music_sources': 'heos://browse/get_music_sources',  # Get music sources
    'browse/browse_source': 'heos://browse/browse?sid={sid}',  # Browse source
    'browse/play_stream': 'heos://browse/play_stream?pid={pid}&sid={sid}&cid={cid}&mid={mid}',  # Play stream
    'browse/add_to_queue': 'heos://browse/add_to_queue?pid={pid}&sid={sid}&cid={cid}&aid={aid}',  # Add to queue
}

async def establish_connection(ip: str, max_retries: int = MAX_RETRIES) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Establish a connection to a HEOS device."""
    retry_count = 0
    last_error = None
    
    while retry_count < max_retries:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, 1255),
                timeout=CONNECTION_TIMEOUT
            )
            # Set TCP keepalive
            sock = writer.transport.get_extra_info('socket')
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # Set TCP keepalive parameters (Linux specific)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
            
            return reader, writer
            
        except Exception as e:
            last_error = e
            retry_count += 1
            if retry_count < max_retries:
                await asyncio.sleep(BACKOFF_FACTOR ** retry_count)
            logger.warning(f"Connection attempt {retry_count} failed for {ip}: {e}")
            
    logger.error(f"Failed to establish connection to {ip} after {max_retries} attempts: {last_error}")
    raise ConnectionError(f"Failed to connect to {ip}: {last_error}")

async def get_detailed_player_info(ip: str, reader, writer, player_info) -> dict:
    """Get detailed player information using HEOS CLI commands according to protocol spec."""
    try:
        # Enable pretty JSON for easier parsing
        cmd = HEOS_COMMANDS['system/prettify'] + "\r\n"
        writer.write(cmd.encode())
        await writer.drain()
        await reader.readuntil(b"\r\n")
        
        # Get player info (Section 5.2)
        cmd = HEOS_COMMANDS['player/get_player_info'].format(pid=player_info['pid']) + "\r\n"
        writer.write(cmd.encode())
        await writer.drain()
        player_response = await reader.readuntil(b"\r\n")
        player_data = json.loads(player_response.decode().strip())
        
        # Get play state (Section 5.2)
        cmd = HEOS_COMMANDS['player/get_play_state'].format(pid=player_info['pid']) + "\r\n"
        writer.write(cmd.encode())
        await writer.drain()
        state_response = await reader.readuntil(b"\r\n")
        state_data = json.loads(state_response.decode().strip())
        
        # Get now playing media (Section 5.2)
        cmd = HEOS_COMMANDS['player/get_now_playing_media'].format(pid=player_info['pid']) + "\r\n"
        writer.write(cmd.encode())
        await writer.drain()
        media_response = await reader.readuntil(b"\r\n")
        media_data = json.loads(media_response.decode().strip())
        
        # Get volume (Section 5.2)
        cmd = HEOS_COMMANDS['player/get_volume'].format(pid=player_info['pid']) + "\r\n"
        writer.write(cmd.encode())
        await writer.drain()
        volume_response = await reader.readuntil(b"\r\n")
        volume_data = json.loads(volume_response.decode().strip())
        
        # Get mute state (Section 5.2)
        cmd = HEOS_COMMANDS['player/get_mute'].format(pid=player_info['pid']) + "\r\n"
        writer.write(cmd.encode())
        await writer.drain()
        mute_response = await reader.readuntil(b"\r\n")
        mute_data = json.loads(mute_response.decode().strip())
        
        # Get play mode (Section 5.2)
        cmd = HEOS_COMMANDS['player/get_play_mode'].format(pid=player_info['pid']) + "\r\n"
        writer.write(cmd.encode())
        await writer.drain()
        mode_response = await reader.readuntil(b"\r\n")
        mode_data = json.loads(mode_response.decode().strip())
        
        # Get queue (Section 5.2)
        cmd = HEOS_COMMANDS['player/get_queue'].format(pid=player_info['pid'], range='0,10') + "\r\n"
        writer.write(cmd.encode())
        await writer.drain()
        queue_response = await reader.readuntil(b"\r\n")
        queue_data = json.loads(queue_response.decode().strip())
        
        # Get group info (Section 5.3)
        cmd = HEOS_COMMANDS['group/get_groups'] + "\r\n"
        writer.write(cmd.encode())
        await writer.drain()
        group_response = await reader.readuntil(b"\r\n")
        group_data = json.loads(group_response.decode().strip())
        
        # Combine all information according to protocol spec
        detailed_info = {
            "player": player_data.get("payload", {}),
            "state": {
                "play_state": state_data.get("payload", {}).get("state", "stop"),
                "volume": volume_data.get("payload", {}).get("level", 0),
                "mute": mute_data.get("payload", {}).get("state", "off"),
                "play_mode": {
                    "repeat": mode_data.get("payload", {}).get("repeat", "off"),
                    "shuffle": mode_data.get("payload", {}).get("shuffle", "off")
                }
            },
            "media": media_data.get("payload", {}),
            "queue": queue_data.get("payload", [])[:10],  # First 10 items
            "group": next((g for g in group_data.get("payload", []) 
                         if str(player_info['pid']) in [p.get("pid") for p in g.get("players", [])]), 
                        None)
        }
        
        return detailed_info
        
    except Exception as e:
        logger.error(f"Error getting detailed player info: {e}")
        return {}

async def get_cached_player_id(ip: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> str:
    """Get the player ID from a HEOS device."""
    try:
        # Send get_players command
        cmd = HEOS_COMMANDS['player/get_players'] + "\r\n"
        writer.write(cmd.encode())
        await writer.drain()
        
        # Wait for response
        response = await asyncio.wait_for(
            reader.readuntil(b"\r\n"),
            timeout=DEVICE_INFO_TIMEOUT
        )
        
        # Parse response
        response_str = response.decode().strip()
        try:
            response_data = json.loads(response_str)
            if 'payload' in response_data:
                for player in response_data['payload']:
                    if 'ip' in player and player['ip'] == ip:
                        return player['pid']
        except json.JSONDecodeError:
            logger.error(f"Failed to parse player info response: {response_str}")
            
        raise ValueError(f"Failed to get player ID for {ip}")
    except Exception as e:
        logger.error(f"Error getting player ID for {ip}: {e}")
        raise ValueError(f"Failed to get player ID: {e}")

async def send_heos_command(ip: str, command: str, params: dict = None) -> Optional[Dict]:
    """Send a command to a HEOS device and get the response."""
    logger.info(f"Processing command for {ip}: {command} with params {params}")
    
    try:
        # Try to get existing connection
        connection = await device_cache.get_connection(ip)
        if connection is None:
            # No valid connection, establish new one
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, 1255),
                timeout=CONNECTION_TIMEOUT
            )
            await device_cache.store_connection(ip, reader, writer)
        else:
            reader, writer = connection
        
        # Construct command string
        cmd = f"heos://{command}"
        if params:
            param_str = "&".join(f"{k}={v}" for k, v in params.items())
            cmd += f"?{param_str}"
        cmd += "\r\n"
        
        # Send command
        writer.write(cmd.encode())
        await writer.drain()
        
        # Read response
        try:
            response = await asyncio.wait_for(
                reader.readuntil(b"\r\n"),
                timeout=DEVICE_INFO_TIMEOUT
            )
            return json.loads(response.decode())
        except asyncio.TimeoutError:
            raise ConnectionError("Timeout waiting for response")
        except Exception as e:
            raise ConnectionError(f"Error reading response: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error sending command to {ip}: {str(e)}")
        # Clear connection on error
        await device_cache.clear_connection(ip)
        raise

async def get_player_info(ip: str) -> Optional[Dict]:
    try:
        response = await send_heos_command(ip, "player/get_players")
        if not response:
            raise HeosError("No response received")
        
        version_response = await send_heos_command(ip, "system/get_version")
        
        data = response
        if "payload" not in data:
            raise HeosError("Invalid response format - no payload")
                
        player_info = data["payload"]
        if player_info and len(player_info) > 0:
            if 'pid' in player_info[0]:
                player_id_cache[ip] = player_info[0]['pid']
                logger.info(f"Stored player ID {player_info[0]['pid']} for device {ip}")
            
            if version_response and "payload" in version_response:
                for player in player_info:
                    player["version"] = version_response["payload"].get("version", "Unknown")
                    
            return player_info
            
        raise HeosError("Invalid response format")
            
    except HeosError as he:
        logging.error(f"HEOS error for {ip}: {str(he)}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error getting player info for {ip}: {str(e)}")
        raise HeosError(f"Failed to get player info: {str(e)}")

async def check_device_online(ip: str) -> bool:
    """Check if a HEOS device is online and responding."""
    try:
        # Try to get device info with a short timeout
        result = await asyncio.wait_for(
            send_heos_command(ip, "system/heart_beat"),
            timeout=2  # Short timeout for quick response
        )
        return result is not None and "heos" in result
    except Exception:
        return False

async def main():
    try:
        devices = await discover_heos_mdns()
        
        if not devices:
            logger.info("No devices found via mDNS.")
            return
        
        logger.info(f"Found {len(devices)} device(s)")
        
        for device in devices:
            logger.info(f"Querying device at {device['ip']}")
            response = await send_heos_command(device['ip'], "player/get_players")
            logger.info(f"Players on {device['ip']}: {response}")
            
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())

class HeosError(Exception):
    pass

def create_error_device(ip: str, error_message: str) -> Dict:
    """Create a standardized error device entry."""
    return {
        "ip": ip,
        "info": {
            "name": f"HEOS Device ({ip})",
            "model": "Unknown",
            "pid": None,
            "serial": None,
            "error": error_message
        },
        "status": "error"
    }
