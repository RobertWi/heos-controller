import asyncio
from heos_mdns import send_heos_command

async def test_devices():
    devices = ['192.168.41.145', '192.168.41.140', '192.168.41.144', '192.168.41.146']
    for ip in devices:
        try:
            print(f'\nTesting device {ip}:')
            result = await send_heos_command(ip, 'player/get_players')
            print(f'Response: {result}')
        except Exception as e:
            print(f'Error: {e}')

if __name__ == '__main__':
    asyncio.run(test_devices())
