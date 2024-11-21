// Theme management
function initTheme() {
    const theme = localStorage.getItem('theme') || 'dark'; // Default to dark
    applyTheme(theme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    applyTheme(newTheme);
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    
    // Update icon to show the opposite of current theme (sun in dark mode, moon in light mode)
    const toggle = document.getElementById('themeToggle');
    if (toggle) {
        toggle.innerHTML = theme === 'light' ? '🌙' : '☀️';
    }
    
    // Apply theme classes to body
    document.body.className = theme === 'light' ? 'bg-white text-black' : 'bg-dark-primary text-dark-text';
}

// Initialize theme on page load
document.addEventListener('DOMContentLoaded', initTheme);
