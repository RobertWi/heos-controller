# HEOS Controller

A GTK4 application for discovering and controlling HEOS audio devices on your network.

## Features

- Automatic HEOS device discovery using mDNS
- Clean and modern GTK4 interface with Libadwaita
- Device control capabilities (login, playback, volume)
- Cross-platform compatibility

## Requirements

- Python 3.8 or higher
- GTK 4.0
- Libadwaita 1.0
- Python packages (see requirements.txt)

## Installation

1. Install system dependencies:

```bash
# Ubuntu/Debian
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 libadwaita-1

# Fedora
sudo dnf install python3-gobject gtk4 libadwaita

# Arch Linux
sudo pacman -S python-gobject gtk4 libadwaita
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

3. Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Usage

1. Run the application:

```bash
python heos_controller_gtk.py
```

2. The application will automatically discover HEOS devices on your network
3. Select a device to control it
4. Log in with your HEOS account to access additional features

## Testing

Run the test suite:

```bash
python -m pytest test_devices.py
```

## License

GPL-3.0

## References

- [HEOS CLI Protocol Specification](HEOS_CLI_ProtocolSpecification.pdf)
