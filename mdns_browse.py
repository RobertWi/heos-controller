#!/usr/bin/env python3

import asyncio
import logging
from zeroconf.asyncio import AsyncZeroconf, AsyncServiceBrowser
import socket

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ServiceListener:
    def __init__(self):
        self.services_found = set()

    def remove_service(self, zc, type_, name):
        logger.info(f"Service {name} removed")
        self.services_found.discard(name)

    async def _async_add_service(self, zc, type_, name):
        logger.info(f"Service {name} added")
        info = await zc.async_get_service_info(type_, name)
        if info:
            addresses = [f"{socket.inet_ntoa(addr)}" for addr in info.addresses]
            logger.info(f"  Addresses: {addresses}")
            logger.info(f"  Port: {info.port}")
            logger.info(f"  Properties: {[(k.decode(), v.decode()) for k, v in info.properties.items()]}")
        self.services_found.add(name)

    def add_service(self, zc, type_, name):
        asyncio.create_task(self._async_add_service(zc, type_, name))

async def main():
    zc = AsyncZeroconf()
    listener = ServiceListener()
    browser = AsyncServiceBrowser(zc.zeroconf, "_services._dns-sd._udp.local.", listener)
    
    try:
        logger.info("Browsing for all mDNS services. Press Ctrl+C to exit...")
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await browser.async_cancel()
        await zc.async_close()

if __name__ == "__main__":
    asyncio.run(main())
