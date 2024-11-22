#!/usr/bin/env python3

import asyncio
import json
import logging
import socket
import time
from typing import Dict, List, Optional, Any
from zeroconf.asyncio import AsyncZeroconf, AsyncServiceBrowser
from device_cache import DeviceCache

logger = logging.getLogger(__name__)

# Global device cache instance
device_cache = DeviceCache()

# Discovery timeouts
DISCOVERY_TIMEOUT = 2.0  # Seconds
DEVICE_INFO_TIMEOUT = 0.5  # Seconds
CONNECTION_TIMEOUT = 0.5  # Seconds
MAX_RETRIES = 1

# HEOS CLI Commands (from HEOS CLI Protocol Specification v1.14)
HEOS_COMMANDS = {
    # System Commands (Section 3)
    'system/register_for_change_events': 'heos://system/register_for_change_events?enable=on',
    'system/prettify': 'heos://system/prettify_json_response?enable=on',
    'system/heart_beat': 'heos://system/heart_beat',
    'system/check_account': 'heos://system/check_account',
    
    # Player Commands (Section 5)
    'player/get_players': 'heos://player/get_players',
    'player/get_player_info': 'heos://player/get_player_info?pid={pid}',
    'player/get_play_state': 'heos://player/get_play_state?pid={pid}',
    'player/set_play_state': 'heos://player/set_play_state?pid={pid}&state={state}',
    'player/get_now_playing_media': 'heos://player/get_now_playing_media?pid={pid}',
    'player/get_volume': 'heos://player/get_volume?pid={pid}',
    'player/set_volume': 'heos://player/set_volume?pid={pid}&level={level}',
    'player/volume_up': 'heos://player/volume_up?pid={pid}&step={step}',
    'player/volume_down': 'heos://player/volume_down?pid={pid}&step={step}',
    'player/get_mute': 'heos://player/get_mute?pid={pid}',
    'player/set_mute': 'heos://player/set_mute?pid={pid}&state={state}',
    'player/toggle_mute': 'heos://player/toggle_mute?pid={pid}',
    'player/get_play_mode': 'heos://player/get_play_mode?pid={pid}',
    'player/set_play_mode': 'heos://player/set_play_mode?pid={pid}&repeat={repeat}&shuffle={shuffle}',
    'player/get_queue': 'heos://player/get_queue?pid={pid}&range={range}',
    'player/play_queue': 'heos://player/play_queue?pid={pid}&qid={qid}',
    'player/remove_from_queue': 'heos://player/remove_from_queue?pid={pid}&qid={qid}',
    'player/save_queue': 'heos://player/save_queue?pid={pid}&name={name}',
    'player/clear_queue': 'heos://player/clear_queue?pid={pid}',
    'player/play_next': 'heos://player/play_next?pid={pid}',
    'player/play_previous': 'heos://player/play_previous?pid={pid}',
    
    # Group Commands (Section 6)
    'group/get_groups': 'heos://group/get_groups',
    'group/get_group_info': 'heos://group/get_group_info?gid={gid}',
    'group/set_group': 'heos://group/set_group?pid={pids}',
    'group/get_volume': 'heos://group/get_volume?gid={gid}',
    'group/set_volume': 'heos://group/set_volume?gid={gid}&level={level}',
    'group/get_mute': 'heos://group/get_mute?gid={gid}',
    'group/set_mute': 'heos://group/set_mute?gid={gid}&state={state}',
    'group/toggle_mute': 'heos://group/toggle_mute?gid={gid}'
}

# Service types for HEOS discovery
SERVICE_TYPES = [
    '_heos-audio._tcp.local.',    # Primary HEOS service
]

class HeosListener:
    def __init__(self):
        self.discovered_event = asyncio.Event()
        self.services_found = set()
        self.devices = {}
        self.potential_heos = set()

    def remove_service(self, zc: AsyncZeroconf, type_: str, name: str) -> None:
        """Handle service removal."""
        logger.debug(f"Service {name} removed")
        self.services_found.discard(name)

    def add_service(self, zc: AsyncZeroconf, type_: str, name: str) -> None:
        """Non-async callback for service discovery."""
        logger.debug(f"Found service: {name} of type {type_}")
        if type_ == SERVICE_TYPES[0]:
            logger.info(f"Found HEOS service: {name}")
            self.services_found.add(name)
            self.discovered_event.set()

    def update_service(self, zc: AsyncZeroconf, type_: str, name: str) -> None:
        """Handle service updates."""
        logger.debug(f"Service {name} updated")
        if type_ == SERVICE_TYPES[0] and name not in self.services_found:
            logger.info(f"Found HEOS service from update: {name}")
            self.services_found.add(name)
            self.discovered_event.set()

async def discover_heos_mdns() -> List[Dict[str, Any]]:
    """Discover HEOS devices on the network using mDNS."""
    logger.info("Starting HEOS device discovery via mDNS...")
    
    # Get network interfaces
    import netifaces
    interfaces = netifaces.interfaces()
    logger.info("Network interfaces for discovery:")
    for iface in interfaces:
        addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in addrs:
            for addr in addrs[netifaces.AF_INET]:
                logger.info(f"Interface {iface}: {addr['addr']}")
    
    aiozc = AsyncZeroconf()
    listener = HeosListener()
    browsers = []
    
    try:
        # Browse for HEOS service types
        logger.info(f"Starting mDNS browser for service types: {SERVICE_TYPES}")
        for service_type in SERVICE_TYPES:
            logger.debug(f"Creating browser for {service_type}")
            browser = AsyncServiceBrowser(aiozc.zeroconf, service_type, listener)
            browsers.append(browser)
        
        # Wait for initial discovery
        try:
            logger.info(f"Waiting for services (timeout: {DISCOVERY_TIMEOUT}s)...")
            await asyncio.wait_for(listener.discovered_event.wait(), timeout=DISCOVERY_TIMEOUT)
            logger.info("Initial service found!")
            
            # Brief wait for additional services
            await asyncio.sleep(0.5)
            
            # Now gather info for all discovered services
            devices = []
            logger.info(f"Found {len(listener.services_found)} services")
            for name in listener.services_found:
                try:
                    logger.debug(f"Getting info for service: {name}")
                    info = await aiozc.async_get_service_info(SERVICE_TYPES[0], name)
                    if info:
                        # Get IP address (first IPv4 address)
                        ip = None
                        for addr in info.addresses:
                            ip_str = socket.inet_ntoa(addr)
                            if not ip_str.startswith('169.254'):  # Skip link-local addresses
                                ip = ip_str
                                break
                        
                        if ip:
                            device_name = name.split('.')[0]
                            logger.info(f"Found HEOS device: {device_name} at {ip}")
                            logger.debug(f"Device properties: {info.properties}")
                            
                            device_info = {
                                'name': device_name,
                                'ip': ip,
                                'port': info.port,
                                'model': info.properties.get(b'model', b'Unknown').decode(),
                                'version': info.properties.get(b'vers', b'Unknown').decode(),
                                'network': info.properties.get(b'networkid', b'Unknown').decode(),
                                'serial': info.properties.get(b'did', b'Unknown').decode(),
                                'service_type': SERVICE_TYPES[0]
                            }
                            devices.append(device_info)
                            logger.info(f"Added device: {device_info}")
                            
                except Exception as e:
                    logger.error(f"Error getting service info for {name}: {e}")
            
            # Sort devices by name
            devices.sort(key=lambda x: x['name'])
            logger.info(f"Discovery complete. Found {len(devices)} devices")
            return devices
            
        except asyncio.TimeoutError:
            logger.warning(f"Discovery timeout after {DISCOVERY_TIMEOUT} seconds")
            return []
            
    except Exception as e:
        logger.error(f"Error during discovery: {e}")
        return []
        
    finally:
        # Clean up browsers and zeroconf
        logger.debug("Cleaning up discovery...")
        for browser in browsers:
            await browser.async_cancel()
        await aiozc.async_close()
        logger.debug("Discovery cleanup complete")

async def get_player_id(ip: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> Optional[str]:
    """Get the player ID from a HEOS device using CLI protocol."""
    try:
        # Enable pretty JSON (Section 3.1.2)
        cmd = HEOS_COMMANDS['system/prettify'] + "\r\n"
        writer.write(cmd.encode())
        await writer.drain()
        await reader.readuntil(b"\r\n")
        
        # Get players (Section 5.2)
        cmd = HEOS_COMMANDS['player/get_players'] + "\r\n"
        writer.write(cmd.encode())
        await writer.drain()
        response = await reader.readuntil(b"\r\n")
        
        data = json.loads(response.decode().strip())
        if 'payload' in data and data['payload']:
            # Return the first player ID found
            return str(data['payload'][0].get('pid'))
        return None
        
    except Exception as e:
        logger.error(f"Error getting player ID: {e}")
        return None

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
                await asyncio.sleep(1 ** retry_count)
            logger.warning(f"Connection attempt {retry_count} failed for {ip}: {e}")
            
    logger.error(f"Failed to establish connection to {ip} after {max_retries} attempts: {last_error}")
    raise ConnectionError(f"Failed to connect to {ip}: {last_error}")

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
