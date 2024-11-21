#!/usr/bin/env python3

import socket
import logging
import asyncio
from typing import List, Dict
import netifaces

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

MULTICAST_IP = "239.255.255.250"
MULTICAST_PORT = 1900
SEARCH_TARGET = "ssdp:all"  # Search for all SSDP devices

class SSDPDiscovery:
    def __init__(self):
        self.devices = {}

    def create_msearch_request(self) -> str:
        """Create an M-SEARCH request following the SSDP protocol."""
        return (
            'M-SEARCH * HTTP/1.1\r\n'
            f'HOST: {MULTICAST_IP}:{MULTICAST_PORT}\r\n'
            'MAN: "ssdp:discover"\r\n'
            'MX: 3\r\n'
            f'ST: {SEARCH_TARGET}\r\n'
            '\r\n'
        )

    async def discover_on_interface(self, interface: str, timeout: int = 5) -> Dict:
        """Send M-SEARCH request on a specific interface and collect responses."""
        # Get interface addresses
        addrs = netifaces.ifaddresses(interface)
        if netifaces.AF_INET not in addrs:
            return {}

        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
        
        # Bind to the interface's address
        interface_ip = addrs[netifaces.AF_INET][0]['addr']
        sock.bind((interface_ip, 0))
        
        sock.settimeout(timeout)

        # Send M-SEARCH request
        msearch = self.create_msearch_request()
        logger.debug(f"Sending M-SEARCH request on {interface} ({interface_ip}):\n{msearch}")
        sock.sendto(msearch.encode(), (MULTICAST_IP, MULTICAST_PORT))

        # Collect responses
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                data, addr = sock.recvfrom(1024)
                response = data.decode()
                logger.debug(f"Received response from {addr}:\n{response}")

                # Parse response headers
                headers = {}
                for line in response.split('\r\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        headers[key.strip().lower()] = value.strip()

                # Store device info
                if addr[0] not in self.devices:
                    self.devices[addr[0]] = {
                        'address': addr[0],
                        'port': addr[1],
                        'server': headers.get('server', 'Unknown'),
                        'location': headers.get('location', 'Unknown'),
                        'usn': headers.get('usn', 'Unknown')
                    }
            except socket.timeout:
                break
            except Exception as e:
                logger.error(f"Error receiving response: {e}")

        sock.close()
        return self.devices

    async def discover(self, timeout: int = 5) -> Dict:
        """Send M-SEARCH request on all interfaces and collect responses."""
        # Get all network interfaces
        interfaces = netifaces.interfaces()
        
        # Filter out loopback and non-active interfaces
        active_interfaces = [
            iface for iface in interfaces
            if iface != 'lo' and netifaces.AF_INET in netifaces.ifaddresses(iface)
        ]
        
        logger.info(f"Discovering on interfaces: {active_interfaces}")
        
        # Run discovery on all interfaces concurrently
        tasks = [
            self.discover_on_interface(iface, timeout)
            for iface in active_interfaces
        ]
        await asyncio.gather(*tasks)
        
        return self.devices

async def main():
    """Main function to discover SSDP devices."""
    logger.info("Starting SSDP device discovery...")
    discoverer = SSDPDiscovery()
    devices = await discoverer.discover()

    if devices:
        logger.info("\nFound devices:")
        for addr, device in devices.items():
            logger.info(f"\nDevice at {addr}:")
            for key, value in device.items():
                logger.info(f"  {key}: {value}")
    else:
        logger.info("No devices found")

if __name__ == "__main__":
    asyncio.run(main())
