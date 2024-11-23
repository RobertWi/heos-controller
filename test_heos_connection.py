import asyncio
import telnetlib
import logging
import time
import base64
from zeroconf.asyncio import AsyncZeroconf
from zeroconf import ServiceBrowser, ServiceListener
import urllib.parse

logging.basicConfig(level=logging.DEBUG,
                   format='%(levelname)s: %(message)s')

class HeosTestListener(ServiceListener):
    def __init__(self):
        self.devices = []
        
    def add_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name)
        if info:
            device = {
                'name': name.split('.')[0],
                'address': '.'.join([str(int(b)) for b in info.addresses[0]]),
                'port': info.port
            }
            self.devices.append(device)
            logging.info(f"Found device: {device['name']} at {device['address']}:{device['port']}")

    def remove_service(self, zc, type_, name):
        pass

    def update_service(self, zc, type_, name):
        pass

async def discover_devices():
    aiozc = AsyncZeroconf()
    listener = HeosTestListener()
    browser = ServiceBrowser(aiozc.zeroconf, "_heos-audio._tcp.local.", listener)
    
    await asyncio.sleep(5)  # Wait for discovery
    await aiozc.async_close()
    return listener.devices

async def send_command(writer, reader, cmd, log_cmd=True):
    """Send a command and read response"""
    if not cmd.endswith('\r\n'):
        cmd = cmd + '\r\n'
    
    if log_cmd:
        logging.info(f"Sending: {cmd.strip()}")
    else:
        # Log the actual credentials for development
        logging.info(f"Sending: {cmd.strip()}")
        
    writer.write(cmd.encode('utf-8'))
    await writer.drain()
    
    try:
        # Try to read response with timeout
        response = await asyncio.wait_for(reader.readuntil(b'\r\n'), timeout=2.0)
        response_str = response.decode('utf-8').strip()
        logging.info(f"Received: {response_str}")
        return response_str
    except asyncio.TimeoutError:
        logging.error("No response received (timeout)")
        return None
    except Exception as e:
        logging.error(f"Error reading response: {str(e)}")
        return None

async def test_login(device, username, password):
    logging.info(f"Connecting to {device['name']} ({device['address']}:{device['port']})")
    try:
        reader, writer = await asyncio.open_connection(device['address'], device['port'])
        logging.info("TCP connection established")

        # Register for change events
        register_cmd = "heos://system/register_for_change_events?enable=on"
        await send_command(writer, reader, register_cmd)

        # Encode credentials for logging
        encoded_username = base64.b64encode(username.encode('utf-8')).decode('utf-8')
        encoded_password = base64.b64encode(password.encode('utf-8')).decode('utf-8')

        # Send login command with encoded credentials
        login_cmd = f"heos://system/sign_in?un={encoded_username}&pw={encoded_password}"
        await send_command(writer, reader, login_cmd, log_cmd=False)

        writer.close()
        await writer.wait_closed()
        return True
    except Exception as e:
        logging.error(f"Connection failed: {str(e)}")
        return False

async def main():
    # Discover devices
    logging.info("Discovering HEOS devices...")
    devices = await discover_devices()

    if not devices:
        logging.error("No HEOS devices found!")
        return

    # Read credentials from 'password' file
    try:
        with open('password', 'r') as file:
            lines = file.readlines()
            username = lines[0].strip().split('=')[1]
            password = lines[1].strip().split('=')[1]
    except Exception as e:
        logging.error(f"Failed to read credentials: {str(e)}")
        return

    # Test login for each device
    for device in devices:
        success = await test_login(device, username, password)
        if success:
            logging.info(f"Successfully logged in to {device['name']}")
        else:
            logging.error(f"Failed to log in to {device['name']}")
        await asyncio.sleep(1)  # Wait between devices

if __name__ == "__main__":
    asyncio.run(main())
