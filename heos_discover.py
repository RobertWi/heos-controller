#!/usr/bin/env python3

import asyncio
import logging
import socket
import json
import argparse

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# HEOS CLI settings
HEOS_CLI_PORT = 1255

async def test_heos_connection(ip: str) -> dict:
    """Test connection to a HEOS device via CLI."""
    try:
        reader, writer = await asyncio.open_connection(ip, HEOS_CLI_PORT)
        
        # Send a simple command to get player info
        cmd = "heos://player/get_players\r\n"
        logger.debug(f"Sending command to {ip}: {cmd.strip()}")
        writer.write(cmd.encode())
        await writer.drain()
        
        response = await reader.readline()
        logger.debug(f"Received response: {response.decode().strip()}")
        
        writer.close()
        await writer.wait_closed()
        
        return {
            'address': ip,
            'port': HEOS_CLI_PORT,
            'response': response.decode().strip()
        }
    except Exception as e:
        logger.error(f"Error connecting to HEOS device at {ip}: {e}")
        return None

async def main():
    """Main function to connect to HEOS devices."""
    parser = argparse.ArgumentParser(description='HEOS Device Discovery and Connection')
    parser.add_argument('--ip', help='IP address of the HEOS device')
    args = parser.parse_args()

    if args.ip:
        logger.info(f"Attempting to connect to HEOS device at {args.ip}")
        device = await test_heos_connection(args.ip)
        if device:
            logger.info(f"\nSuccessfully connected to HEOS device:")
            logger.info(f"Address: {device['address']}:{device['port']}")
            logger.info(f"Response: {device['response']}")
        else:
            logger.error(f"Could not connect to HEOS device at {args.ip}")
    else:
        logger.error("Please specify the IP address of the HEOS device using --ip")
        logger.info("Example: ./heos_discover.py --ip 192.168.1.100")

if __name__ == "__main__":
    asyncio.run(main())
