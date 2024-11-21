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

# CORS middleware
@web.middleware
async def cors_middleware(request, handler):
    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

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

device_cache = DeviceCache()  # Using the correct DeviceCache implementation

# Route handlers
async def discover_devices(request):
    """Discover HEOS devices on the network."""
    try:
        # Check cache first
        cached_devices = await device_cache.get_cached_devices()
        if cached_devices:
            logger.info(f"Returning {len(cached_devices)} cached devices")
            return web.json_response({"devices": cached_devices, "status": "success"})

        # Perform discovery
        logger.info("Starting device discovery")
        devices = await discover_heos_mdns()
        
        if devices:
            # Update cache with new devices
            await device_cache.update_cache(devices)
            
            logger.info(f"Found {len(devices)} devices")
            return web.json_response({"devices": devices, "status": "success"})
        else:
            logger.warning("No devices found during discovery")
            return web.json_response({"devices": [], "status": "success"})
            
    except Exception as e:
        logger.error(f"Error during device discovery: {e}")
        return web.json_response({
            "error": str(e),
            "status": "error"
        }, status=500)

async def send_command(request):
    """Send a command to a specific HEOS player."""
    try:
        data = await request.json()
        logger.info(f"Headers: {request.headers}")
        
        # Extract player IP from URL path
        player_ip = request.match_info['player_ip']
        if not player_ip:
            raise ValueError("Player IP is required")
            
        # Get device from cache
        device = await device_cache.get_device(player_ip)
        if not device:
            logger.error(f"Device {player_ip} not found in cache")
            return web.json_response({
                "error": f"Device {player_ip} not found",
                "status": "error"
            }, status=404)
            
        # Send command
        command = data.get('command')
        params = data.get('params', {})
        if not command:
            raise ValueError("Command is required")
            
        logger.info(f"Processing command for {player_ip}: {command} with params {params}")
        
        # Get existing connection or establish new one
        connection = await device_cache.get_connection(player_ip)
        if connection:
            reader, writer = connection
        else:
            reader, writer = await heos_mdns.establish_connection(player_ip)
            if reader and writer:
                await device_cache.store_connection(player_ip, reader, writer)
        
        # Format and send the command
        response = await heos_mdns.send_heos_command(player_ip, command, params)
        
        return web.json_response({"response": response, "status": "success"})
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return web.json_response({
            "error": "Invalid JSON in request body",
            "status": "error"
        }, status=400)
    except ValueError as e:
        logger.error(f"Value error: {e}")
        return web.json_response({
            "error": str(e),
            "status": "error"
        }, status=400)
    except Exception as e:
        logger.error(f"Error sending command: {e}")
        return web.json_response({
            "error": str(e),
            "status": "error"
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

async def init_app():
    """Initialize the web application."""
    app = web.Application(middlewares=[cors_middleware])
    
    # Configure routes
    app.router.add_get('/api/discover', discover_devices)
    app.router.add_post('/api/player/{player_ip}/command', send_command)
    app.router.add_get('/api/player/{ip}/status', get_status)
    app.router.add_get('/health', health_check)
    app.router.add_options('/{tail:.*}', handle_options)
    
    return app

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    app = loop.run_until_complete(init_app())
    logger.info("Starting HEOS Controller API server on http://0.0.0.0:8000")
    web.run_app(app, host='0.0.0.0', port=8000)
