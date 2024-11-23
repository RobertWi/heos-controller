import asyncio
import pytest
from device_cache import DeviceCache
from unittest.mock import Mock, AsyncMock

@pytest.fixture
def device_cache():
    return DeviceCache(cache_duration=5)

@pytest.fixture
def mock_connection():
    reader = AsyncMock(spec=asyncio.StreamReader)
    writer = AsyncMock(spec=asyncio.StreamWriter)
    writer.is_closing.return_value = False
    return reader, writer

@pytest.mark.asyncio
async def test_store_and_get_connection(device_cache, mock_connection):
    reader, writer = mock_connection
    ip = "192.168.41.145"
    
    # Store connection
    await device_cache.store_connection(ip, reader, writer)
    
    # Get connection
    stored_reader, stored_writer = await device_cache.get_connection(ip)
    
    assert stored_reader == reader
    assert stored_writer == writer

@pytest.mark.asyncio
async def test_connection_invalid_returns_none(device_cache, mock_connection):
    reader, writer = mock_connection
    ip = "192.168.41.145"
    
    # Make connection appear closed
    writer.is_closing.return_value = True
    
    await device_cache.store_connection(ip, reader, writer)
    result = await device_cache.get_connection(ip)
    
    assert result is None

@pytest.mark.asyncio
async def test_close_connection(device_cache, mock_connection):
    reader, writer = mock_connection
    ip = "192.168.41.145"
    
    await device_cache.store_connection(ip, reader, writer)
    await device_cache._close_connection(ip)
    
    writer.close.assert_called_once()
    writer.wait_closed.assert_called_once()
    
    result = await device_cache.get_connection(ip)
    assert result is None

@pytest.mark.asyncio
async def test_close_all_connections(device_cache):
    # Create multiple mock connections
    ips = ["192.168.41.145", "192.168.41.140"]
    connections = []
    
    for ip in ips:
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = AsyncMock(spec=asyncio.StreamWriter)
        writer.is_closing.return_value = False
        connections.append((ip, reader, writer))
        await device_cache.store_connection(ip, reader, writer)
    
    await device_cache.close_all_connections()
    
    # Verify all connections were closed
    for ip, _, writer in connections:
        writer.close.assert_called_once()
        writer.wait_closed.assert_called_once()
        result = await device_cache.get_connection(ip)
        assert result is None

@pytest.mark.asyncio
async def test_store_connection_closes_existing(device_cache, mock_connection):
    reader1, writer1 = mock_connection
    reader2, writer2 = AsyncMock(spec=asyncio.StreamReader), AsyncMock(spec=asyncio.StreamWriter)
    writer2.is_closing.return_value = False
    ip = "192.168.41.145"
    
    # Store first connection
    await device_cache.store_connection(ip, reader1, writer1)
    
    # Store second connection
    await device_cache.store_connection(ip, reader2, writer2)
    
    # Verify first connection was closed
    writer1.close.assert_called_once()
    writer1.wait_closed.assert_called_once()
    
    # Verify second connection is active
    stored_reader, stored_writer = await device_cache.get_connection(ip)
    assert stored_reader == reader2
    assert stored_writer == writer2
