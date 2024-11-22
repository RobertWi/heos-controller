#!/usr/bin/env python3

from device_cache import DeviceCache
import logging
from aiohttp import web
import json
import asyncio
from datetime import datetime
from heos_mdns import discover_heos_mdns, send_heos_command, get_player_info
import os
from pathlib import Path
from command_history import CommandHistory

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('heos_app.log')
    ]
)
logger = logging.getLogger(__name__)

# Global state
device_cache = DeviceCache()
current_discovery = None
discovery_lock = asyncio.Lock()
command_history = CommandHistory()

# CORS middleware
@web.middleware
async def cors_middleware(request, handler):
    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

async def cleanup_old_discovery():
    """Clean up any existing discovery task."""
    global current_discovery
    if current_discovery and not current_discovery.done():
        logger.debug("Cancelling previous discovery task")
        current_discovery.cancel()
        try:
            await current_discovery
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error cleaning up discovery: {e}")
    current_discovery = None
    logger.debug("Previous discovery task cleaned up")

async def query_device_info(ip: str):
    """Query a single device for its information."""
    try:
        # Get existing connection or establish new one
        connection = await device_cache.get_connection(ip)
        if connection:
            reader, writer = connection
        else:
            reader, writer = await heos_mdns.establish_connection(ip)
            if reader and writer:
                await device_cache.store_connection(ip, reader, writer)
        
        # Get player info
        player_info = await heos_mdns.get_player_info(ip)
        if not player_info:
            logger.error(f"No response from {ip}")
            return heos_mdns.create_error_device(ip, "No response from device")
            
        return player_info
        
    except Exception as e:
        logger.error(f"Error querying device {ip}: {e}")
        return heos_mdns.create_error_device(ip, str(e))

def create_error_device(ip: str, error_message: str):
    """Create a standardized error device entry."""
    return {
        "ip": ip,
        "info": {
            "name": "Error",
            "error": error_message
        },
        "status": "error"
    }

async def discover_devices(request):
    """Handle device discovery request."""
    try:
        # Check cache first
        cached_devices = device_cache.get_devices()
        if cached_devices:
            logger.info("Returning cached devices")
            return web.json_response({
                'source': 'cache',
                'devices': cached_devices
            })

        # No cache or cache expired, do fresh discovery
        logger.info("Starting fresh device discovery")
        devices = await discover_heos_mdns()
        
        if devices:
            logger.info(f"Found {len(devices)} devices")
            # Update cache with new devices
            device_cache.update_devices(devices)
            return web.json_response({
                'source': 'discovery',
                'devices': devices
            })
        else:
            logger.warning("No devices found during discovery")
            return web.json_response({
                'source': 'discovery',
                'devices': []
            })

    except Exception as e:
        logger.error(f"Error during device discovery: {e}")
        return web.json_response({
            'error': str(e)
        }, status=500)

async def start_discovery():
    """Start a new discovery process."""
    global current_discovery
    
    async with discovery_lock:
        # Clean up any existing discovery
        await cleanup_old_discovery()
        
        # Start new discovery immediately
        logger.info("Starting device discovery")
        current_discovery = asyncio.create_task(discover_heos_mdns())
        
        # Wait for discovery with timeout
        try:
            devices = await asyncio.wait_for(
                current_discovery,
                timeout=1.5  # Slightly longer than DISCOVERY_TIMEOUT
            )
            
            if devices:
                # Update cache with new devices
                await device_cache.update_cache(devices)
                logger.info(f"Found {len(devices)} devices")
                return web.json_response({"devices": devices, "status": "success", "source": "discovery"})
            else:
                logger.warning("No devices found during discovery")
                return web.json_response({"devices": [], "status": "success", "source": "discovery"})
                
        except asyncio.TimeoutError:
            logger.error("Discovery timed out")
            return web.json_response({
                "error": "Discovery timed out",
                "status": "error"
            })

async def update_cache_with_discovery(discovery_task):
    """Update cache with discovery results in background."""
    try:
        devices = await discovery_task
        if devices:
            await device_cache.update_cache(devices)
            logger.info(f"Cache updated with {len(devices)} devices")
    except Exception as e:
        logger.error(f"Error updating cache: {e}")

async def send_command(request):
    """Send a command to a HEOS device."""
    try:
        data = await request.json()
        ip = data.get('ip')
        command = data.get('command')
        
        if not ip or not command:
            return web.json_response({
                'error': 'Missing ip or command parameter'
            }, status=400)
            
        # Get device info
        device = None
        devices = device_cache.get_devices()
        if devices:
            device = next((d for d in devices if d['ip'] == ip), None)
        
        if not device:
            return web.json_response({
                'error': f'Device {ip} not found'
            }, status=404)
            
        # Connect and send command
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, 1255),
                timeout=5
            )
            
            # Send command
            writer.write(f"{command}\r\n".encode())
            await writer.drain()
            
            # Read response
            response = await asyncio.wait_for(
                reader.readuntil(b"\r\n"),
                timeout=5
            )
            
            # Close connection
            writer.close()
            await writer.wait_closed()
            
            # Parse response
            response_str = response.decode().strip()
            
            # Add to history
            command_history.add_command(command, device, response_str)
            
            return web.json_response({
                'response': response_str
            })
            
        except asyncio.TimeoutError:
            return web.json_response({
                'error': f'Timeout connecting to {ip}'
            }, status=504)
            
        except Exception as e:
            return web.json_response({
                'error': f'Error sending command: {str(e)}'
            }, status=500)
            
    except Exception as e:
        return web.json_response({
            'error': str(e)
        }, status=500)

async def get_status(request):
    """Get the current status of a HEOS player."""
    try:
        ip = request.match_info.get('ip')
        if not ip:
            return web.json_response({"error": "IP is required"}, status=400)
            
        # Get existing connection or establish new one
        connection = await device_cache.get_connection(ip)
        if connection:
            reader, writer = connection
        else:
            reader, writer = await heos_mdns.establish_connection(ip)
            if reader and writer:
                await device_cache.store_connection(ip, reader, writer)
        
        # Get detailed player info
        player_info = await heos_mdns.get_player_info(ip)
        if not player_info:
            return web.json_response({
                "error": "Failed to get player status",
                "status": "error"
            }, status=500)
            
        return web.json_response({
            "player": player_info,
            "status": "success"
        })
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return web.json_response({
            "error": str(e),
            "status": "error"
        }, status=500)

async def handle_options(request):
    """Handle CORS preflight requests."""
    return web.Response(
        headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        }
    )

async def health_check(request):
    """Health check endpoint."""
    return web.Response(text="OK")

async def get_history(request):
    """Get command history."""
    try:
        limit = int(request.query.get('limit', '100'))
        history = command_history.get_history(limit)
        return web.json_response({
            'history': history
        })
    except Exception as e:
        return web.json_response({
            'error': str(e)
        }, status=500)

async def clear_history(request):
    """Clear command history."""
    try:
        command_history.clear_history()
        return web.json_response({
            'status': 'success',
            'message': 'History cleared'
        })
    except Exception as e:
        return web.json_response({
            'error': str(e)
        }, status=500)

async def force_discovery(request):
    """Force a fresh device discovery by clearing cache first."""
    try:
        # Clear the cache
        device_cache.clear()
        logger.info("Cache cleared, starting fresh discovery")
        
        # Do fresh discovery
        devices = await discover_heos_mdns()
        
        if devices:
            logger.info(f"Found {len(devices)} devices")
            # Update cache with new devices
            device_cache.update_devices(devices)
            return web.json_response({
                'source': 'fresh_discovery',
                'devices': devices
            })
        else:
            logger.warning("No devices found during forced discovery")
            return web.json_response({
                'source': 'fresh_discovery',
                'devices': []
            })

    except Exception as e:
        logger.error(f"Error during forced discovery: {e}")
        return web.json_response({
            'error': str(e)
        }, status=500)

async def init_app():
    """Initialize the web application."""
    app = web.Application(middlewares=[cors_middleware])
    
    # Configure routes
    app.router.add_get('/api/devices', discover_devices)
    app.router.add_get('/api/devices/force', force_discovery)  
    app.router.add_post('/api/command', send_command)
    app.router.add_get('/api/status', get_status)
    app.router.add_get('/api/history', get_history)
    app.router.add_post('/api/history/clear', clear_history)
    app.router.add_options('/{tail:.*}', handle_options)
    app.router.add_get('/health', health_check)
    
    return app

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    app = loop.run_until_complete(init_app())
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Get all network interfaces
    import netifaces
    interfaces = netifaces.interfaces()
    logger.info("Available network interfaces:")
    for iface in interfaces:
        addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in addrs:
            for addr in addrs[netifaces.AF_INET]:
                logger.info(f"Interface {iface}: {addr['addr']}")
    
    # Start the server
    logger.info("Starting HEOS Controller API server on http://0.0.0.0:8080")
    web.run_app(app, host='0.0.0.0', port=8080)
