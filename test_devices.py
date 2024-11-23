import asyncio
import logging
from heos_mdns import send_heos_command
import json

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Test device configuration
TEST_DEVICE = {
    'name': 'Denon Home 150',
    'ip': '192.168.41.140',
    'did': '3C424E4F8CA96F0546E1',  # Device ID
    'version': '3.34.425',
    'model': 'Denon Home 150',
    'network': 'dc2c6e43f901'
}

class HeosCommandTester:
    def __init__(self, device_ip):
        self.ip = device_ip
        
    async def initialize_device(self):
        """Initialize HEOS device with required setup."""
        try:
            # Register for change events
            await send_heos_command(self.ip, 'system/register_for_change_events', {'enable': 'on'})
            return True
        except Exception as e:
            logger.error(f'Error initializing device: {e}')
            return False

    async def test_system_commands(self):
        """Test HEOS System Commands"""
        print("\n=== Testing System Commands ===")
        
        commands = [
            ('system/heart_beat', {}),
            ('system/check_account', {}),
            ('system/sign_in', {'un': 'YOUR_USERNAME', 'pw': 'YOUR_PASSWORD'}),
            ('system/sign_out', {}),
            ('system/register_for_change_events', {'enable': 'on'}),
            ('system/prettify_json_response', {'enable': 'on'})
        ]
        
        for cmd, params in commands:
            try:
                print(f"\nTesting: {cmd}")
                result = await send_heos_command(self.ip, cmd, params)
                print(f"Result: {json.dumps(result, indent=2)}")
            except Exception as e:
                logger.error(f'Error testing {cmd}: {e}')

    async def test_player_commands(self):
        """Test HEOS Player Commands"""
        print("\n=== Testing Player Commands ===")
        
        # Basic playback commands
        playback_commands = [
            ('player/get_players', {}),
            ('player/get_play_state', {'pid': TEST_DEVICE['did']}),
            ('player/set_play_state', {'pid': TEST_DEVICE['did'], 'state': 'play'}),
            ('player/get_now_playing_media', {'pid': TEST_DEVICE['did']}),
            ('player/get_volume', {'pid': TEST_DEVICE['did']}),
            ('player/set_volume', {'pid': TEST_DEVICE['did'], 'level': '25'}),
            ('player/volume_up', {'pid': TEST_DEVICE['did'], 'step': '5'}),
            ('player/volume_down', {'pid': TEST_DEVICE['did'], 'step': '5'}),
            ('player/get_mute', {'pid': TEST_DEVICE['did']}),
            ('player/set_mute', {'pid': TEST_DEVICE['did'], 'state': 'on'}),
            ('player/toggle_mute', {'pid': TEST_DEVICE['did']}),
            ('player/get_play_mode', {'pid': TEST_DEVICE['did']}),
            ('player/set_play_mode', {'pid': TEST_DEVICE['did'], 'repeat': 'on_all', 'shuffle': 'on'})
        ]
        
        for cmd, params in playback_commands:
            try:
                print(f"\nTesting: {cmd}")
                result = await send_heos_command(self.ip, cmd, params)
                print(f"Result: {json.dumps(result, indent=2)}")
                await asyncio.sleep(1)  # Add delay between commands
            except Exception as e:
                logger.error(f'Error testing {cmd}: {e}')

    async def test_group_commands(self):
        """Test HEOS Group Commands"""
        print("\n=== Testing Group Commands ===")
        
        commands = [
            ('group/get_groups', {}),
            ('group/get_group_volume', {'gid': '1'}),
            ('group/set_group_volume', {'gid': '1', 'level': '25'}),
            ('group/volume_up', {'gid': '1', 'step': '5'}),
            ('group/volume_down', {'gid': '1', 'step': '5'}),
            ('group/get_group_mute', {'gid': '1'}),
            ('group/set_group_mute', {'gid': '1', 'state': 'on'}),
            ('group/toggle_group_mute', {'gid': '1'})
        ]
        
        for cmd, params in commands:
            try:
                print(f"\nTesting: {cmd}")
                result = await send_heos_command(self.ip, cmd, params)
                print(f"Result: {json.dumps(result, indent=2)}")
            except Exception as e:
                logger.error(f'Error testing {cmd}: {e}')

    async def test_browse_commands(self):
        """Test HEOS Browse Commands"""
        print("\n=== Testing Browse Commands ===")
        
        commands = [
            ('browse/get_music_sources', {}),
            ('browse/get_source_info', {'sid': '1'}),
            ('browse/browse', {'sid': '1'}),
            ('browse/browse_source', {'sid': '1'}),
            ('browse/play_station', {'pid': TEST_DEVICE['did'], 'sid': '1', 'cid': '1', 'mid': '1'}),
            ('browse/play_preset', {'pid': TEST_DEVICE['did'], 'preset': '1'}),
            ('browse/play_input', {'pid': TEST_DEVICE['did'], 'input': 'aux_in_1'}),
            ('browse/add_to_queue', {'pid': TEST_DEVICE['did'], 'sid': '1', 'cid': '1', 'aid': '1', 'mid': '1'})
        ]
        
        for cmd, params in commands:
            try:
                print(f"\nTesting: {cmd}")
                result = await send_heos_command(self.ip, cmd, params)
                print(f"Result: {json.dumps(result, indent=2)}")
            except Exception as e:
                logger.error(f'Error testing {cmd}: {e}')

    async def test_queue_commands(self):
        """Test HEOS Queue Commands"""
        print("\n=== Testing Queue Commands ===")
        
        commands = [
            ('player/get_queue', {'pid': TEST_DEVICE['did']}),
            ('player/play_queue', {'pid': TEST_DEVICE['did'], 'qid': '1'}),
            ('player/remove_from_queue', {'pid': TEST_DEVICE['did'], 'qid': '1'}),
            ('player/save_queue', {'pid': TEST_DEVICE['did'], 'name': 'My Playlist'}),
            ('player/clear_queue', {'pid': TEST_DEVICE['did']}),
            ('player/move_queue_item', {'pid': TEST_DEVICE['did'], 'sqid': '1', 'dqid': '2'}),
            ('player/play_next', {'pid': TEST_DEVICE['did']}),
            ('player/play_previous', {'pid': TEST_DEVICE['did']})
        ]
        
        for cmd, params in commands:
            try:
                print(f"\nTesting: {cmd}")
                result = await send_heos_command(self.ip, cmd, params)
                print(f"Result: {json.dumps(result, indent=2)}")
            except Exception as e:
                logger.error(f'Error testing {cmd}: {e}')

async def main():
    """Main test function"""
    tester = HeosCommandTester(TEST_DEVICE['ip'])
    
    # Initialize device
    if not await tester.initialize_device():
        logger.error("Failed to initialize device")
        return
    
    # Run all tests
    test_functions = [
        tester.test_system_commands,
        tester.test_player_commands,
        tester.test_group_commands,
        tester.test_browse_commands,
        tester.test_queue_commands
    ]
    
    for test_func in test_functions:
        try:
            await test_func()
            await asyncio.sleep(2)  # Add delay between test categories
        except Exception as e:
            logger.error(f'Error in {test_func.__name__}: {e}')

if __name__ == '__main__':
    # Run the test suite
    asyncio.run(main())
