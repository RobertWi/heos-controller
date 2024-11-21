const { app, BrowserWindow } = require('electron');
const path = require('path');

let mainWindow;

// Error logging function
function logError(message, error = null) {
  const timestamp = new Date().toISOString();
  const errorLog = {
    timestamp,
    message,
    error: error ? error.toString() : null,
    stack: error?.stack
  };
  
  if (mainWindow?.webContents) {
    mainWindow.webContents.send('error-log', errorLog);
  }
  
  console.error(`[${timestamp}] ${message}`, error || '');
}

// Create main browser window
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: true,
      webSecurity: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  // Set Content Security Policy
  mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          "default-src 'self' http://localhost:8000;" +
          "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com;" +
          "style-src 'self' 'unsafe-inline';" +
          "font-src 'self' data:;" +
          "connect-src 'self' http://localhost:8000 ws://localhost:*;" +
          "img-src 'self' data: http://localhost:*"
        ]
      }
    });
  });

  // Log the current directory and file path
  console.log('Current directory:', __dirname);
  console.log('Index path:', path.join(__dirname, 'index.html'));

  // Load index.html
  mainWindow.loadFile(path.join(__dirname, 'index.html'))
    .catch(err => {
      console.error('Failed to load index.html:', err);
      app.quit();
    });

  // Open DevTools in development
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }

  // Log any window errors
  mainWindow.webContents.on('crashed', (event) => {
    console.error('Window crashed:', event);
    logError('Window crashed', event);
  });

  mainWindow.on('unresponsive', () => {
    console.error('Window became unresponsive');
    logError('Window became unresponsive');
  });

  // Log any console messages from the renderer
  mainWindow.webContents.on('console-message', (event, level, message, line, sourceId) => {
    console.log('Renderer Console:', message);
  });

  // Log any load failures
  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    console.error('Page failed to load:', errorCode, errorDescription);
  });
}

// Handle app ready
app.whenReady().then(() => {
  createWindow();
  
  // Log any uncaught exceptions
  process.on('uncaughtException', (error) => {
    logError('Uncaught Exception:', error);
  });

  process.on('unhandledRejection', (error) => {
    logError('Unhandled Promise Rejection:', error);
  });

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
}).catch(err => {
  console.error('Failed to initialize app:', err);
  app.quit();
});

// Quit when all windows are closed.
app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});
