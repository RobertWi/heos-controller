// preload.js
const { contextBridge, ipcRenderer } = require('electron');

// Store error logs
let errorLogs = [];

// Listen for error logs from main process
ipcRenderer.on('error-log', (event, log) => {
  errorLogs.push(log);
  // Keep only last 100 errors
  if (errorLogs.length > 100) {
    errorLogs.shift();
  }
  // Notify any listeners
  window.dispatchEvent(new CustomEvent('error-log-updated', { detail: log }));
});

// Expose protected methods that allow the renderer process to use
contextBridge.exposeInMainWorld('api', {
    async discoverDevices() {
        try {
            console.log('Starting device discovery...');
            const response = await fetch('http://localhost:8000/discover');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log('Discovery response:', data);
            return data;
        } catch (error) {
            console.error('Error discovering devices:', error);
            throw error;
        }
    },

    async sendCommand(ip, command, params = null) {
        try {
            console.log(`Sending command to ${ip}: ${command}`, params);
            const url = new URL(`http://localhost:8000/command/${ip}/${command}`);
            if (params) {
                Object.keys(params).forEach(key => 
                    url.searchParams.append(key, params[key])
                );
            }
            const response = await fetch(url, {
                method: 'POST',
            });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log('Command response:', data);
            return data;
        } catch (error) {
            console.error('Error sending command:', error);
            throw error;
        }
    },

    getErrorLogs: () => errorLogs,
    clearErrorLogs: () => {
      errorLogs = [];
      window.dispatchEvent(new CustomEvent('error-logs-cleared'));
    },
    onErrorLog: (callback) => {
      window.addEventListener('error-log-updated', (event) => callback(event.detail));
    },
    onErrorLogsCleared: (callback) => {
      window.addEventListener('error-logs-cleared', callback);
    }
});
