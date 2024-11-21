// Renderer process code

// Add this at the top of the file
function initTheme() {
    // Check if dark mode is enabled in system
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.classList.add('dark');
    }

    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', event => {
        if (event.matches) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
});

document.addEventListener('alpine:init', () => {
    Alpine.data('heosController', () => ({
        deviceList: [],
        isLoading: false,
        errorMessage: null,
        lastDiscoveryTime: null,
        discoveryInProgress: false,
        errorLogs: [],
        showErrorPane: false,

        init() {
            console.log('Initializing HEOS controller...');
            this.discoverDevices();
            this.setupErrorLogging();
            // Poll for devices every 30 seconds
            setInterval(() => {
                // Only discover if not already in progress
                if (!this.discoveryInProgress) {
                    this.discoverDevices();
                }
            }, 30000); // 30 seconds
        },

        setupErrorLogging() {
            // Load initial error logs
            this.errorLogs = window.api.getErrorLogs();

            // Listen for new error logs
            window.api.onErrorLog((log) => {
                this.errorLogs.push(log);
                // Keep only last 100 errors
                if (this.errorLogs.length > 100) {
                    this.errorLogs.shift();
                }
            });

            // Listen for cleared logs
            window.api.onErrorLogsCleared(() => {
                this.errorLogs = [];
            });
        },

        clearErrorLogs() {
            window.api.clearErrorLogs();
        },

        toggleErrorPane() {
            this.showErrorPane = !this.showErrorPane;
        },

        formatTimestamp(timestamp) {
            return new Date(timestamp).toLocaleString();
        },

        async discoverDevices() {
            if (this.discoveryInProgress) {
                console.log('Discovery already in progress, skipping...');
                return;
            }
            
            this.discoveryInProgress = true;
            this.isLoading = true;
            this.errorMessage = '';
            
            try {
                console.log('Starting device discovery...');
                const response = await fetch('http://localhost:8000/api/discover', {
                    method: 'GET',
                    headers: {
                        'Accept': 'application/json',
                    }
                });
                
                if (!response.ok) {
                    let errorMessage = 'Failed to discover devices';
                    try {
                        const errorData = await response.json();
                        errorMessage = errorData.detail || errorMessage;
                    } catch (e) {
                        // If response isn't JSON, try to get text
                        errorMessage = await response.text() || errorMessage;
                    }
                    throw new Error(errorMessage);
                }
                
                const data = await response.json();
                console.log('Discovery response:', data);
                
                if (!data.devices || !Array.isArray(data.devices)) {
                    throw new Error('Invalid response format: missing devices array');
                }
                
                if (data.devices.length === 0) {
                    this.errorMessage = 'No HEOS devices found on your network';
                    this.deviceList = [];
                    return;
                }
                
                // Update device list with error handling for each device
                this.deviceList = data.devices.map(device => ({
                    ...device,
                    state: device.state?.play_state || 'stopped',
                    volume: device.state?.volume || 0,
                    // Add default values for required fields
                    name: device.info?.name || 'Unknown Device',
                    model: device.info?.model || 'Unknown Model',
                    ip: device.ip || 'Unknown IP',
                    status: device.status || 'unknown',
                    error: device.error || null
                }));
                
                // Start polling for device status
                this.deviceList.forEach(device => {
                    if (device.status === 'connected') {
                        this.pollDeviceStatus(device);
                    }
                });
                
                this.lastDiscoveryTime = Date.now();
                console.log('Device discovery completed successfully');
                
            } catch (error) {
                console.error('Error during device discovery:', error);
                this.errorMessage = `Discovery failed: ${error.message}`;
                this.deviceList = [];
            } finally {
                this.isLoading = false;
                this.discoveryInProgress = false;
            }
        },
        
        async pollDeviceStatus(device) {
            if (!device || !device.ip) return;
            
            const pollStatus = async () => {
                try {
                    // Get volume
                    const volumeResponse = await this.sendCommand(device.ip, 'player/get_volume');
                    if (volumeResponse.heos?.result === 'success') {
                        device.volume = parseInt(volumeResponse.payload?.level || 0);
                    }
                    
                    // Get play state
                    const stateResponse = await this.sendCommand(device.ip, 'player/get_play_state');
                    if (stateResponse.heos?.result === 'success') {
                        device.state = stateResponse.payload?.state?.toLowerCase() || 'stopped';
                    }
                    
                    device.status = 'connected';
                    device.error = null;
                    
                } catch (error) {
                    console.error(`Error polling device ${device.ip}:`, error);
                    device.status = 'error';
                    device.error = error.message;
                }
            };
            
            // Initial poll
            await pollStatus();
            
            // Continue polling every 5 seconds if device is connected
            const intervalId = setInterval(async () => {
                if (device.status === 'connected') {
                    await pollStatus();
                } else {
                    clearInterval(intervalId);
                }
            }, 5000);
        },
        
        async sendCommand(ip, command, value = null) {
            if (!ip || !command) {
                console.error('Invalid command parameters:', { ip, command, value });
                return;
            }
            
            try {
                this.errorMessage = '';
                console.log(`Sending command ${command} to ${ip}`);
                
                const result = await window.api.sendCommand(ip, command, value ? { value } : null);
                console.log(`Command ${command} result:`, result);
                
            } catch (error) {
                console.error(`Error sending ${command} command:`, error);
                this.errorMessage = `Failed to send ${command} command: ${error.message}`;
            }
        }
    }))
});

// Add refresh button functionality
const refreshButton = document.createElement('button');
refreshButton.innerHTML = '<i class="fas fa-sync-alt"></i>';
refreshButton.className = 'refresh-button';
refreshButton.onclick = () => {
    const controller = Alpine.evaluate(document.querySelector('[x-data]'), 'heosController');
    controller.discoverDevices();
};
document.body.appendChild(refreshButton);

const deviceList = document.getElementById('device-list');

function createDeviceCard(device) {
    return `
        <div class="device-card bg-white rounded-lg shadow-md p-4 flex items-center gap-4">
            <div class="device-status-group flex flex-col items-center gap-2">
                <i class="device-icon fas ${device.model.toLowerCase().includes('speaker') ? 'fa-volume-up' : 'fa-tv'} text-2xl text-gray-700"></i>
                <div class="status-indicator ${device.state === 'playing' ? 'active' : ''}"></div>
            </div>
            
            <div class="device-info flex-grow">
                <h3 class="device-name font-medium text-gray-900">${device.name}</h3>
                <span class="device-model text-sm text-gray-500">${device.model}</span>
            </div>
            
            <div class="device-controls flex items-center gap-4">
                <button class="play-pause-btn bg-white rounded-full p-2 hover:bg-gray-100" data-pid="${device.pid}">
                    <i class="fas ${device.state === 'playing' ? 'fa-pause' : 'fa-play'} text-gray-700"></i>
                </button>
                
                <div class="volume-control flex items-center gap-2">
                    <input type="range" class="volume-slider" min="0" max="100" value="${device.volume}" data-pid="${device.pid}">
                </div>
                
                <div class="waveform ${device.state === 'playing' ? 'playing' : ''}">
                    <div class="bar"></div>
                    <div class="bar"></div>
                    <div class="bar"></div>
                </div>
            </div>
        </div>
    `;
}

// Update device list when it changes
Alpine.effect(() => {
    const heosController = Alpine.store('heosController');
    deviceList.innerHTML = '';
    heosController.deviceList.forEach(device => {
        deviceList.innerHTML += createDeviceCard(device);
    });

    // Add event listeners after adding cards to DOM
    document.querySelectorAll('.play-pause-btn').forEach(btn => {
        btn.onclick = async function() {
            const pid = this.dataset.pid;
            const device = heosController.deviceList.find(d => d.pid === pid);
            if (device) {
                const isPlaying = this.querySelector('i').classList.contains('fa-pause');
                await heosController.sendCommand(device.ip, isPlaying ? 'pause' : 'play');
                
                // Toggle play/pause icon
                const icon = this.querySelector('i');
                icon.classList.toggle('fa-play');
                icon.classList.toggle('fa-pause');
                
                // Toggle waveform animation
                const card = this.closest('.device-card');
                const waveform = card.querySelector('.waveform');
                waveform.classList.toggle('playing', !isPlaying);
            }
        };
    });

    document.querySelectorAll('.volume-slider').forEach(slider => {
        slider.oninput = async function() {
            const pid = this.dataset.pid;
            const device = heosController.deviceList.find(d => d.pid === pid);
            if (device) {
                await heosController.sendCommand(device.ip, 'volume', this.value);
            }
        };
    });
});
