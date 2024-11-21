// Device details modal component
function showDeviceDetails(device) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-header">
                <h2>${device.info?.name || device.name || device.ip}</h2>
                <button class="close-button" onclick="closeModal(this)">×</button>
            </div>
            <div class="modal-body">
                <div class="details-grid">
                    <div class="detail-group">
                        <h3>Player Controls</h3>
                        <div class="player-controls">
                            <button class="control-button" onclick="sendPlayerCommand('${device.ip}', 'player/play')">
                                <svg viewBox="0 0 24 24" class="control-icon">
                                    <path d="M8 5v14l11-7z"/>
                                </svg>
                                Play
                            </button>
                            <button class="control-button" onclick="sendPlayerCommand('${device.ip}', 'player/pause')">
                                <svg viewBox="0 0 24 24" class="control-icon">
                                    <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                                </svg>
                                Pause
                            </button>
                            <button class="control-button" onclick="sendPlayerCommand('${device.ip}', 'player/stop')">
                                <svg viewBox="0 0 24 24" class="control-icon">
                                    <path d="M6 6h12v12H6z"/>
                                </svg>
                                Stop
                            </button>
                            <div class="volume-control">
                                <input type="range" min="0" max="100" value="50" 
                                    onchange="sendPlayerCommand('${device.ip}', 'player/set_volume', {level: this.value})"
                                    class="volume-slider">
                                <label>Volume</label>
                            </div>
                        </div>
                    </div>

                    <div class="detail-group">
                        <h3>Basic Information</h3>
                        <div class="detail-item">
                            <span class="label">Name:</span>
                            <span class="value">${device.info?.name || device.name || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">Model:</span>
                            <span class="value">${device.info?.model || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">Version:</span>
                            <span class="value">${device.info?.version || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">Serial:</span>
                            <span class="value">${device.info?.serial || 'N/A'}</span>
                        </div>
                    </div>
                    
                    <div class="detail-group">
                        <h3>Network Information</h3>
                        <div class="detail-item">
                            <span class="label">IP Address:</span>
                            <span class="value">${device.ip || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">Status:</span>
                            <span class="value status-${device.status || 'initializing'}">${device.status || 'Initializing'}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Close modal when clicking outside
    modal.onclick = () => closeModal(modal);

    document.body.appendChild(modal);
    setTimeout(() => modal.classList.add('visible'), 10);
}

function closeModal(element) {
    const modal = element.closest('.modal-overlay');
    modal.classList.remove('visible');
    setTimeout(() => modal.remove(), 300);
}

async function sendPlayerCommand(ip, command, params = {}) {
    try {
        console.log(`Sending command: ${command} to ${ip} with params:`, params);
        
        const response = await fetch(`/api/player/${ip}/command`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                command: command,
                params: params
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        console.log('Command result:', result);
        
        // Update UI based on command response
        if (result.heos?.result === 'success') {
            showNotification(`${command.split('/')[1]} command sent successfully`, 'success');
        } else {
            showNotification(result.heos?.message || 'Command failed', 'error');
        }
        
        // Update player status after command
        setTimeout(() => updatePlayerStatus(ip), 500);
        
    } catch (error) {
        console.error('Error sending command:', error);
        showNotification('Error sending command: ' + error.message, 'error');
    }
}

async function updatePlayerStatus(ip) {
    try {
        const response = await fetch(`/api/player/${ip}/status`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const status = await response.json();
        console.log('Player status:', status);
        
        // Update UI based on status
        const controls = document.querySelector('.player-controls');
        if (controls) {
            const buttons = controls.querySelectorAll('.control-button');
            buttons.forEach(button => {
                button.classList.remove('active');
                if (status.state && button.textContent.trim().toLowerCase() === status.state.toLowerCase()) {
                    button.classList.add('active');
                }
            });
        }
    } catch (error) {
        console.error('Error updating status:', error);
    }
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}
