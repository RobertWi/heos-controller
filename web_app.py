import logging

# Configure root logger with custom formatting
class CustomFormatter(logging.Formatter):
    def format(self, record):
        # Pad the level name to 8 characters for alignment
        record.levelname = f"{record.levelname:<8}"
        # Pad the logger name to 15 characters for alignment
        record.name = f"{record.name:<15}"
        return super().format(record)

logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler('heos_app.log')  # Log to file
    ]
)

# Set custom formatter for all handlers
formatter = CustomFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
for handler in logging.root.handlers:
    handler.setFormatter(formatter)

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import json
import logging
from typing import Dict, Optional
from heos_mdns import discover_heos_mdns, send_heos_command, device_cache
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Callable
import uvicorn
import sys
from datetime import datetime
from starlette.responses import Response
import aiohttp

logger = logging.getLogger(__name__)

class LongRunningRequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path == "/api/discover":
            try:
                # Give discovery endpoint up to 60 seconds
                response = await asyncio.wait_for(call_next(request), timeout=60)
                return response
            except asyncio.TimeoutError:
                logger.error("Discovery request timed out after 60 seconds")
                return HTTPException(
                    status_code=504,
                    detail="Discovery request timed out"
                )
        else:
            # Use default timeout for other requests
            response = await call_next(request)
            return response

app = FastAPI(title="HEOS Controller API")

# Add the custom middleware first
app.add_middleware(LongRunningRequestMiddleware)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}")
    logger.info(f"Headers: {request.headers}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response

# Ensure static and images directories exist
static_dir = os.path.join(os.path.dirname(__file__), "static")
images_dir = os.path.join(static_dir, "images")  # Move images under static
models_dir = os.path.join(images_dir, "models")

# Create directories with proper permissions
for directory in [static_dir, images_dir, models_dir]:
    if not os.path.exists(directory):
        os.makedirs(directory, mode=0o755, exist_ok=True)
    else:
        os.chmod(directory, 0o755)  # Ensure proper permissions

# Mount static directory
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Create default fallback image if it doesn't exist
default_image = os.path.join(models_dir, "unknown.png")
if not os.path.exists(default_image):
    # Create a simple colored rectangle as fallback
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (400, 400), color='#2C3E50')
    d = ImageDraw.Draw(img)
    d.rectangle([50, 50, 350, 350], fill='#34495E')
    img.save(default_image)
    os.chmod(default_image, 0o644)  # Ensure proper file permissions

async def download_model_image(model: str) -> bool:
    """Download the image for a specific model if it doesn't exist."""
    # Normalize model name
    normalized_model = model.lower().replace(' ', '-').replace('_', '-')
    image_path = os.path.join(models_dir, f'{normalized_model}.png')
    
    # Define image URLs for different models
    model_image_urls = {
        'denon-home-150': 'https://assets.denon.com/assets/images/productimages/DenonHome150/DNH150BKE2-1.png',
        'denon-home-250': 'https://assets.denon.com/assets/images/productimages/DenonHome250/DNH250BKE2-1.png',
        'denon-home-350': 'https://assets.denon.com/assets/images/productimages/DenonHome350/DNH350BKE2-1.png',
        'denon-ceol': 'https://assets.denon.com/assets/images/productimages/CEOL/CEOLN11DABWE2-1.png',
        'denon-dra-800h': 'https://assets.denon.com/assets/images/productimages/DRA-800H/DRA800HE2-1.png',
        'heos-1': 'https://assets.denon.com/assets/images/productimages/HEOS1/HEOS1HS2BKE2-1.png',
        'heos-3': 'https://assets.denon.com/assets/images/productimages/HEOS3/HEOS3HS2BKE2-1.png',
        'heos-5': 'https://assets.denon.com/assets/images/productimages/HEOS5/HEOS5HS2BKE2-1.png',
        'heos-7': 'https://assets.denon.com/assets/images/productimages/HEOS7/HEOS7HS2BKE2-1.png',
    }
    
    try:
        # Check if we already have a valid image
        if os.path.exists(image_path) and os.path.getsize(image_path) > 10240:  # 10KB minimum
            logger.info(f"Using existing image for {model}")
            return True
            
        # Try to download new image if model is known
        if normalized_model in model_image_urls:
            image_url = model_image_urls[normalized_model]
            logger.info(f"Downloading image for {model} from {image_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, headers=headers, allow_redirects=True) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        # Only save if we got a real image (more than 10KB)
                        if len(image_data) > 10240:
                            # Save image with proper permissions
                            with open(image_path, 'wb') as f:
                                f.write(image_data)
                            os.chmod(image_path, 0o644)  # Ensure proper file permissions
                            logger.info(f"Successfully downloaded image for {model} ({len(image_data)} bytes)")
                            return True
                        else:
                            logger.error(f"Downloaded image for {model} is too small ({len(image_data)} bytes)")
                    else:
                        logger.error(f"Failed to download image for {model}: HTTP {response.status}")
                        
    except Exception as e:
        logger.error(f"Error downloading image for {model}: {e}")
    
    # If we failed to get the model image, copy the unknown.png as a fallback
    try:
        if not os.path.exists(image_path):
            import shutil
            shutil.copy2(default_image, image_path)
            os.chmod(image_path, 0o644)  # Ensure proper file permissions
            logger.info(f"Using fallback image for {model}")
            return True
    except Exception as e:
        logger.error(f"Error copying fallback image: {e}")
        
    return False

@app.get("/")
async def root():
    """Root endpoint for server health check."""
    return {"status": "ok", "message": "HEOS Controller API is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

@app.get("/api/discover")
async def discover_devices():
    """Discover HEOS devices on the network."""
    try:
        logger.info("Accessing /api/discover endpoint")
        
        # Check cache first
        cached_devices = await device_cache.get_cached_devices()
        if cached_devices:
            logger.info("Using cached device information")
            return {"devices": cached_devices}
            
        devices = []
        
        # Discover devices using mDNS
        device_ips = await discover_heos_mdns()
        logger.info(f"Found mDNS devices: {device_ips}")
        
        # Query each device for more information
        for ip in device_ips:
            try:
                logger.info(f"Querying HEOS device at {ip}")
                response = await send_heos_command(ip, "player/get_players")
                
                if response and "heos" in response and response["heos"].get("result") == "success":
                    if "payload" in response:
                        for player in response["payload"]:
                            device_info = {
                                "ip": player.get("ip", ip),
                                "info": {
                                    "name": player.get("name", "Unknown"),
                                    "model": player.get("model", "Unknown"),
                                    "version": player.get("version", "Unknown"),
                                    "serial": player.get("serial", "Unknown"),
                                    "pid": player.get("pid", "Unknown")
                                },
                                "status": "connected"
                            }
                            
                            # Download model image if needed
                            if device_info["info"]["model"] != "Unknown":
                                await download_model_image(device_info["info"]["model"])
                            
                            logger.info(f"Successfully added device: {device_info}")
                            devices.append(device_info)
                    else:
                        device_info = {
                            "ip": ip,
                            "info": {"name": "Unknown", "model": "Unknown"},
                            "status": "error",
                            "error": "No player information in response"
                        }
                        devices.append(device_info)
                else:
                    error_msg = response.get("heos", {}).get("message", "Unknown error") if response else "No response"
                    device_info = {
                        "ip": ip,
                        "info": {"name": "Unknown", "model": "Unknown"},
                        "status": "error",
                        "error": error_msg
                    }
                    devices.append(device_info)
                
            except Exception as e:
                logger.error(f"Error querying device at {ip}: {e}")
                device_info = {
                    "ip": ip,
                    "info": {"name": "Unknown", "model": "Unknown"},
                    "status": "error",
                    "error": str(e)
                }
                devices.append(device_info)

        # Update cache with new device information
        await device_cache.update_cache(devices)
        logger.info(f"Discovery complete. Found {len(devices)} devices")
        return {"devices": devices}

    except Exception as e:
        logger.error(f"Error during device discovery: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error during device discovery: {str(e)}"
        )

@app.post("/api/player/{ip}/command")
async def send_player_command(ip: str, request: Request):
    """Send a command to a specific HEOS player."""
    try:
        # Get the command from the request body
        body = await request.json()
        command = body.get("command")
        params = body.get("params", {})  # Get optional parameters
        
        if not command:
            raise HTTPException(status_code=400, detail="Command is required")

        logger.debug(f"Sending command to {ip}: {command} with params {params}")
        response = await send_heos_command(ip, command, params)
        
        return response
        
    except Exception as e:
        logger.error(f"Error sending command to {ip}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/player/{ip}/status")
async def get_player_status(ip: str):
    """Get the current status of a HEOS player."""
    try:
        response = await send_heos_command(ip, "player/get_play_state")
        if response:
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {"response": response}
        return {"error": "No response from device"}
    except Exception as e:
        logger.error(f"Error getting status from {ip}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/player/{ip}/preset/{preset_number}")
async def play_preset(ip: str, preset_number: int):
    """Play a specific preset on a HEOS player."""
    try:
        if not 1 <= preset_number <= 6:  # HEOS supports presets 1-6
            raise HTTPException(status_code=400, detail="Preset number must be between 1 and 6")

        response = await send_heos_command(ip, "player/play_preset", {"preset": preset_number})
        if response:
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {"response": response}
        return {"error": "No response from device"}
    except Exception as e:
        logger.error(f"Error playing preset {preset_number} on {ip}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,  # Back to port 8000
        log_level="debug",
        timeout_keep_alive=120,     # Increased keep-alive timeout
        timeout_notify=30,
        workers=1,                  # Single worker for development
        loop="asyncio",             # Explicitly use asyncio
        http="h11",                # Use h11 for HTTP
        ws_ping_interval=20,        # Keep WebSocket connections alive
        ws_ping_timeout=30,         # WebSocket ping timeout
        proxy_headers=True,         # Trust proxy headers
        server_header=False,        # Don't send server header
    )
    server = uvicorn.Server(config)
    server.run()
