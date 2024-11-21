# HEOS Controller

A Python application to control DENON HEOS devices on your local network. This application allows you to control HEOS-enabled devices, manage playback, adjust volume, and view now playing information.

## Features

- Control HEOS devices on your network
- List all available HEOS players
- Basic playback controls (play/pause)
- Volume control
- View now playing information

## Requirements

- Python 3.7 or higher
- HEOS-enabled device(s) on the same network
- IP address of your HEOS device

## Installation

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Linux/Mac
```

2. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Make sure your HEOS device is powered on and connected to the same network as your computer.

2. Find your HEOS device's IP address. You can usually find this in:
   - Your router's admin interface
   - The HEOS app's device settings
   - Network scanner tools

3. Run the application:
```bash
python heos_controller.py
```

4. When prompted, enter your HEOS device's IP address.

5. Use the interactive menu to control your HEOS devices:
   - List all available players
   - Control playback (play/pause)
   - Adjust volume
   - View now playing information

## Troubleshooting

If the application fails to connect to your HEOS device:
1. Ensure the device is powered on and connected to the network
2. Verify the IP address is correct
3. Check that your computer and the HEOS device are on the same network
4. Make sure no firewall is blocking the connection

## License

This project is open source and available under the MIT License.
