"""
HEOS Controller GTK Application
Copyright (c) 2024 Robert Winder

HEOS, DENON and Marantz are trademarks of D&amp;M Holdings Inc. 
The developers of this module are in no way endorsed by or affiliated with 
D&amp;M Holdings Inc., or any associated subsidiaries, logos or trademarks.
"""

import asyncio
import base64
import json
import logging
import threading
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote as urllib_parse_quote

import gi
import telnetlib3
from zeroconf import ServiceInfo, ServiceStateChange, Zeroconf
from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gio, GLib, GObject, Gtk  # noqa: E402

import os
import socket
import sys
from urllib.parse import urljoin

import requests

from logger_config import setup_logging

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

# Service types for HEOS discovery
SERVICE_TYPES = [
    "_heos-audio._tcp.local.",
]

class ServiceHandler:
    """Non-async wrapper for HeosListener to handle zeroconf callbacks"""
    def __init__(self, listener: 'HeosListener'):
        self.listener = listener
        self.logger = logging.getLogger(__name__ + '.ServiceHandler')

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Handle service added event by scheduling async task"""
        asyncio.create_task(self.listener.add_service(zc, type_, name))

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Handle service update event"""
        self.logger.info(f"Service updated: {name} (type: {type_})")
        asyncio.create_task(self.listener.update_service(zc, type_, name))

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Handle service removed event"""
        self.listener.remove_service(zc, type_, name)

class HeosListener:
    """Async listener for HEOS service discovery events"""
    def __init__(self):
        self.logger = logging.getLogger(__name__ + '.HeosListener')
        self.logger.info("HeosListener initialized")
        self.devices = {}
        self.discovered_event = asyncio.Event()

    async def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Handle a service being added."""
        self.logger.info(f"Service added: {name} (type: {type_})")
        try:
            info = await self._get_service_info(zc, type_, name)
            if info:
                self.logger.info(f"Service info details for {name}:")
                self.logger.info(f"  - Server: {info.server}")
                self.logger.info(f"  - Address: {info.parsed_addresses()}")
                self.logger.info(f"  - Port: {info.port}")
                self.logger.info(f"  - Properties: {info.properties}")
                
                device = {
                    'name': name.split('.')[0],  # Remove the service type suffix
                    'address': info.parsed_addresses()[0] if info.parsed_addresses() else None,
                    'port': info.port,
                    'properties': info.properties
                }
                self.devices[name] = device
                self.discovered_event.set()
            else:
                self.logger.warning(f"No service info available for {name}")
        except Exception as e:
            self.logger.error(f"Error processing service {name}: {e}", exc_info=True)

    async def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Handle service updated event."""
        self.logger.info(f"Service updated: {name} (type: {type_})")
        info = await self._get_service_info(zc, type_, name)
        if info and name in self.devices:
            try:
                self.devices[name].update({
                    'address': info.parsed_addresses()[0] if info.parsed_addresses() else None,
                    'port': info.port,
                })
                self.logger.info(f"Updated device: {self.devices[name]}")
            except Exception as e:
                self.logger.error(f"Error updating device info for {name}: {e}")

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Handle service removed event."""
        self.logger.info(f"Service removed: {name} (type: {type_})")
        if name in self.devices:
            del self.devices[name]

    async def _get_service_info(self, zc: Zeroconf, type_: str, name: str) -> Optional[ServiceInfo]:
        """Get service info for a discovered device."""
        try:
            self.logger.info(f"Getting service info for: {name}")
            # Create ServiceInfo instance first
            info = ServiceInfo(type_, name)
            # Then request the info with a timeout
            if await info.async_request(zc, timeout=2000):  # 2 second timeout
                self.logger.info(f"Got service info for {name}: {info}")
                return info
            else:
                self.logger.warning(f"Failed to get service info for {name}")
                return None
        except Exception as e:
            self.logger.error(f"Error getting service info for {name}: {e}")
        return None

class HeosDiscovery:
    """HEOS device discovery using AsyncZeroconf"""
    def __init__(self):
        self.logger = logging.getLogger(__name__ + '.HeosDiscovery')
        self.logger.info("HeosDiscovery initialized")
        self.zeroconf = None
        self.browsers = []
        self.listener = None

    async def discover_devices(self, timeout: float = 10.0) -> List[Dict]:
        """Discover HEOS devices on the network"""
        try:
            self.logger.info(f"Starting device discovery with timeout {timeout}s")
            self.zeroconf = AsyncZeroconf()
            
            # Create a listener for handling service events
            self.listener = HeosListener()
            service_handler = ServiceHandler(self.listener)
            
            # Start browsing for each service type
            for service_type in SERVICE_TYPES:
                self.logger.info(f"Creating browser for service type: {service_type}")
                browser = AsyncServiceBrowser(
                    self.zeroconf.zeroconf,
                    service_type,
                    service_handler
                )
                self.browsers.append(browser)
            
            # Wait for initial discovery
            try:
                # Give some time for initial discovery
                await asyncio.sleep(2.0)
                
                # Then wait for the discovery event or timeout
                try:
                    await asyncio.wait_for(self.listener.discovered_event.wait(), timeout=timeout-2)
                    self.logger.info("Discovery event received")
                except asyncio.TimeoutError:
                    self.logger.info("Discovery timeout reached")
                
                # Small delay to allow for final updates
                await asyncio.sleep(1.0)
                
            except asyncio.CancelledError:
                self.logger.info("Discovery cancelled")
            
            # Return discovered devices
            devices = list(self.listener.devices.values())
            self.logger.info(f"Discovery completed, found {len(devices)} devices")
            for device in devices:
                self.logger.info(f"Found device: {device}")
            return devices
            
        except Exception as e:
            self.logger.error(f"Error during discovery: {str(e)}", exc_info=True)
            return []
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Cleanup discovery resources"""
        self.logger.info("Starting cleanup of HeosDiscovery")
        if self.browsers:
            self.logger.info(f"Canceling {len(self.browsers)} browsers")
            for browser in self.browsers:
                await browser.async_cancel()
            self.browsers = []
        
        if self.zeroconf:
            self.logger.info("Closing AsyncZeroconf")
            await self.zeroconf.async_close()  # Use async_close instead of close
            self.zeroconf = None
            
        self.logger.info("HeosDiscovery cleanup completed")

class HeosWindow(Adw.ApplicationWindow):
    """Main application window."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.logger = logging.getLogger(__name__ + '.HeosWindow')
        self.username = None
        self.password = None
        self.connection = None  # Store connection details
        self.login_in_progress = False  # Single flag for login state
        
        # Create event loop in background thread
        self.loop = None
        self.thread = None
        self.start_background_loop()
        
        # Initialize UI components
        self.username_entry = None
        self.password_entry = None
        self.login_button = None
        self.spinner = None
        self.devices_list = None
        self.stack = None
        self.toast_overlay = None
        self.about_window = None
        self.selected_device = None
        self.discovered_devices = []
        
        # Load UI
        self.setup_ui()
        
        # Start discovery using GLib idle callback
        GLib.idle_add(self._start_initial_discovery)

    def start_background_loop(self):
        """Create a new event loop in a background thread."""
        self.loop = asyncio.new_event_loop()
        
        def run_event_loop():
            self.logger.info("Starting event loop in background thread")
            asyncio.set_event_loop(self.loop)
            try:
                self.loop.run_forever()
            except Exception as e:
                self.logger.error(f"Event loop error: {e}", exc_info=True)
            
        self.thread = threading.Thread(target=run_event_loop, daemon=True)
        self.thread.start()

    def _start_initial_discovery(self):
        """Start initial device discovery"""
        self.logger.info("Starting initial device discovery")
        try:
            future = asyncio.run_coroutine_threadsafe(self._do_initial_discovery(), self.loop)
            
            def discovery_done(fut):
                try:
                    fut.result()
                    self.logger.info("Discovery completed successfully")
                except Exception as e:
                    self.logger.error(f"Discovery failed: {e}", exc_info=True)
                    GLib.idle_add(lambda: self.show_error_toast(f"Discovery failed: {str(e)}"))
            
            future.add_done_callback(discovery_done)
            
        except Exception as e:
            self.logger.error(f"Failed to start discovery: {e}", exc_info=True)
            self.show_error_toast(f"Failed to start discovery: {str(e)}")
        
        return False  # Don't repeat the idle callback

    async def _do_initial_discovery(self):
        """Perform initial device discovery"""
        self.logger.info("Starting discovery process")
        try:
            self.show_spinner()
            self.logger.info("Creating HeosDiscovery instance")
            discovery = HeosDiscovery()
            
            # Wait for discovery to complete
            devices = await discovery.discover_devices()
            self.logger.info(f"Found {len(devices)} devices")
            
            if devices:
                # Automatically select first device
                self.selected_device = devices[0]
                self.logger.info(f"Using device: {self.selected_device['name']}")
            else:
                self.logger.error("No devices found")
                GLib.idle_add(lambda: self.show_error_toast("No HEOS devices found"))
            
            # Store all devices for reference
            self.discovered_devices = devices
            
            # Update UI list
            GLib.idle_add(lambda: self.update_devices_list(devices))
            
        except Exception as e:
            self.logger.error(f"Error during discovery: {e}", exc_info=True)
            GLib.idle_add(lambda: self.show_error_toast("Error during device discovery"))
        finally:
            GLib.idle_add(self.hide_spinner)
            self.logger.info("Discovery process completed")

    def setup_ui(self):
        """Initialize the UI components"""
        self.logger.debug("Setting up UI components")
        builder = Gtk.Builder()
        
        # Get absolute path to UI file
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "window.ui")
        self.logger.debug(f"Loading UI file from: {ui_path}")
        
        try:
            builder.add_from_file(ui_path)
        except Exception as e:
            self.logger.error(f"Failed to load UI file: {e}")
            return
            
        # Get window content
        window = builder.get_object("window")
        if not window:
            self.logger.error("Failed to get window from UI file")
            return
            
        # Get UI elements
        self.login_button = builder.get_object("login_button")
        self.username_entry = builder.get_object("username_entry")
        self.password_entry = builder.get_object("password_entry")
        self.spinner = builder.get_object("spinner")
        self.devices_list = builder.get_object("devices_list")
        self.stack = builder.get_object("stack")
        self.toast_overlay = builder.get_object("toast_overlay")
        self.about_window = builder.get_object("about_window")
        
        # Set up window properties
        self.set_default_size(800, 600)
        self.set_title("HEOS Controller")
        
        # Set the content
        if self.toast_overlay:
            if self.toast_overlay.get_parent():
                self.toast_overlay.unparent()
            self.set_content(self.toast_overlay)
            self.logger.debug("Main window content set successfully")
            
            # Show login view
            if self.stack:
                self.stack.set_visible_child_name("login-view")
        else:
            self.logger.error("Failed to get toast overlay from UI file")
            
        self.setup_signals()
        self.connect("close-request", self.on_window_close)

    def setup_signals(self):
        """Connect UI signals to handlers"""
        self.logger.debug("Setting up signal handlers")
        if self.login_button:
            self.login_button.connect("clicked", self.on_login_clicked)
            
    async def on_login_clicked(self, button):
        """Handle login button click"""
        if self.login_in_progress:
            self.logger.warning("Login already in progress")
            return
            
        self.login_in_progress = True
        self.logger.info("Starting login process...")
        
        async def login_task():
            try:
                success = await self.send_login_command()
                if success:
                    GLib.idle_add(self.on_login_success)
            except Exception as e:
                self.logger.error(f"Login task error: {str(e)}")
            finally:
                self.login_in_progress = False
                GLib.idle_add(self.hide_spinner)
                self.logger.info("Login task completed")
        
        # Schedule login task in the event loop
        self.logger.info("Scheduling login task")
        future = asyncio.run_coroutine_threadsafe(login_task(), self.loop)
        future.add_done_callback(lambda f: self.logger.info("Login task future completed"))

    async def establish_connection(self, address: str, port: int) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Establish connection with proper handshake"""
        try:
            self.logger.info(f"Connecting to {address}:{port}")
            
            # Create connection
            reader, writer = await asyncio.open_connection(address, port)
            
            # Configure socket
            sock = writer.get_extra_info('socket')
            if sock is not None:
                # Enable TCP keepalive
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                # Set TCP keepalive time (seconds)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
                # Set TCP keepalive interval (seconds)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 60)
                # Set TCP keepalive retry count
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)
            
            self.logger.info(f"Connection established with {address}:{port}")
            
            # Initial read to clear any pending data
            try:
                initial_data = await asyncio.wait_for(reader.read(1024), timeout=1.0)
                if initial_data:
                    self.logger.debug(f"Received initial data: {initial_data.decode('utf-8', errors='ignore')}")
            except asyncio.TimeoutError:
                self.logger.debug("No initial data received")
            
            return reader, writer
            
        except Exception as e:
            self.logger.error(f"Connection establishment failed: {str(e)}")
            raise

    async def send_command(self, writer, reader, cmd: str, log_cmd=True, retry_count=1) -> Optional[str]:
        """Send a command and read response with improved error handling."""
        if log_cmd:
            self.logger.info(f"Sending: {cmd}")
        else:
            self.logger.info("Sending command (credentials masked)")
            
        for attempt in range(retry_count):
            try:
                # Ensure command ends with \r\n
                if not cmd.endswith('\r\n'):
                    cmd += '\r\n'
                    
                # Send command
                cmd_bytes = cmd.encode('utf-8')
                writer.write(cmd_bytes)
                await writer.drain()
                self.logger.debug(f"Command sent ({len(cmd_bytes)} bytes), waiting for response...")
                
                # Read response with timeout
                response = await self._read_complete_response(reader)
                if response:
                    if log_cmd:
                        self.logger.debug(f"Received response: {response}")
                    return response
                    
                self.logger.warning(f"No response received (attempt {attempt + 1}/{retry_count})")
                if attempt < retry_count - 1:
                    await asyncio.sleep(1)  # Longer wait between retries
                    
            except Exception as e:
                self.logger.error(f"Error sending command (attempt {attempt + 1}): {str(e)}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(1)
                    
        return None

    async def send_login_command(self) -> bool:
        """Login to the selected HEOS device using user-provided credentials."""
        try:
            GLib.idle_add(self.show_spinner)

            if not self.connection or (self.connection[1].is_closing()):
                if not self.selected_device:
                    self.logger.error("No device selected")
                    GLib.idle_add(lambda: self.show_error_toast("No device found"))
                    return False

                address = self.selected_device['address']
                port = self.selected_device['port']
                
                try:
                    reader, writer = await self.establish_connection(address, port)
                    self.connection = (reader, writer)
                except Exception as e:
                    self.logger.error(f"Failed to connect: {str(e)}")
                    GLib.idle_add(lambda: self.show_error_toast(f"Connection failed: {str(e)}"))
                    return False

            reader, writer = self.connection

            # Get username and password first
            username = self.username_entry.get_text().strip()
            password = self.password_entry.get_text().strip()

            if not username or not password:
                self.logger.error("Username or password is empty")
                GLib.idle_add(lambda: self.show_error_toast("Please enter username and password"))
                return False

            # Test connection with heartbeat
            heartbeat_cmd = "heos://system/heart_beat"
            self.logger.info("Testing connection with heartbeat")
            heartbeat_response = await self.send_command(writer, reader, heartbeat_cmd, retry_count=2)
            if not heartbeat_response:
                self.logger.error("No response to heartbeat")
                GLib.idle_add(lambda: self.show_error_toast("Device not responding"))
                return False
            self.logger.info(f"Heartbeat response: {heartbeat_response}")

            # Send login command
            self.logger.info("Preparing login command")
            encoded_username = base64.b64encode(username.encode('utf-8')).decode('utf-8')
            encoded_password = base64.b64encode(password.encode('utf-8')).decode('utf-8')

            login_cmd = f"heos://system/sign_in?un={encoded_username}&pw={encoded_password}"
            self.logger.info("Sending login command")
            response_str = await self.send_command(writer, reader, login_cmd, log_cmd=False, retry_count=2)

            if not response_str:
                self.logger.error("No response from login command")
                GLib.idle_add(lambda: self.show_error_toast("No response from device"))
                return False

            self.logger.info(f"Login response received: {response_str}")
            
            if "signed_in" in response_str or "success" in response_str:
                self.logger.info("Login successful")
                return True
            else:
                self.logger.error(f"Login failed: {response_str}")
                GLib.idle_add(lambda: self.show_error_toast("Login failed - please check credentials"))
                return False

        except asyncio.TimeoutError:
            self.logger.error("Login timeout")
            GLib.idle_add(lambda: self.show_error_toast("Login timeout - please try again"))
            return False

        except Exception as e:
            self.logger.error(f"Login error: {str(e)}")
            GLib.idle_add(lambda: self.show_error_toast("Login error - please try again"))
            return False

    async def on_login_success(self):
        """Handle successful login"""
        try:
            if self.connection:
                reader, writer = self.connection
        except Exception as e:
            self.logger.warning(f"Failed to handle login success: {str(e)}")
            # Continue anyway as login was successful

        GLib.idle_add(self.show_info_toast, "Login successful!")
        GLib.idle_add(self.stack.set_visible_child_name, "player_page")

    async def _read_complete_response(self, reader, timeout=5.0) -> Optional[str]:
        """Read a complete response from the reader with improved timeout handling."""
        try:
            response_data = bytearray()
            start_time = time.time()
            
            while True:
                if time.time() - start_time > timeout:
                    if response_data:
                        break  # Return what we have if timeout with data
                    self.logger.warning("Response read timeout with no data")
                    return None
                    
                try:
                    chunk = await asyncio.wait_for(reader.read(1024), timeout=1.0)
                    if chunk:
                        response_data.extend(chunk)
                        if b'\r\n' in chunk:  # HEOS responses end with \r\n
                            break
                    elif response_data:  # If we have data but got empty chunk
                        break
                    else:
                        await asyncio.sleep(0.1)
                        
                except asyncio.TimeoutError:
                    if response_data:  # If we have partial data, try one more read
                        try:
                            final_chunk = await asyncio.wait_for(reader.read(1024), timeout=0.5)
                            if final_chunk:
                                response_data.extend(final_chunk)
                        except asyncio.TimeoutError:
                            pass
                        break
                    continue
                    
            if response_data:
                result = response_data.decode('utf-8').strip()
                self.logger.debug(f"Read complete response: {result}")
                return result
            return None
            
        except Exception as e:
            self.logger.error(f"Error reading response: {str(e)}")
            return None

    def show_spinner(self):
        """Show the spinner widget"""
        if self.spinner:
            self.spinner.start()
            self.spinner.set_visible(True)
            
    def hide_spinner(self):
        """Hide the spinner widget"""
        if self.spinner:
            self.spinner.stop()
            self.spinner.set_visible(False)
            
    def show_error_toast(self, message: str):
        """Show an error message in a toast"""
        if self.toast_overlay:
            toast = Adw.Toast.new(message)
            toast.set_timeout(3)
            self.toast_overlay.add_toast(toast)
            
    def on_window_close(self, *args):
        """Handle window close event"""
        self.logger.info("Window closing, cleaning up...")
        self.cleanup()
        self.get_application().quit()
        return False

    def cleanup(self):
        """Clean up resources before closing."""
        self.logger.info("Starting cleanup")
        try:
            self.logger.info("Canceling all tasks")
            for task in asyncio.all_tasks(self.loop):
                task.cancel()
            
            self.logger.info("Stopping event loop")
            self.loop.call_soon_threadsafe(self.loop.stop)
            
            self.logger.info("Waiting for event loop thread to finish")
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=1.0)
            
            self.logger.info("Closing event loop")
            self.loop.close()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}", exc_info=True)
        
        self.logger.info("Cleanup completed")

    def on_play_clicked(self, button):
        self.logger.info("Play button clicked")

    def on_next_clicked(self, button):
        self.logger.info("Next button clicked")

    def on_prev_clicked(self, button):
        self.logger.info("Previous button clicked")

    def on_volume_changed(self, scale):
        self.logger.info("Volume changed")

    def show_info_toast(self, message: str):
        """Show info message in a toast."""
        toast = Adw.Toast.new(message)
        toast.set_timeout(5)
        self.toast_overlay.add_toast(toast)

    def update_devices_list(self, devices: List[Dict]):
        """Update the devices list in the UI"""
        self.logger.info(f"Updating devices list with {len(devices)} devices")
        
        # Clear existing items
        while True:
            row = self.devices_list.get_first_child()
            if row is None:
                break
            self.devices_list.remove(row)
            
        # Add new items
        for device in devices:
            try:
                model = device['properties'][b'model'].decode()
                name = device['name']
                
                row = Adw.ActionRow()
                row.set_title(name)
                row.set_subtitle(model)
                row.device_info = device  # Store device info for selection
                
                # Mark first device as selected
                if device == self.selected_device:
                    row.set_subtitle(f"{model} (Selected)")
                
                self.devices_list.append(row)
            except Exception as e:
                self.logger.error(f"Error adding device to list: {e}")
                
        self.devices_list.show()

    def on_device_selected(self, row):
        """Handle device selection"""
        try:
            self.selected_device = row.device_info
            self.logger.info(f"Selected device: {self.selected_device['name']}")
            
            # Enable login button if we have credentials
            if self.username_entry and self.password_entry:
                username = self.username_entry.get_text()
                password = self.password_entry.get_text()
                if username and password:
                    self.login_button.set_sensitive(True)
                    return
                    
            self.login_button.set_sensitive(False)
            
        except Exception as e:
            self.logger.error(f"Error handling device selection: {e}")
            self.show_error_toast("Error selecting device")

    def show_about_dialog(self):
        """Show the About dialog with application information and disclaimer."""
        about_dialog = Gtk.AboutDialog()
        about_dialog.set_program_name("HEOS Controller")
        about_dialog.set_version("1.0")
        about_dialog.set_comments("Control your HEOS devices from your computer.")
        about_dialog.set_license_type(Gtk.License.GPL_3_0)

        # Properly escape ampersands in the markup
        about_dialog.set_copyright(
            "HEOS, DENON and Marantz are trademarks of D&amp;M Holdings Inc. "
            "The developers of this module are in no way endorsed by or affiliated with "
            "D&amp;M Holdings Inc., or any associated subsidiaries, logos or trademarks."
        )

        about_dialog.set_website("https://example.com")
        about_dialog.set_website_label("Visit our website")

        about_dialog.run()
        about_dialog.destroy()


class HeosApplication(Adw.Application):
    """Main application class"""
    def __init__(self):
        super().__init__(application_id='com.github.heos.controller',
                        flags=Gio.ApplicationFlags.FLAGS_NONE)
        
        self.window = None
        self.connect('activate', self.on_activate)
        
    def on_activate(self, app):
        """Called when the application is activated"""
        self.window = HeosWindow(application=app)
        self.window.present()

def main(version):
    app = HeosApplication()
    return app.run(sys.argv)

if __name__ == '__main__':
    sys.exit(main(None))