
// ================================================
// INITIALIZATION AND GLOBAL INSTANCES
// ================================================

// Global instances
let aiSystemPanel = null;
let governancePanel = null;
let intelligenceArena = null;
let activeWidget = null;
let backendOnline = false;

// Initialize dashboard on page load
document.addEventListener('DOMContentLoaded', async function () {
    console.log('🚀 Aura IA Dashboard initializing...');

    // Initialize timestamp
    updateTimestamp();
    setInterval(updateTimestamp, 1000);

    // Initialize AI System Panel
    aiSystemPanel = new AISystemPanel();
    aiSystemPanel.initialize();

    // Initialize Governance Panel
    governancePanel = new GovernancePanel();
    governancePanel.initialize();

    // Initialize Intelligence Arena
    intelligenceArena = new IntelligenceArenaPanel();
    intelligenceArena.initialize();

    // Check backend health
    await checkBackendStatus();
    setInterval(checkBackendStatus, 30000);

    // Setup system monitoring
    setupSystemWebSocket();
    setInterval(updateSystemStats, 10000);

    // Setup monitor links
    setupMonitorLinks();

    console.log('✅ Aura IA Dashboard initialized successfully');
});

// Update timestamp display
function updateTimestamp() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString();
    const dateStr = now.toLocaleDateString();
    const el = document.getElementById('timestamp');
    if (el) el.textContent = `${dateStr} ${timeStr}`;
}

// Check backend health status
async function checkBackendStatus() {
    try {
        const response = await fetchWithTimeout(`${API_URL}/healthz`, {}, 3000);
        backendOnline = response.ok;

        const statusEl = document.getElementById('backend-status');
        if (statusEl) {
            if (backendOnline) {
                statusEl.innerHTML = '<span style="width: 8px; height: 8px; border-radius: 50%; background: var(--success);"></span><span>Backend: Online</span>';
            } else {
                statusEl.innerHTML = '<span style="width: 8px; height: 8px; border-radius: 50%; background: var(--danger); animation: pulse 2s infinite;"></span><span>Backend: Offline</span>';
            }
        }

        updateWidgetDots();

    } catch (error) {
        backendOnline = false;
        updateWidgetDots();
    }
}

// Setup system monitoring WebSocket
function setupSystemWebSocket() {
    if (!window.wsManager) {
        window.wsManager = new WebSocketManager();
    }

    window.wsManager.connect(
        'system',
        (data) => {
            if (data.type === 'system_update') {
                updateMonitorUI(data);
            }
        },
        (error) => {
            console.warn('System WebSocket error:', error);
        }
    );
}

// Setup monitor tool links
function setupMonitorLinks() {
    document.querySelectorAll('.widget-icon.monitor-link').forEach(icon => {
        icon.addEventListener('click', function (e) {
            e.stopPropagation();
            const url = this.getAttribute('data-monitor-url');
            const label = this.getAttribute('data-monitor-label');
            if (url) {
                window.open(url, '_blank');
                pushUiAlert(`Opening ${label}...`, 'success');
            }
        });
    });
}

// Utility: fetch with timeout
function fetchWithTimeout(url, options = {}, timeout = 5000) {
    return Promise.race([
        fetch(url, options),
        new Promise((_, reject) =>
            setTimeout(() => reject(new Error('Request timeout')), timeout)
        )
    ]);
}

// Utility: push UI alert
function pushUiAlert(message, type = 'info') {
    const alertsContainer = document.getElementById('ui-alerts');
    if (!alertsContainer) return;

    const alert = document.createElement('div');
    alert.className = `ui-alert ui-alert-${type}`;
    alert.textContent = message;

    alertsContainer.appendChild(alert);

    setTimeout(() => {
        alert.classList.add('ui-alert-hide');
        setTimeout(() => alert.remove(), 300);
    }, 3000);
}

// View switching function
function switchView(viewId) {
    document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
    const target = document.getElementById(`view-${viewId}`);
    if (target) target.classList.add('active');

    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    const navItem = document.getElementById(`nav-${viewId}`);
    if (navItem) navItem.classList.add('active');

    if (viewId === 'monitor') {
        setupSystemWebSocket();
        updateSystemStats();
    } else if (viewId === 'governance' && governancePanel) {
        governancePanel.fetchGovernanceDataHTTP();
    } else if (viewId === 'intelligence' && intelligenceArena) {
        intelligenceArena.fetchModelStatistics();
        intelligenceArena.fetchDebateHistory();
    }
}

// Chat dropdown functions
function toggleChatDropdown() {
    const menu = document.getElementById('chat-dropdown-menu');
    if (menu) menu.classList.toggle('show');
}

function selectChatMode(mode) {
    const modeText = {
        'auto': '✨ Auto (Smart Routing)',
        'concierge': '🤖 MCP Concierge',
        'general': '💬 General Chat',
        'mcp': '🔧 MCP Commands',
        'debug': '🐛 Debug Mode'
    };

    currentChatMode = mode;
    const modeDisplay = document.getElementById('chat-mode-text');
    if (modeDisplay) {
        modeDisplay.textContent = modeText[mode] || 'Unknown Mode';
    }

    document.querySelectorAll('.chat-dropdown-item').forEach(item => {
        if (item.getAttribute('data-mode') === mode) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    const menu = document.getElementById('chat-dropdown-menu');
    if (menu) menu.classList.remove('show');

    pushUiAlert(`Chat mode: ${modeText[mode]}`, 'success');
}

// Format uptime helper
function formatUptime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return `${h}h ${m}m ${s}s`;
}

// Render HNSC panel placeholder
function renderHNSCPanel() {
    console.log('🏗️ HNSC Panel rendering...');
}

// Instant apply for control toggles
function instantApply(feature, enabled) {
    console.log(`⚙️ ${feature}: ${enabled ? 'enabled' : 'disabled'}`);
    pushUiAlert(`${feature} ${enabled ? 'enabled' : 'disabled'}`, 'success');
}

console.log('📡 Aura IA Dashboard script loaded');
