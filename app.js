/* Aura IA MCP Dashboard Logic - V2.0 Enterprise */
/* MCP Concierge - HNSC Architecture Integration */
/* Audio I/O Support - MCP-Bound STT/TTS Tools (PRD 8.12) */

// Auto-detect server host (works for localhost AND remote deployment)
const SERVER_HOST = window.location.hostname || 'localhost';
const API_URL = `http://${SERVER_HOST}:9200`; // MCP Server (all tools MCP-bound)
const ML_BACKEND_URL = `http://${SERVER_HOST}:9201`; // ML Backend
// Audio endpoints are now MCP-bound at API_URL/api/audio/*

// State
let activityLog = [];
let activityStats = {
    total: 0,
    active: 0,
    completed: 0,
    failed: 0
};
let currentChatMode = 'concierge';

// === AI SYSTEM PANEL CLASS ===
class AISystemPanel {
    constructor() {
        this.wsManager = null;
        this.modelData = null;
        this.isInitialized = false;
        this.updateInterval = null;
    }

    initialize() {
        if (this.isInitialized) return;

        // Initialize WebSocket manager if not already done
        if (!window.wsManager) {
            window.wsManager = new WebSocketManager();
        }
        this.wsManager = window.wsManager;

        // Connect to models WebSocket
        this.initializeWebSocket();

        // Set up periodic updates as fallback
        this.setupPeriodicUpdates();

        this.isInitialized = true;
        console.log('🧠 AI System Panel initialized');
    }

    initializeWebSocket() {
        this.wsManager.connect(
            'models',
            (data) => this.handleModelUpdate(data),
            (error) => this.handleConnectionError(error)
        );
    }

    handleModelUpdate(data) {
        if (data.type === 'model_update') {
            this.modelData = data;
            this.updateDisplay();
            console.log('🧠 AI System Panel: Model data updated via WebSocket');
        }
    }

    handleConnectionError(error) {
        console.warn('🧠 AI System Panel WebSocket error:', error);
        this.showConnectionError('WebSocket connection failed, using HTTP fallback');
    }

    setupPeriodicUpdates() {
        // Update every 10 seconds as fallback
        this.updateInterval = setInterval(() => {
            if (this.wsManager.getStatus('models') !== 'connected') {
                this.fetchModelDataHTTP();
            }
        }, 10000);
    }

    async fetchModelDataHTTP() {
        try {
            // Try the new model status endpoint first
            const response = await fetchWithTimeout(`http://${SERVER_HOST}:9200/v1/models/status`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            }, 5000);

            if (response.ok) {
                const data = await response.json();
                this.modelData = {
                    type: 'model_update',
                    loaded_models: data.loaded_models || [],
                    available_models: data.available_models || [],
                    memory_usage: data.memory_usage || {},
                    model_stats: data.model_stats || [],
                    timestamp: new Date().toISOString()
                };
                this.updateDisplay();
                return;
            }
        } catch (error) {
            console.debug('Model status endpoint failed, trying Ollama direct:', error.message);
        }

        // Fallback to direct Ollama API
        try {
            const response = await fetchWithTimeout(`http://${SERVER_HOST}:9207/api/tags`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            }, 5000);

            if (response.ok) {
                const data = await response.json();
                this.modelData = {
                    type: 'model_update',
                    loaded_models: data.models || [],
                    available_models: data.models?.map(m => m.name) || [],
                    memory_usage: {},
                    model_stats: [],
                    timestamp: new Date().toISOString()
                };
                this.updateDisplay();
            }
        } catch (error) {
            console.debug('Ollama API failed:', error.message);
            this.showNoModelsState();
        }
    }

    updateDisplay() {
        const container = document.getElementById('ai-system-status');
        if (!container) {
            // Update the existing AI model display
            this.updateExistingDisplay();
            return;
        }

        if (!this.modelData || !this.modelData.loaded_models || this.modelData.loaded_models.length === 0) {
            this.showNoModelsState();
            return;
        }

        const modelsHtml = this.modelData.loaded_models.map(model => {
            const modelName = typeof model === 'string' ? model : (model.name || 'Unknown');
            const modelSize = model.size ? this.formatBytes(model.size) : 'Unknown size';
            const memoryUsage = this.modelData.memory_usage[modelName] || 0;

            return `
                <div class="model-card" style="background: rgba(0, 212, 255, 0.1); border: 1px solid var(--accent-cyan); border-radius: 8px; padding: 12px; margin-bottom: 8px;">
                    <div class="model-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <h4 style="color: var(--accent-cyan); margin: 0; font-size: 0.9em;">${modelName}</h4>
                        <span class="model-status active" style="background: var(--success); color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.7em;">Active</span>
                    </div>
                    <div class="model-stats" style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.8em;">
                        <div class="stat">
                            <label style="color: var(--text-secondary);">Size:</label>
                            <span style="color: var(--text-primary);">${modelSize}</span>
                        </div>
                        <div class="stat">
                            <label style="color: var(--text-secondary);">Memory:</label>
                            <span style="color: var(--text-primary);">${this.formatBytes(memoryUsage)}</span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = `
            <div class="models-grid">
                ${modelsHtml}
            </div>
            <div class="model-actions" style="margin-top: 12px; display: flex; gap: 8px;">
                <button onclick="aiSystemPanel.refreshModels()" class="btn btn-secondary" style="background: var(--bg-tertiary); border: 1px solid var(--accent-cyan); color: var(--accent-cyan); padding: 6px 12px; border-radius: 4px; cursor: pointer;">Refresh</button>
                <button onclick="aiSystemPanel.loadModel()" class="btn btn-primary" style="background: var(--accent-cyan); color: var(--bg-primary); padding: 6px 12px; border-radius: 4px; cursor: pointer; border: none;">Load Model</button>
            </div>
        `;
    }

    updateExistingDisplay() {
        // Update the existing AI model name display
        const modelEl = document.getElementById('ai-model-name');
        if (modelEl && this.modelData && this.modelData.loaded_models && this.modelData.loaded_models.length > 0) {
            const firstModel = this.modelData.loaded_models[0];
            const modelName = typeof firstModel === 'string' ? firstModel : (firstModel.name || 'Unknown');
            modelEl.textContent = modelName;
            modelEl.title = `${this.modelData.loaded_models.length} model(s) loaded`;
        }
    }

    showNoModelsState() {
        const container = document.getElementById('ai-system-status');
        if (container) {
            container.innerHTML = `
                <div class="no-models" style="text-align: center; padding: 20px; color: var(--text-secondary);">
                    <i class="fas fa-robot" style="font-size: 2em; margin-bottom: 10px; color: var(--accent-cyan);"></i>
                    <p style="margin: 8px 0;">No models currently loaded</p>
                    <button onclick="aiSystemPanel.loadDefaultModel()" class="btn btn-primary" style="background: var(--accent-cyan); color: var(--bg-primary); padding: 8px 16px; border-radius: 4px; cursor: pointer; border: none;">Load Default Model</button>
                </div>
            `;
        }

        // Also update existing display
        const modelEl = document.getElementById('ai-model-name');
        if (modelEl) {
            modelEl.textContent = 'No models loaded';
            modelEl.title = 'Click to load a model';
        }
    }

    showConnectionError(message) {
        const container = document.getElementById('ai-system-status');
        if (container) {
            container.innerHTML = `
                <div class="connection-error" style="text-align: center; padding: 20px; color: var(--warning);">
                    <i class="fas fa-exclamation-triangle" style="font-size: 2em; margin-bottom: 10px;"></i>
                    <p style="margin: 8px 0;">${message}</p>
                    <button onclick="aiSystemPanel.retry()" class="btn btn-secondary" style="background: var(--bg-tertiary); border: 1px solid var(--warning); color: var(--warning); padding: 6px 12px; border-radius: 4px; cursor: pointer;">Retry Connection</button>
                </div>
            `;
        }
    }

    formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        if (!bytes) return 'N/A';

        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    async refreshModels() {
        console.log('🔄 Refreshing model data...');
        await this.fetchModelDataHTTP();
    }

    async loadDefaultModel() {
        try {
            const response = await fetch(`http://${SERVER_HOST}:9200/v1/models/phi3.5:3.8b/load`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (response.ok) {
                console.log('✅ Default model loading initiated');
                // Refresh after a delay to show the loaded model
                setTimeout(() => this.refreshModels(), 2000);
            } else {
                console.error('❌ Failed to load default model');
            }
        } catch (error) {
            console.error('❌ Error loading default model:', error);
        }
    }

    async loadModel() {
        const modelName = prompt('Enter model name to load (e.g., llama3.1:8b):');
        if (!modelName) return;

        try {
            const response = await fetch(`http://${SERVER_HOST}:9200/v1/models/${modelName}/load`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (response.ok) {
                console.log(`✅ Model ${modelName} loading initiated`);
                setTimeout(() => this.refreshModels(), 2000);
            } else {
                console.error(`❌ Failed to load model ${modelName}`);
            }
        } catch (error) {
            console.error(`❌ Error loading model ${modelName}:`, error);
        }
    }

    retry() {
        console.log('🔄 Retrying AI System Panel connection...');
        this.initializeWebSocket();
        this.fetchModelDataHTTP();
    }

    destroy() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        if (this.wsManager) {
            this.wsManager.disconnect('models');
        }
        this.isInitialized = false;
    }
}

// === VIEW SWITCHING LOGIC ===
function switchView(viewId) {
    // Hide all views
    document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
    // Show target view
    const target = document.getElementById(`view-${viewId}`);
    if (target) target.classList.add('active');

    // Update Nav State
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    const navItem = document.getElementById(`nav-${viewId}`);
    if (navItem) navItem.classList.add('active');

    // Trigger specific view logic
    if (viewId === 'monitor') {
        setupSystemWebSocket();
    } else if (viewId === 'governance') {
        if (governancePanel && governancePanel.isInitialized) {
            governancePanel.fetchGovernanceDataHTTP();
        } else {
            fetchGovernanceData(); // Fallback to legacy function
        }
    } else if (viewId === 'intelligence') {
        if (intelligenceArena && intelligenceArena.isInitialized) {
            intelligenceArena.fetchModelStatistics();
            intelligenceArena.fetchDebateHistory();
        }
    }
}

// === SYSTEM MONITOR LOGIC ===
async function updateSystemStats() {
    try {
        const response = await fetch(`${ML_BACKEND_URL}/api/system/stats`);
        if (!response.ok) return;
        const stats = await response.json();

        // Update Metrics
        document.getElementById('monitor-uptime').textContent = formatUptime(stats.uptime_seconds);
        document.getElementById('monitor-rps').textContent = `${stats.requests_total} total`;
        const errRate = stats.requests_total > 0 ? ((stats.error_count / stats.requests_total) * 100).toFixed(1) : "0.0";
        document.getElementById('monitor-errors').textContent = `${errRate}%`;

        // Update Bars
        const cpu = stats.cpu_percent || 0;
        document.getElementById('cpu-val').textContent = `${cpu}%`;
        document.getElementById('cpu-bar').style.width = `${cpu}%`;

        const mem = stats.memory_mb || 0;
        document.getElementById('mem-val').textContent = `${mem} MB`;
        document.getElementById('mem-bar').style.width = `${Math.min(mem / 10, 100)}%`; // Arbitrary scale for now

        // Disk Usage
        const disk = stats.disk_percent || 0;
        document.getElementById('disk-val').textContent = `${disk}%`;
        document.getElementById('disk-bar').style.width = `${disk}%`;
        // Network Usage (show as KB/s or MB/s)
        let net = stats.network_kbps || 0;
        let netDisplay = net > 1024 ? `${(net / 1024).toFixed(1)} MB/s` : `${net.toFixed(1)} KB/s`;
        document.getElementById('network-val').textContent = netDisplay;
        document.getElementById('network-bar').style.width = `${Math.min(net / 10, 100)}%`;
        // GPU Usage (may be N/A)
        let gpu = (typeof stats.gpu_percent === 'number') ? stats.gpu_percent : null;
        document.getElementById('gpu-val').textContent = (gpu !== null) ? `${gpu}%` : 'N/A';
        document.getElementById('gpu-bar').style.width = (gpu !== null) ? `${gpu}%` : '0%';
        // Temperature (may be N/A)
        let temp = (typeof stats.temperature_c === 'number') ? stats.temperature_c : null;
        document.getElementById('temp-val').textContent = (temp !== null) ? `${temp}°C` : 'N/A';
        document.getElementById('temp-bar').style.width = (temp !== null) ? `${Math.min(temp, 100)}%` : '0%';

    } catch (e) {
        console.warn('System stats fetch failed:', e);
    }
}

function formatUptime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h}h ${m}m ${s}s`;
}

// === CHAT MANAGEMENT SYSTEM ===
// Chat state tracking
const chatState = {
    isProcessing: false,
    currentTimeout: null,
    messageQueue: [],
    queuePosition: 0,
    lastMessageTime: 0,
    messageTimeout: 30000, // 30 seconds
    requestTimeout: 180000, // 180 seconds (backend timeout)
    retryCount: 0,
    maxRetries: 3
};

// Update chat status indicator
function updateChatStatus(status, text, queuePos = null) {
    const indicator = document.getElementById('chat-status-indicator');
    const statusText = document.getElementById('chat-status-text');
    const queueCounter = document.getElementById('chat-queue-counter');
    const feedback = document.getElementById('chat-feedback');
    const healthButton = document.getElementById('chat-health-button');

    if (!indicator) return;

    indicator.setAttribute('data-status', status);
    if (statusText) statusText.textContent = text;

    // Update feedback tone based on status
    if (feedback) {
        switch (status) {
            case 'processing':
                feedback.setAttribute('data-tone', '');
                break;
            case 'waiting':
                feedback.setAttribute('data-tone', 'warning');
                break;
            case 'timeout':
                feedback.setAttribute('data-tone', 'error');
                break;
            case 'idle':
            case 'ready':
                feedback.setAttribute('data-tone', '');
                break;
            default:
                feedback.setAttribute('data-tone', '');
        }
    }

    // Show health check button in error states
    if (healthButton) {
        if (status === 'timeout' || status === 'error') {
            healthButton.style.display = 'inline-block';
        } else {
            healthButton.style.display = 'none';
        }
    }

    if (status === 'idle' || status === 'ready') {
        indicator.classList.remove('active');
        return;
    }

    indicator.classList.add('active');

    if (queuePos !== null && queuePos > 0) {
        if (queueCounter) {
            queueCounter.textContent = `📋 Queue: ${queuePos}`;
            queueCounter.style.display = 'inline-block';
        }
    } else {
        if (queueCounter) queueCounter.style.display = 'none';
    }
}

// Chat mode switching
function toggleChatDropdown() {
    const menu = document.getElementById('chat-dropdown-menu');
    if (!menu) return;
    menu.classList.toggle('show');
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

    // Update active item in dropdown
    const items = document.querySelectorAll('.chat-dropdown-item');
    items.forEach(item => {
        if (item.getAttribute('data-mode') === mode) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Close dropdown
    const menu = document.getElementById('chat-dropdown-menu');
    if (menu) menu.classList.remove('show');

    pushUiAlert(`Chat mode: ${modeText[mode]}`, 'success');
}

// Check backend health/readiness with timeout
async function checkBackendHealth() {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3000); // 3 second health check timeout

        const response = await fetch(`${API_URL}/healthz`, {
            method: 'GET',
            signal: controller.signal
        });

        clearTimeout(timeoutId);
        return response.ok;
    } catch (error) {
        return false;
    }
}

// Calculate exponential backoff delay with jitter
function calculateBackoffDelay(retryCount, maxRetries) {
    // Base delay: 500ms, exponential: 2^retryCount * 500ms, max: 8 seconds
    // Formula: min(500 * 2^retryCount, 8000) + random jitter (0-1000ms)
    const baseDelay = 500;
    const exponentialDelay = Math.min(baseDelay * Math.pow(2, retryCount), 8000);
    const jitter = Math.random() * 1000; // 0-1000ms random jitter
    return Math.floor(exponentialDelay + jitter);
}

// Send chat message with timeout/queue handling
async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const feedback = document.getElementById('chat-feedback');
    if (!input || !feedback) return;

    const message = input.value.trim();
    if (!message) {
        updateChatStatus('idle', 'Enter a message');
        return;
    }

    // Check if already processing
    if (chatState.isProcessing) {
        chatState.messageQueue.push(message);
        chatState.queuePosition = chatState.messageQueue.length;
        updateChatStatus('waiting', `Message queued (${chatState.queuePosition})`, chatState.queuePosition);
        input.value = '';
        feedback.setAttribute('data-tone', 'warning');
        feedback.textContent = `📋 Message queued (${chatState.queuePosition}). Currently processing message...`;
        return;
    }

    // Mark as processing
    chatState.isProcessing = true;
    chatState.lastMessageTime = Date.now();
    input.disabled = true;
    const originalMessage = input.value;
    input.value = '';

    updateChatStatus('processing', 'Sending message...', 0);
    feedback.setAttribute('data-tone', '');
    feedback.textContent = '📤 Processing your message...';

    try {
        // Make the actual chat request with timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), chatState.messageTimeout);

        try {
            const response = await fetch(
                `${API_URL}/v1/chat/${currentChatMode}`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: originalMessage, mode: currentChatMode }),
                    signal: controller.signal
                }
            );

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.text();
                const statusCode = response.status;

                // Handle specific HTTP error codes
                if (statusCode === 503 || statusCode === 502 || statusCode === 504) {
                    throw new Error('SERVICE_UNAVAILABLE');
                } else if (statusCode === 429) {
                    throw new Error('RATE_LIMITED');
                } else if (statusCode === 401 || statusCode === 403) {
                    throw new Error('UNAUTHORIZED');
                } else if (statusCode >= 500) {
                    throw new Error('SERVER_ERROR');
                } else {
                    throw new Error(`HTTP_${statusCode}`);
                }
            }

            const data = await response.json();

            // Success response
            feedback.setAttribute('data-tone', 'success');
            const responseText = data.response || data.result || 'Response received';
            feedback.textContent = `✅ ${responseText.substring(0, 100)}${responseText.length > 100 ? '...' : ''}`;
            updateChatStatus('idle', 'Ready', 0);
            chatState.retryCount = 0;

            console.log('✅ Chat message processed successfully');

        } catch (fetchError) {
            clearTimeout(timeoutId);

            // Network or AbortController errors
            if (fetchError.name === 'AbortError') {
                throw new Error('TIMEOUT');
            } else if (fetchError.message.includes('Failed to fetch') || fetchError.message.includes('NetworkError')) {
                throw new Error('NETWORK_ERROR');
            } else {
                throw fetchError;
            }
        }

    } catch (error) {
        console.error('❌ Chat error:', error.message);

        // Determine error type and provide specific feedback
        let errorType = 'UNKNOWN';
        let userMessage = '';
        let canRetry = true;

        if (error.message === 'TIMEOUT') {
            errorType = 'TIMEOUT';
            userMessage = '⏱️ Request timed out (>30s). The backend may be overloaded. Try a shorter message.';
        } else if (error.message === 'SERVICE_UNAVAILABLE') {
            errorType = 'SERVICE_UNAVAILABLE';
            userMessage = '🔧 Backend service unavailable. Check if Ollama/MCP server is running.';
            canRetry = true;
        } else if (error.message === 'NETWORK_ERROR') {
            errorType = 'NETWORK_ERROR';
            userMessage = '📡 Network error. Check your connection and backend URL.';
            canRetry = true;
        } else if (error.message === 'RATE_LIMITED') {
            errorType = 'RATE_LIMITED';
            userMessage = '⏳ Too many requests. Please wait a moment before trying again.';
            canRetry = false;
        } else if (error.message === 'UNAUTHORIZED') {
            errorType = 'UNAUTHORIZED';
            userMessage = '🔒 Authentication error. Check API keys/permissions.';
            canRetry = false;
        } else if (error.message === 'SERVER_ERROR') {
            errorType = 'SERVER_ERROR';
            userMessage = '❌ Server error. Please check backend logs for details.';
            canRetry = true;
        } else {
            errorType = 'UNKNOWN';
            userMessage = `❌ Error: ${error.message}`;
            canRetry = true;
        }

        // Update UI with error
        feedback.setAttribute('data-tone', 'error');

        // Add retry action if applicable
        if (canRetry && chatState.retryCount < chatState.maxRetries) {
            const retryNum = chatState.retryCount + 1;
            const backoffDelay = calculateBackoffDelay(chatState.retryCount, chatState.maxRetries);
            const delayInSeconds = (backoffDelay / 1000).toFixed(1);

            feedback.innerHTML = `${userMessage} <br><small>🔄 Retrying in ${delayInSeconds}s... (${retryNum}/${chatState.maxRetries})</small>`;
            updateChatStatus('timeout', `${errorType} - Retrying (${retryNum}/${chatState.maxRetries})...`, 0);

            // Store message and retry with exponential backoff
            input.value = originalMessage;
            chatState.retryCount++;

            setTimeout(() => {
                input.value = originalMessage;
                sendChatMessage();
            }, backoffDelay);

            return; // Exit early, don't mark as not processing yet
        } else {
            // No more retries
            if (chatState.retryCount >= chatState.maxRetries) {
                feedback.innerHTML = `${userMessage} <br><small>⚠️ Max retries (${chatState.maxRetries}) reached. Message not sent.</small>`;
            } else {
                feedback.textContent = userMessage;
            }

            updateChatStatus('idle', 'Error', 0);

            // Restore message to input for manual retry
            input.value = originalMessage;

            // Add action button for manual retry
            if (canRetry) {
                const retryBtn = document.createElement('button');
                retryBtn.textContent = ' 🔄 Retry';
                retryBtn.style.marginLeft = '8px';
                retryBtn.style.padding = '2px 8px';
                retryBtn.style.cursor = 'pointer';
                retryBtn.style.fontSize = '0.85em';
                retryBtn.onclick = () => {
                    input.value = originalMessage;
                    chatState.retryCount = 0; // Reset counter for manual retry
                    sendChatMessage();
                };
                feedback.appendChild(retryBtn);
            }
        }

    } finally {
        input.disabled = false;
        input.focus();
        chatState.isProcessing = false;

        // Process next message in queue
        if (chatState.messageQueue.length > 0) {
            const nextMessage = chatState.messageQueue.shift();
            chatState.queuePosition = 0;
            setTimeout(() => {
                document.getElementById('chat-input').value = nextMessage;
                sendChatMessage();
            }, 500);
        } else {
            updateChatStatus('idle', 'Ready', 0);
        }
    }
}

// Clear chat queue
function clearChatQueue() {
    chatState.messageQueue = [];
    chatState.queuePosition = 0;
    updateChatStatus('idle', 'Ready', 0);
    const feedback = document.getElementById('chat-feedback');
    if (feedback) feedback.textContent = 'Queue cleared.';
}

// Check and display backend service status
async function checkAndDisplayServiceStatus() {
    const feedback = document.getElementById('chat-feedback');
    if (!feedback) return;

    feedback.setAttribute('data-tone', 'warning');
    feedback.textContent = '🔍 Checking backend service status...';
    updateChatStatus('processing', 'Checking health...', 0);

    try {
        const isHealthy = await checkBackendHealth();

        if (isHealthy) {
            feedback.setAttribute('data-tone', 'success');
            feedback.textContent = '✅ Backend is healthy and ready for chat.';
            updateChatStatus('idle', 'Ready', 0);
        } else {
            feedback.setAttribute('data-tone', 'error');
            feedback.innerHTML = '❌ Backend not responding. Check if services are running. ' +
                '<button onclick="checkAndDisplayServiceStatus()" style="margin-left: 8px;">🔄 Retry</button>';
            updateChatStatus('idle', 'Service Unavailable', 0);
        }
    } catch (error) {
        feedback.setAttribute('data-tone', 'error');
        feedback.innerHTML = '❌ Failed to check service status: ' + error.message +
            '<button onclick="checkAndDisplayServiceStatus()" style="margin-left: 8px;">🔄 Retry</button>';
        updateChatStatus('idle', 'Check Failed', 0);
    }
}

// Speech recognition functions (placeholder)
function toggleSpeechRecognition() {
    const btn = document.getElementById('mic-button');
    if (!btn) return;

    const isRecording = btn.classList.contains('recording');
    if (isRecording) {
        btn.classList.remove('recording');
        btn.textContent = '🎤';
        const feedback = document.getElementById('chat-feedback');
        if (feedback) feedback.textContent = 'Speech recognition stopped.';
    } else {
        btn.classList.add('recording');
        btn.textContent = '⛔';
        const feedback = document.getElementById('chat-feedback');
        if (feedback) feedback.textContent = 'Listening...';
    }
}

// Wake word functions (placeholder)
function toggleWakeWord() {
    const btn = document.getElementById('wake-toggle-btn');
    if (!btn) return;

    const isActive = btn.classList.contains('active');
    if (isActive) {
        btn.classList.remove('active');
        const status = document.getElementById('wake-status-text');
        if (status) status.textContent = 'Wake';
        const indicator = document.getElementById('wake-word-indicator');
        if (indicator) indicator.classList.remove('active');
    } else {
        btn.classList.add('active');
        const status = document.getElementById('wake-status-text');
        if (status) status.textContent = 'Listening';
        const indicator = document.getElementById('wake-word-indicator');
        if (indicator) indicator.classList.add('active', 'listening');
    }
}

// === DEBATE LOGIC ===
async function triggerDebate() {
    try {
        await fetch(`${ML_BACKEND_URL}/api/debate/simulate`, { method: 'POST' });
        pushUiAlert('Verify Debate in "Intelligence" View', 'success');
    } catch (e) {
        pushUiAlert('Failed to trigger debate', 'error');
    }
}

// Widget Toggle Function
function toggleWidget(widgetName) {
    const panel = document.getElementById(`panel-${widgetName}`);
    const icon = document.getElementById(`widget-${widgetName}`);

    // If clicking the same widget, close it
    if (activeWidget === widgetName) {
        panel.classList.remove('visible');
        icon.classList.remove('active');
        activeWidget = null;
        return;
    }

    // Close any currently open panel
    if (activeWidget) {
        const oldPanel = document.getElementById(`panel-${activeWidget}`);
        const oldIcon = document.getElementById(`widget-${activeWidget}`);
        if (oldPanel) oldPanel.classList.remove('visible');
        if (oldIcon) oldIcon.classList.remove('active');
    }

    // Open the new panel
    panel.classList.add('visible');
    icon.classList.add('active');
    activeWidget = widgetName;

    // Special handling for HNSC panel - render layers
    if (widgetName === 'hnsc') {
        renderHNSCPanel();
    }
}

// Update widget status dots based on service health
function updateWidgetDots() {
    const mcpDot = document.getElementById('mcp-dot');
    const aiDot = document.getElementById('ai-dot');

    if (mcpDot) {
        mcpDot.className = backendOnline ? 'status-dot' : 'status-dot offline';
    }
    if (aiDot) {
        aiDot.className = backendOnline ? 'status-dot' : 'status-dot offline';
    }
}

// Global AI System Panel instance

// === GOVERNANCE PANEL CLASS ===
class GovernancePanel {
    constructor() {
        this.wsManager = null;
        this.roleData = null;
        this.auditData = null;
        this.isInitialized = false;
        this.updateInterval = null;
        this.roleEngineUrl = `${window.location.protocol}//${window.location.hostname}:9206`;
    }

    initialize() {
        if (this.isInitialized) return;

        // Initialize WebSocket manager if not already done
        if (!window.wsManager) {
            window.wsManager = new WebSocketManager();
        }
        this.wsManager = window.wsManager;

        // Connect to governance WebSocket
        this.initializeWebSocket();

        // Set up periodic updates as fallback
        this.setupPeriodicUpdates();

        this.isInitialized = true;
        console.log('🛡️ Governance Panel initialized');
    }

    initializeWebSocket() {
        this.wsManager.connect(
            'governance',
            (data) => this.handleGovernanceUpdate(data),
            (error) => this.handleConnectionError(error)
        );
    }

    handleGovernanceUpdate(data) {
        if (data.type === 'governance_update') {
            this.roleData = data.roles;
            this.auditData = data.audit_logs;
            this.updateDisplay();
            console.log('🛡️ Governance Panel: Data updated via WebSocket');
        }
    }

    handleConnectionError(error) {
        console.warn('🛡️ Governance Panel WebSocket error:', error);
        this.showConnectionError('WebSocket connection failed, using HTTP fallback');
    }

    setupPeriodicUpdates() {
        // Update every 15 seconds as fallback
        this.updateInterval = setInterval(() => {
            if (this.wsManager.getStatus('governance') !== 'connected') {
                this.fetchGovernanceDataHTTP();
            }
        }, 15000);
    }

    async fetchGovernanceDataHTTP() {
        console.log("🛡️ Fetching governance data from", this.roleEngineUrl);

        // Fetch Roles
        try {
            const response = await fetchWithTimeout(`${this.roleEngineUrl}/api/governance/roles`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            }, 8000);

            if (response.ok) {
                const data = await response.json();
                this.roleData = data;
                this.renderRoleTree();
            } else {
                this.showRoleError(`Failed to load roles (Status ${response.status})`);
            }
        } catch (error) {
            console.error("Role fetch error:", error);
            this.showRoleError(`Role Engine unreachable at ${this.roleEngineUrl}. Ensure Aura Role Engine is running on port 9206.`);
        }

        // Fetch Audit Log
        try {
            const response = await fetchWithTimeout(`${this.roleEngineUrl}/api/governance/audit-logs?limit=50`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            }, 8000);

            if (response.ok) {
                const data = await response.json();
                this.auditData = data.events || data;
                this.renderAuditLog();
            } else {
                this.showAuditError('Audit Log Unavailable');
            }
        } catch (error) {
            console.warn("Audit fetch error:", error);
            this.showAuditError('Audit service unreachable');
        }
    }

    updateDisplay() {
        this.renderRoleTree();
        this.renderAuditLog();
    }

    renderRoleTree() {
        const container = document.getElementById('role-tree-container');
        if (!container) return;

        if (!this.roleData) {
            container.innerHTML = `
                <div style="text-align: center; padding: 20px; color: var(--text-secondary);">
                    <div style="font-size: 1.5em; margin-bottom: 8px;">🔄</div>
                    <div>Loading role hierarchy...</div>
                </div>
            `;
            return;
        }

        // Handle different data structures
        let rolesObj = this.roleData.roles || this.roleData;
        let rolesArray = [];

        if (rolesObj && typeof rolesObj === 'object' && !Array.isArray(rolesObj)) {
            rolesArray = Object.keys(rolesObj).map(key => ({
                name: key,
                ...rolesObj[key]
            }));
        } else if (Array.isArray(rolesObj)) {
            rolesArray = rolesObj;
        }

        if (rolesArray.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 20px; color: var(--text-muted);">
                    <div style="font-size: 1.5em; margin-bottom: 8px;">👥</div>
                    <div>No roles configured</div>
                    <button onclick="governancePanel.createDefaultRoles()" style="margin-top: 10px; background: var(--accent-cyan); color: var(--bg-primary); border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer;">Create Default Roles</button>
                </div>
            `;
            return;
        }

        // Sort roles: Admin first, then by name
        const sorted = rolesArray.sort((a, b) => {
            if (a.name === 'Admin') return -1;
            if (b.name === 'Admin') return 1;
            return a.name.localeCompare(b.name);
        });

        let html = '<div class="role-tree">';

        sorted.forEach(role => {
            const color = this.getRoleColor(role.name);
            const icon = this.getRoleIcon(role.name);
            const capabilities = role.capabilities || [];
            const trustLevel = role.trust_level || 'medium';

            html += `
                <div class="role-item" style="margin-bottom: 12px; padding: 12px; background: rgba(255,255,255,0.05); border-radius: 8px; border-left: 4px solid ${color};">
                    <div class="role-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 1.2em;">${icon}</span>
                            <span style="color: ${color}; font-weight: bold; font-size: 1.1em;">${role.name}</span>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <span class="trust-badge" style="font-size: 0.7em; color: var(--text-muted); background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px;">Trust: ${trustLevel}</span>
                            <span class="version-badge" style="font-size: 0.7em; color: var(--text-muted); background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px;">v${role.version || '1.0'}</span>
                        </div>
                    </div>
                    <div class="role-description" style="font-size: 0.9em; color: var(--text-secondary); margin-bottom: 8px; line-height: 1.4;">
                        ${role.purpose || role.description || 'No description available'}
                    </div>
                    ${capabilities.length > 0 ? `
                        <div class="role-capabilities" style="margin-top: 8px;">
                            <div style="font-size: 0.8em; color: var(--text-muted); margin-bottom: 4px;">Capabilities:</div>
                            <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                                ${capabilities.map(cap => `
                                    <span style="font-size: 0.7em; background: rgba(0, 212, 255, 0.2); color: var(--accent-cyan); padding: 2px 6px; border-radius: 3px;">${cap}</span>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            `;
        });

        html += '</div>';
        container.innerHTML = html;
    }

    renderAuditLog() {
        const tbody = document.getElementById('audit-log-body');
        if (!tbody) return;

        if (!this.auditData || this.auditData.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: center; padding: 20px; color: var(--text-muted);">
                        <div style="margin-bottom: 8px;">📋</div>
                        <div>No recent audit events</div>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = this.auditData.slice(0, 20).map(event => {
            const timestamp = event.timestamp || (event.ts ? event.ts * 1000 : Date.now());
            const time = new Date(timestamp).toLocaleTimeString();
            const date = new Date(timestamp).toLocaleDateString();

            const eventType = event.action || event.type || event.event || 'Unknown';
            const actor = event.actor || event.user || event.source || 'System';
            const result = event.result || event.status || 'Success';
            const risk = event.risk_score || event.risk || 0;

            // Determine colors based on event type and risk
            let eventColor = 'var(--success)';
            let resultColor = 'var(--success)';

            if (risk > 0.7 || result.toLowerCase().includes('fail') || result.toLowerCase().includes('error')) {
                eventColor = 'var(--danger)';
                resultColor = 'var(--danger)';
            } else if (risk > 0.4 || result.toLowerCase().includes('warn') || eventType.toLowerCase().includes('warn')) {
                eventColor = 'var(--warning)';
                resultColor = 'var(--warning)';
            }

            return `
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <td style="padding: 8px; color: var(--text-muted); font-family: monospace; font-size: 0.8em;">
                        <div>${time}</div>
                        <div style="font-size: 0.7em; opacity: 0.7;">${date}</div>
                    </td>
                    <td style="padding: 8px; color: var(--text-primary); font-weight: 500;">${actor}</td>
                    <td style="padding: 8px; color: ${eventColor};">${eventType}</td>
                    <td style="padding: 8px; color: ${resultColor}; font-weight: 500;">${result}</td>
                </tr>
            `;
        }).join('');
    }

    getRoleColor(roleName) {
        const colors = {
            'Admin': 'var(--accent-purple)',
            'Operator': 'var(--accent-cyan)',
            'User': 'var(--success)',
            'Guest': 'var(--text-secondary)'
        };
        return colors[roleName] || 'var(--text-secondary)';
    }

    getRoleIcon(roleName) {
        const icons = {
            'Admin': '👑',
            'Operator': '⚡',
            'User': '👤',
            'Guest': '👥',
            'System': '🤖'
        };
        return icons[roleName] || '👤';
    }

    showRoleError(message) {
        const container = document.getElementById('role-tree-container');
        if (container) {
            container.innerHTML = `
                <div style="text-align: center; padding: 20px; color: var(--danger);">
                    <div style="font-size: 1.5em; margin-bottom: 8px;">⚠️</div>
                    <div style="margin-bottom: 12px;">${message}</div>
                    <button onclick="governancePanel.retry()" style="background: var(--danger); color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer;">Retry</button>
                </div>
            `;
        }
    }

    showAuditError(message) {
        const tbody = document.getElementById('audit-log-body');
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: center; padding: 20px; color: var(--warning);">
                        <div style="margin-bottom: 8px;">⚠️</div>
                        <div>${message}</div>
                    </td>
                </tr>
            `;
        }
    }

    showConnectionError(message) {
        console.warn('🛡️ Governance Panel:', message);
        // Could add a connection status indicator here
    }

    async createDefaultRoles() {
        try {
            const response = await fetch(`${this.roleEngineUrl}/api/governance/roles/create-defaults`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (response.ok) {
                console.log('✅ Default roles created');
                setTimeout(() => this.fetchGovernanceDataHTTP(), 1000);
            } else {
                console.error('❌ Failed to create default roles');
            }
        } catch (error) {
            console.error('❌ Error creating default roles:', error);
        }
    }

    async refreshData() {
        console.log('🔄 Refreshing governance data...');
        await this.fetchGovernanceDataHTTP();
    }

    retry() {
        console.log('🔄 Retrying Governance Panel connection...');
        this.initializeWebSocket();
        this.fetchGovernanceDataHTTP();
    }

    destroy() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        if (this.wsManager) {
            this.wsManager.disconnect('governance');
        }
        this.isInitialized = false;
    }
}

// Global Governance Panel instance

// === INTELLIGENCE ARENA PANEL CLASS ===
class IntelligenceArenaPanel {
    constructor() {
        this.wsManager = null;
        this.modelStats = null;
        this.debateData = null;
        this.isInitialized = false;
        this.updateInterval = null;
        this.currentDebateId = null;
    }

    initialize() {
        if (this.isInitialized) return;

        // Initialize WebSocket manager if not already done
        if (!window.wsManager) {
            window.wsManager = new WebSocketManager();
        }
        this.wsManager = window.wsManager;

        // Connect to debates WebSocket
        this.initializeWebSocket();

        // Set up periodic updates as fallback
        this.setupPeriodicUpdates();

        // Load initial data
        this.fetchModelStatistics();

        this.isInitialized = true;
        console.log('🧠 Intelligence Arena Panel initialized');
    }

    initializeWebSocket() {
        this.wsManager.connect(
            'debates',
            (data) => this.handleDebateUpdate(data),
            (error) => this.handleConnectionError(error)
        );
    }

    handleDebateUpdate(data) {
        if (data.type === 'debate_update') {
            this.debateData = data;
            this.updateDebateDisplay();
            console.log('🧠 Intelligence Arena: Debate data updated via WebSocket');
        } else if (data.type === 'model_stats_update') {
            this.modelStats = data.stats;
            this.updateModelStatistics();
            console.log('🧠 Intelligence Arena: Model stats updated via WebSocket');
        }
    }

    handleConnectionError(error) {
        console.warn('🧠 Intelligence Arena WebSocket error:', error);
        this.showConnectionError('WebSocket connection failed, using HTTP fallback');
    }

    setupPeriodicUpdates() {
        // Update every 30 seconds as fallback
        this.updateInterval = setInterval(() => {
            if (this.wsManager.getStatus('debates') !== 'connected') {
                this.fetchModelStatistics();
            }
        }, 30000);
    }

    async fetchModelStatistics() {
        try {
            // Fetch model statistics from debate leaderboard
            const response = await fetchWithTimeout(`http://${SERVER_HOST}:9200/v1/debate/leaderboard`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            }, 8000);

            if (response.ok) {
                const data = await response.json();
                this.modelStats = data;
                this.updateModelStatistics();
            } else {
                this.showStatsError('Failed to load model statistics');
            }
        } catch (error) {
            console.error('Model statistics fetch error:', error);
            this.showStatsError('Statistics service unavailable');
        }
    }

    async fetchDebateHistory() {
        try {
            const response = await fetchWithTimeout(`http://${SERVER_HOST}:9200/v1/debate/history?limit=10`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            }, 8000);

            if (response.ok) {
                const data = await response.json();
                this.updateDebateHistory(data.debates || []);
            }
        } catch (error) {
            console.error('Debate history fetch error:', error);
        }
    }

    updateModelStatistics() {
        const container = document.getElementById('model-statistics-container');
        if (!container) return;

        if (!this.modelStats || this.modelStats.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 40px; color: var(--text-secondary);">
                    <div style="font-size: 2em; margin-bottom: 10px;">🤖</div>
                    <div style="margin-bottom: 10px;">No model statistics available</div>
                    <button onclick="intelligenceArena.loadAllModels()" style="background: var(--accent-cyan); color: var(--bg-primary); border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">Load All Models</button>
                </div>
            `;
            return;
        }

        // Sort models by ELO rating or win rate
        const sortedModels = [...this.modelStats].sort((a, b) => (b.elo_rating || b.win_rate || 0) - (a.elo_rating || a.win_rate || 0));

        let html = '<div class="model-stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 15px;">';

        sortedModels.forEach((model, index) => {
            const winRate = ((model.wins || 0) / Math.max(model.total_debates || 1, 1) * 100).toFixed(1);
            const eloRating = model.elo_rating || 1200;
            const rankColor = index === 0 ? 'var(--accent-cyan)' : index === 1 ? 'var(--success)' : 'var(--text-secondary)';
            const rankIcon = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : '🤖';

            html += `
                <div class="model-stat-card" style="background: rgba(0, 212, 255, 0.1); border: 1px solid ${rankColor}; border-radius: 12px; padding: 16px; position: relative;">
                    <div class="model-rank" style="position: absolute; top: -8px; right: -8px; background: ${rankColor}; color: var(--bg-primary); width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.8em; font-weight: bold;">
                        ${index + 1}
                    </div>
                    <div class="model-header" style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
                        <span style="font-size: 1.5em;">${rankIcon}</span>
                        <div>
                            <h4 style="color: ${rankColor}; margin: 0; font-size: 1em;">${model.model_name || model.name || 'Unknown'}</h4>
                            <div style="font-size: 0.8em; color: var(--text-secondary);">ELO: ${eloRating}</div>
                        </div>
                    </div>
                    <div class="model-stats" style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.85em;">
                        <div class="stat">
                            <div style="color: var(--text-secondary);">Win Rate</div>
                            <div style="color: var(--success); font-weight: bold; font-size: 1.1em;">${winRate}%</div>
                        </div>
                        <div class="stat">
                            <div style="color: var(--text-secondary);">Debates</div>
                            <div style="color: var(--text-primary); font-weight: bold;">${model.total_debates || 0}</div>
                        </div>
                        <div class="stat">
                            <div style="color: var(--text-secondary);">Wins</div>
                            <div style="color: var(--success);">${model.wins || 0}</div>
                        </div>
                        <div class="stat">
                            <div style="color: var(--text-secondary);">Losses</div>
                            <div style="color: var(--danger);">${model.losses || 0}</div>
                        </div>
                    </div>
                    <div class="model-actions" style="margin-top: 12px; display: flex; gap: 6px;">
                        <button onclick="intelligenceArena.viewModelHistory('${model.model_name || model.name}')" style="flex: 1; background: transparent; border: 1px solid ${rankColor}; color: ${rankColor}; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 0.8em;">History</button>
                        <button onclick="intelligenceArena.challengeModel('${model.model_name || model.name}')" style="flex: 1; background: ${rankColor}; color: var(--bg-primary); border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 0.8em;">Challenge</button>
                    </div>
                </div>
            `;
        });

        html += '</div>';

        // Add summary statistics
        const totalDebates = sortedModels.reduce((sum, model) => sum + (model.total_debates || 0), 0);
        const avgWinRate = sortedModels.reduce((sum, model) => {
            const winRate = (model.wins || 0) / Math.max(model.total_debates || 1, 1);
            return sum + winRate;
        }, 0) / Math.max(sortedModels.length, 1) * 100;

        html += `
            <div class="arena-summary" style="margin-top: 20px; padding: 16px; background: rgba(0,0,0,0.3); border-radius: 8px; display: flex; justify-content: space-around; text-align: center;">
                <div>
                    <div style="color: var(--accent-cyan); font-size: 1.2em; font-weight: bold;">${sortedModels.length}</div>
                    <div style="color: var(--text-secondary); font-size: 0.8em;">Active Models</div>
                </div>
                <div>
                    <div style="color: var(--accent-cyan); font-size: 1.2em; font-weight: bold;">${totalDebates}</div>
                    <div style="color: var(--text-secondary); font-size: 0.8em;">Total Debates</div>
                </div>
                <div>
                    <div style="color: var(--accent-cyan); font-size: 1.2em; font-weight: bold;">${avgWinRate.toFixed(1)}%</div>
                    <div style="color: var(--text-secondary); font-size: 0.8em;">Avg Win Rate</div>
                </div>
            </div>
        `;

        container.innerHTML = html;
    }

    updateDebateDisplay() {
        // Update live debate display if there's an active debate
        if (this.debateData && this.debateData.debate_id) {
            this.updateDebateCards(this.debateData);
        }
    }

    updateDebateCards(debateData) {
        // Update Model A card
        const cardA = document.getElementById('debate-text-a');
        if (cardA && debateData.model_a_response) {
            cardA.innerHTML = debateData.model_a_response;
            cardA.parentElement.style.borderTopColor = 'var(--accent-cyan)';
        }

        // Update Model B card
        const cardB = document.getElementById('debate-text-b');
        if (cardB && debateData.model_b_response) {
            cardB.innerHTML = debateData.model_b_response;
            cardB.parentElement.style.borderTopColor = 'var(--danger)';
        }

        // Update Judge card
        const cardJudge = document.getElementById('debate-text-judge');
        if (cardJudge && debateData.judge_verdict) {
            cardJudge.innerHTML = debateData.judge_verdict;
            cardJudge.parentElement.style.borderTopColor = 'var(--accent-purple)';
        }

        // Update debate status
        const statusElement = document.getElementById('debate-status');
        if (statusElement) {
            statusElement.textContent = debateData.status || 'ACTIVE';
            statusElement.className = `status-badge ${debateData.status === 'completed' ? 'status-offline' : 'status-online'}`;
        }
    }

    updateDebateHistory(debates) {
        const container = document.getElementById('debate-history-container');
        if (!container) return;

        if (debates.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 20px; color: var(--text-secondary);">
                    <div style="font-size: 1.5em; margin-bottom: 8px;">📜</div>
                    <div>No debate history available</div>
                </div>
            `;
            return;
        }

        const historyHtml = debates.map(debate => {
            const date = new Date(debate.timestamp || debate.created_at).toLocaleDateString();
            const time = new Date(debate.timestamp || debate.created_at).toLocaleTimeString();
            const winner = debate.winner || 'Draw';
            const winnerColor = winner === 'Model A' ? 'var(--accent-cyan)' :
                winner === 'Model B' ? 'var(--danger)' : 'var(--text-secondary)';

            return `
                <div class="debate-history-item" style="padding: 12px; margin-bottom: 8px; background: rgba(255,255,255,0.05); border-radius: 8px; border-left: 3px solid ${winnerColor};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <div style="font-weight: bold; color: var(--text-primary);">${debate.topic || 'Unknown Topic'}</div>
                        <div style="font-size: 0.8em; color: var(--text-secondary);">${date} ${time}</div>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.9em;">
                        <div style="color: var(--text-secondary);">
                            ${debate.model_a || 'Model A'} vs ${debate.model_b || 'Model B'}
                        </div>
                        <div style="color: ${winnerColor}; font-weight: bold;">Winner: ${winner}</div>
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = historyHtml;
    }

    showStatsError(message) {
        const container = document.getElementById('model-statistics-container');
        if (container) {
            container.innerHTML = `
                <div style="text-align: center; padding: 40px; color: var(--danger);">
                    <div style="font-size: 2em; margin-bottom: 10px;">⚠️</div>
                    <div style="margin-bottom: 12px;">${message}</div>
                    <button onclick="intelligenceArena.retry()" style="background: var(--danger); color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">Retry</button>
                </div>
            `;
        }
    }

    showConnectionError(message) {
        console.warn('🧠 Intelligence Arena:', message);
    }

    async loadAllModels() {
        try {
            const models = ['phi3.5:3.8b', 'llama3.1:8b', 'qwen2.5-coder:7b', 'deepseek-r1:8b'];

            for (const model of models) {
                const response = await fetch(`http://${SERVER_HOST}:9200/v1/models/${model}/load`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                if (response.ok) {
                    console.log(`✅ Model ${model} loading initiated`);
                } else {
                    console.warn(`⚠️ Failed to load model ${model}`);
                }
            }

            // Refresh statistics after a delay
            setTimeout(() => this.fetchModelStatistics(), 5000);

        } catch (error) {
            console.error('❌ Error loading models:', error);
        }
    }

    async startDebate() {
        try {
            const response = await fetch(`http://${SERVER_HOST}:9200/v1/debate/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model_a: 'phi3.5:3.8b',
                    model_b: 'llama3.1:8b',
                    topic: 'The future of artificial intelligence'
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.currentDebateId = data.debate_id;
                console.log('✅ Debate started:', data.debate_id);
            } else {
                console.error('❌ Failed to start debate');
            }
        } catch (error) {
            console.error('❌ Error starting debate:', error);
        }
    }

    async viewModelHistory(modelName) {
        console.log(`📊 Viewing history for ${modelName}`);
        // Could open a modal or navigate to detailed view
    }

    async challengeModel(modelName) {
        console.log(`⚔️ Challenging ${modelName}`);
        // Could start a specific debate against this model
    }

    async refreshData() {
        console.log('🔄 Refreshing Intelligence Arena data...');
        await this.fetchModelStatistics();
        await this.fetchDebateHistory();
    }

    retry() {
        console.log('🔄 Retrying Intelligence Arena connection...');
        this.initializeWebSocket();
        this.fetchModelStatistics();
    }

    destroy() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        if (this.wsManager) {
            this.wsManager.disconnect('debates');
        }
        this.isInitialized = false;
    }
}

// Global Intelligence Arena Panel instance

// === SYSTEM MONITOR REAL-TIME LOGIC ===
function updateMonitorUI(stats) {
    if (!stats) return;
    // Update Metrics
    document.getElementById('monitor-uptime').textContent = formatUptime(stats.uptime_seconds || 0);
    document.getElementById('monitor-rps').textContent = `${stats.requests_total || 0} total`;
    const errRate = stats.requests_total > 0 ? ((stats.error_count / stats.requests_total) * 100).toFixed(1) : "0.0";
    document.getElementById('monitor-errors').textContent = `${errRate}%`;
    // Update Bars
    const cpu = stats.cpu_percent || 0;
    document.getElementById('cpu-val').textContent = `${cpu}%`;
    document.getElementById('cpu-bar').style.width = `${cpu}%`;
    const mem = stats.memory_mb || 0;
    document.getElementById('mem-val').textContent = `${mem} MB`;
    document.getElementById('mem-bar').style.width = `${Math.min(mem / 10, 100)}%`;
    // Disk Usage
    const disk = stats.disk_percent || 0;
    document.getElementById('disk-val').textContent = `${disk}%`;
    document.getElementById('disk-bar').style.width = `${disk}%`;
    // Network Usage (show as KB/s or MB/s)
    let net = stats.network_kbps || 0;
    let netDisplay = net > 1024 ? `${(net / 1024).toFixed(1)} MB/s` : `${net.toFixed(1)} KB/s`;
    document.getElementById('network-val').textContent = netDisplay;
    document.getElementById('network-bar').style.width = `${Math.min(net / 10, 100)}%`;
    // GPU Usage (may be N/A)
    let gpu = (typeof stats.gpu_percent === 'number') ? stats.gpu_percent : null;
    document.getElementById('gpu-val').textContent = (gpu !== null) ? `${gpu}%` : 'N/A';
    document.getElementById('gpu-bar').style.width = (gpu !== null) ? `${gpu}%` : '0%';
    // Temperature (may be N/A)
    let temp = (typeof stats.temperature_c === 'number') ? stats.temperature_c : null;
    document.getElementById('temp-val').textContent = (temp !== null) ? `${temp}°C` : 'N/A';
    document.getElementById('temp-bar').style.width = (temp !== null) ? `${Math.min(temp, 100)}%` : '0%';
}

// --- Performance Graphs and Threshold Alerts ---
// Store history for each metric (last 30 points)

// Keep a short history for sparkline rendering
const monitorHistory = { cpu: [], mem: [], disk: [], network: [], gpu: [], temp: [] };

function pushHistory(arr, val) {
    arr.push(val);
    if (arr.length > 30) arr.shift();
}

function renderSparkline(canvasId, data, color) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !data.length) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    const max = Math.max(...data, 100);
    const min = Math.min(...data, 0);
    for (let i = 0; i < data.length; i++) {
        const x = (i / (data.length - 1)) * canvas.width;
        const y = canvas.height - ((data[i] - min) / (max - min)) * canvas.height;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.stroke();
}

function setThresholdColor(val, warn, crit, el) {
    if (!el) return;
    el.style.color = '';
    if (val >= crit) el.style.color = 'var(--danger)';
    else if (val >= warn) el.style.color = 'var(--warning)';
    else el.style.color = '';
}

// Patch updateMonitorUI to add history, sparklines, and alerts
const oldUpdateMonitorUI = updateMonitorUI;
updateMonitorUI = function (stats) {
    if (!stats) return;
    // History
    pushHistory(monitorHistory.cpu, stats.cpu_percent || 0);
    pushHistory(monitorHistory.mem, stats.memory_mb || 0);
    pushHistory(monitorHistory.disk, stats.disk_percent || 0);
    pushHistory(monitorHistory.network, stats.network_kbps || 0);
    pushHistory(monitorHistory.gpu, typeof stats.gpu_percent === 'number' ? stats.gpu_percent : 0);
    pushHistory(monitorHistory.temp, typeof stats.temperature_c === 'number' ? stats.temperature_c : 0);
    // Call original
    oldUpdateMonitorUI(stats);
    // Render sparklines
    renderSparkline('cpu-spark', monitorHistory.cpu, '#00d4ff');
    renderSparkline('mem-spark', monitorHistory.mem, '#a259ff');
    renderSparkline('disk-spark', monitorHistory.disk, '#00ffff');
    renderSparkline('network-spark', monitorHistory.network, '#00ff00');
    renderSparkline('gpu-spark', monitorHistory.gpu, '#ff0044');
    renderSparkline('temp-spark', monitorHistory.temp, '#ffaa00');
    // Threshold alerts
    setThresholdColor(stats.cpu_percent, 70, 90, document.getElementById('cpu-val'));
    setThresholdColor(stats.memory_mb, 12000, 16000, document.getElementById('mem-val'));
    setThresholdColor(stats.disk_percent, 80, 95, document.getElementById('disk-val'));
    setThresholdColor(stats.network_kbps, 5000, 20000, document.getElementById('network-val'));
    setThresholdColor(stats.gpu_percent, 80, 95, document.getElementById('gpu-val'));
    setThresholdColor(stats.temperature_c, 70, 85, document.getElementById('temp-val'));
}

// === DEBATE LOGIC ===
async function triggerDebate() {
    try {
        await fetch(`${ML_BACKEND_URL}/api/debate/simulate`, { method: 'POST' });
        pushUiAlert('Verify Debate in "Intelligence" View', 'success');
    } catch (e) {
        pushUiAlert('Failed to trigger debate', 'error');
    }
}

// Widget Toggle Function
function toggleWidget(widgetName) {
    const panel = document.getElementById(`panel-${widgetName}`);
    const icon = document.getElementById(`widget-${widgetName}`);

    // If clicking the same widget, close it
    if (activeWidget === widgetName) {
        panel.classList.remove('visible');
        icon.classList.remove('active');
        activeWidget = null;
        return;
    }

    // Close any currently open panel
    if (activeWidget) {
        const oldPanel = document.getElementById(`panel-${activeWidget}`);
        const oldIcon = document.getElementById(`widget-${activeWidget}`);
        if (oldPanel) oldPanel.classList.remove('visible');
        if (oldIcon) oldIcon.classList.remove('active');
    }

    // Open the new panel
    panel.classList.add('visible');
    icon.classList.add('active');
    activeWidget = widgetName;

    // Special handling for HNSC panel - render layers
    if (widgetName === 'hnsc') {
        renderHNSCPanel();
    }
}

// Update widget status dots based on service health
function updateWidgetDots() {
    const mcpDot = document.getElementById('mcp-dot');
    const aiDot = document.getElementById('ai-dot');

    if (mcpDot) {
        mcpDot.className = backendOnline ? 'status-dot' : 'status-dot offline';
    }
    if (aiDot) {
        aiDot.className = backendOnline ? 'status-dot' : 'status-dot offline';
    }
}

// Global AI System Panel instance

// === GOVERNANCE PANEL CLASS ===
class GovernancePanel {
    constructor() {
        this.wsManager = null;
        this.roleData = null;
        this.auditData = null;
        this.isInitialized = false;
        this.updateInterval = null;
        this.roleEngineUrl = `${window.location.protocol}//${window.location.hostname}:9206`;
    }

    initialize() {
        if (this.isInitialized) return;

        // Initialize WebSocket manager if not already done
        if (!window.wsManager) {
            window.wsManager = new WebSocketManager();
        }
        this.wsManager = window.wsManager;

        // Connect to governance WebSocket
        this.initializeWebSocket();

        // Set up periodic updates as fallback
        this.setupPeriodicUpdates();

        this.isInitialized = true;
        console.log('🛡️ Governance Panel initialized');
    }

    initializeWebSocket() {
        this.wsManager.connect(
            'governance',
            (data) => this.handleGovernanceUpdate(data),
            (error) => this.handleConnectionError(error)
        );
    }

    handleGovernanceUpdate(data) {
        if (data.type === 'governance_update') {
            this.roleData = data.roles;
            this.auditData = data.audit_logs;
            this.updateDisplay();
            console.log('🛡️ Governance Panel: Data updated via WebSocket');
        }
    }

    handleConnectionError(error) {
        console.warn('🛡️ Governance Panel WebSocket error:', error);
        this.showConnectionError('WebSocket connection failed, using HTTP fallback');
    }

    setupPeriodicUpdates() {
        // Update every 15 seconds as fallback
        this.updateInterval = setInterval(() => {
            if (this.wsManager.getStatus('governance') !== 'connected') {
                this.fetchGovernanceDataHTTP();
            }
        }, 15000);
    }

    async fetchGovernanceDataHTTP() {
        console.log("🛡️ Fetching governance data from", this.roleEngineUrl);

        // Fetch Roles
        try {
            const response = await fetchWithTimeout(`${this.roleEngineUrl}/api/governance/roles`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            }, 8000);

            if (response.ok) {
                const data = await response.json();
                this.roleData = data;
                this.renderRoleTree();
            } else {
                this.showRoleError(`Failed to load roles (Status ${response.status})`);
            }
        } catch (error) {
            console.error("Role fetch error:", error);
            this.showRoleError(`Role Engine unreachable at ${this.roleEngineUrl}. Ensure Aura Role Engine is running on port 9206.`);
        }

        // Fetch Audit Log
        try {
            const response = await fetchWithTimeout(`${this.roleEngineUrl}/api/governance/audit-logs?limit=50`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            }, 8000);

            if (response.ok) {
                const data = await response.json();
                this.auditData = data.events || data;
                this.renderAuditLog();
            } else {
                this.showAuditError('Audit Log Unavailable');
            }
        } catch (error) {
            console.warn("Audit fetch error:", error);
            this.showAuditError('Audit service unreachable');
        }
    }

    updateDisplay() {
        this.renderRoleTree();
        this.renderAuditLog();
    }

    renderRoleTree() {
        const container = document.getElementById('role-tree-container');
        if (!container) return;

        if (!this.roleData) {
            container.innerHTML = `
                <div style="text-align: center; padding: 20px; color: var(--text-secondary);">
                    <div style="font-size: 1.5em; margin-bottom: 8px;">🔄</div>
                    <div>Loading role hierarchy...</div>
                </div>
            `;
            return;
        }

        // Handle different data structures
        let rolesObj = this.roleData.roles || this.roleData;
        let rolesArray = [];

        if (rolesObj && typeof rolesObj === 'object' && !Array.isArray(rolesObj)) {
            rolesArray = Object.keys(rolesObj).map(key => ({
                name: key,
                ...rolesObj[key]
            }));
        } else if (Array.isArray(rolesObj)) {
            rolesArray = rolesObj;
        }

        if (rolesArray.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 20px; color: var(--text-muted);">
                    <div style="font-size: 1.5em; margin-bottom: 8px;">👥</div>
                    <div>No roles configured</div>
                    <button onclick="governancePanel.createDefaultRoles()" style="margin-top: 10px; background: var(--accent-cyan); color: var(--bg-primary); border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer;">Create Default Roles</button>
                </div>
            `;
            return;
        }

        // Sort roles: Admin first, then by name
        const sorted = rolesArray.sort((a, b) => {
            if (a.name === 'Admin') return -1;
            if (b.name === 'Admin') return 1;
            return a.name.localeCompare(b.name);
        });

        let html = '<div class="role-tree">';

        sorted.forEach(role => {
            const color = this.getRoleColor(role.name);
            const icon = this.getRoleIcon(role.name);
            const capabilities = role.capabilities || [];
            const trustLevel = role.trust_level || 'medium';

            html += `
                <div class="role-item" style="margin-bottom: 12px; padding: 12px; background: rgba(255,255,255,0.05); border-radius: 8px; border-left: 4px solid ${color};">
                    <div class="role-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 1.2em;">${icon}</span>
                            <span style="color: ${color}; font-weight: bold; font-size: 1.1em;">${role.name}</span>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <span class="trust-badge" style="font-size: 0.7em; color: var(--text-muted); background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px;">Trust: ${trustLevel}</span>
                            <span class="version-badge" style="font-size: 0.7em; color: var(--text-muted); background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px;">v${role.version || '1.0'}</span>
                        </div>
                    </div>
                    <div class="role-description" style="font-size: 0.9em; color: var(--text-secondary); margin-bottom: 8px; line-height: 1.4;">
                        ${role.purpose || role.description || 'No description available'}
                    </div>
                    ${capabilities.length > 0 ? `
                        <div class="role-capabilities" style="margin-top: 8px;">
                            <div style="font-size: 0.8em; color: var(--text-muted); margin-bottom: 4px;">Capabilities:</div>
                            <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                                ${capabilities.map(cap => `
                                    <span style="font-size: 0.7em; background: rgba(0, 212, 255, 0.2); color: var(--accent-cyan); padding: 2px 6px; border-radius: 3px;">${cap}</span>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            `;
        });

        html += '</div>';
        container.innerHTML = html;
    }

    renderAuditLog() {
        const tbody = document.getElementById('audit-log-body');
        if (!tbody) return;

        if (!this.auditData || this.auditData.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: center; padding: 20px; color: var(--text-muted);">
                        <div style="margin-bottom: 8px;">📋</div>
                        <div>No recent audit events</div>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = this.auditData.slice(0, 20).map(event => {
            const timestamp = event.timestamp || (event.ts ? event.ts * 1000 : Date.now());
            const time = new Date(timestamp).toLocaleTimeString();
            const date = new Date(timestamp).toLocaleDateString();

            const eventType = event.action || event.type || event.event || 'Unknown';
            const actor = event.actor || event.user || event.source || 'System';
            const result = event.result || event.status || 'Success';
            const risk = event.risk_score || event.risk || 0;

            // Determine colors based on event type and risk
            let eventColor = 'var(--success)';
            let resultColor = 'var(--success)';

            if (risk > 0.7 || result.toLowerCase().includes('fail') || result.toLowerCase().includes('error')) {
                eventColor = 'var(--danger)';
                resultColor = 'var(--danger)';
            } else if (risk > 0.4 || result.toLowerCase().includes('warn') || eventType.toLowerCase().includes('warn')) {
                eventColor = 'var(--warning)';
                resultColor = 'var(--warning)';
            }

            return `
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <td style="padding: 8px; color: var(--text-muted); font-family: monospace; font-size: 0.8em;">
                        <div>${time}</div>
                        <div style="font-size: 0.7em; opacity: 0.7;">${date}</div>
                    </td>
                    <td style="padding: 8px; color: var(--text-primary); font-weight: 500;">${actor}</td>
                    <td style="padding: 8px; color: ${eventColor};">${eventType}</td>
                    <td style="padding: 8px; color: ${resultColor}; font-weight: 500;">${result}</td>
                </tr>
            `;
        }).join('');
    }

    getRoleColor(roleName) {
        const colors = {
            'Admin': 'var(--accent-purple)',
            'Operator': 'var(--accent-cyan)',
            'User': 'var(--success)',
            'Guest': 'var(--text-secondary)'
        };
        return colors[roleName] || 'var(--text-secondary)';
    }

    getRoleIcon(roleName) {
        const icons = {
            'Admin': '👑',
            'Operator': '⚡',
            'User': '👤',
            'Guest': '👥',
            'System': '🤖'
        };
        return icons[roleName] || '👤';
    }

    showRoleError(message) {
        const container = document.getElementById('role-tree-container');
        if (container) {
            container.innerHTML = `
                <div style="text-align: center; padding: 20px; color: var(--danger);">
                    <div style="font-size: 1.5em; margin-bottom: 8px;">⚠️</div>
                    <div style="margin-bottom: 12px;">${message}</div>
                    <button onclick="governancePanel.retry()" style="background: var(--danger); color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer;">Retry</button>
                </div>
            `;
        }
    }

    showAuditError(message) {
        const tbody = document.getElementById('audit-log-body');
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: center; padding: 20px; color: var(--warning);">
                        <div style="margin-bottom: 8px;">⚠️</div>
                        <div>${message}</div>
                    </td>
                </tr>
            `;
        }
    }

    showConnectionError(message) {
        console.warn('🛡️ Governance Panel:', message);
        // Could add a connection status indicator here
    }

    async createDefaultRoles() {
        try {
            const response = await fetch(`${this.roleEngineUrl}/api/governance/roles/create-defaults`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (response.ok) {
                console.log('✅ Default roles created');
                setTimeout(() => this.fetchGovernanceDataHTTP(), 1000);
            } else {
                console.error('❌ Failed to create default roles');
            }
        } catch (error) {
            console.error('❌ Error creating default roles:', error);
        }
    }

    async refreshData() {
        console.log('🔄 Refreshing governance data...');
        await this.fetchGovernanceDataHTTP();
    }

    retry() {
        console.log('🔄 Retrying Governance Panel connection...');
        this.initializeWebSocket();
        this.fetchGovernanceDataHTTP();
    }

    destroy() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        if (this.wsManager) {
            this.wsManager.disconnect('governance');
        }
        this.isInitialized = false;
    }
}

// Global Governance Panel instance

// === INTELLIGENCE ARENA PANEL CLASS ===
class IntelligenceArenaPanel {
    constructor() {
        this.wsManager = null;
        this.modelStats = null;
        this.debateData = null;
        this.isInitialized = false;
        this.updateInterval = null;
        this.currentDebateId = null;
    }

    initialize() {
        if (this.isInitialized) return;

        // Initialize WebSocket manager if not already done
        if (!window.wsManager) {
            window.wsManager = new WebSocketManager();
        }
        this.wsManager = window.wsManager;

        // Connect to debates WebSocket
        this.initializeWebSocket();

        // Set up periodic updates as fallback
        this.setupPeriodicUpdates();

        // Load initial data
        this.fetchModelStatistics();

        this.isInitialized = true;
        console.log('🧠 Intelligence Arena Panel initialized');
    }

    initializeWebSocket() {
        this.wsManager.connect(
            'debates',
            (data) => this.handleDebateUpdate(data),
            (error) => this.handleConnectionError(error)
        );
    }

    handleDebateUpdate(data) {
        if (data.type === 'debate_update') {
            this.debateData = data;
            this.updateDebateDisplay();
            console.log('🧠 Intelligence Arena: Debate data updated via WebSocket');
        } else if (data.type === 'model_stats_update') {
            this.modelStats = data.stats;
            this.updateModelStatistics();
            console.log('🧠 Intelligence Arena: Model stats updated via WebSocket');
        }
    }

    handleConnectionError(error) {
        console.warn('🧠 Intelligence Arena WebSocket error:', error);
        this.showConnectionError('WebSocket connection failed, using HTTP fallback');
    }

    setupPeriodicUpdates() {
        // Update every 30 seconds as fallback
        this.updateInterval = setInterval(() => {
            if (this.wsManager.getStatus('debates') !== 'connected') {
                this.fetchModelStatistics();
            }
        }, 30000);
    }

    async fetchModelStatistics() {
        try {
            // Fetch model statistics from debate leaderboard
            const response = await fetchWithTimeout(`http://${SERVER_HOST}:9200/v1/debate/leaderboard`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            }, 8000);

            if (response.ok) {
                const data = await response.json();
                this.modelStats = data;
                this.updateModelStatistics();
            } else {
                this.showStatsError('Failed to load model statistics');
            }
        } catch (error) {
            console.error('Model statistics fetch error:', error);
            this.showStatsError('Statistics service unavailable');
        }
    }

    async fetchDebateHistory() {
        try {
            const response = await fetchWithTimeout(`http://${SERVER_HOST}:9200/v1/debate/history?limit=10`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            }, 8000);

            if (response.ok) {
                const data = await response.json();
                this.updateDebateHistory(data.debates || []);
            }
        } catch (error) {
            console.error('Debate history fetch error:', error);
        }
    }

    updateModelStatistics() {
        const container = document.getElementById('model-statistics-container');
        if (!container) return;

        if (!this.modelStats || this.modelStats.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 40px; color: var(--text-secondary);">
                    <div style="font-size: 2em; margin-bottom: 10px;">🤖</div>
                    <div style="margin-bottom: 10px;">No model statistics available</div>
                    <button onclick="intelligenceArena.loadAllModels()" style="background: var(--accent-cyan); color: var(--bg-primary); border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">Load All Models</button>
                </div>
            `;
            return;
        }

        // Sort models by ELO rating or win rate
        const sortedModels = [...this.modelStats].sort((a, b) => (b.elo_rating || b.win_rate || 0) - (a.elo_rating || a.win_rate || 0));

        let html = '<div class="model-stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 15px;">';

        sortedModels.forEach((model, index) => {
            const winRate = ((model.wins || 0) / Math.max(model.total_debates || 1, 1) * 100).toFixed(1);
            const eloRating = model.elo_rating || 1200;
            const rankColor = index === 0 ? 'var(--accent-cyan)' : index === 1 ? 'var(--success)' : 'var(--text-secondary)';
            const rankIcon = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : '🤖';

            html += `
                <div class="model-stat-card" style="background: rgba(0, 212, 255, 0.1); border: 1px solid ${rankColor}; border-radius: 12px; padding: 16px; position: relative;">
                    <div class="model-rank" style="position: absolute; top: -8px; right: -8px; background: ${rankColor}; color: var(--bg-primary); width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.8em; font-weight: bold;">
                        ${index + 1}
                    </div>
                    <div class="model-header" style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
                        <span style="font-size: 1.5em;">${rankIcon}</span>
                        <div>
                            <h4 style="color: ${rankColor}; margin: 0; font-size: 1em;">${model.model_name || model.name || 'Unknown'}</h4>
                            <div style="font-size: 0.8em; color: var(--text-secondary);">ELO: ${eloRating}</div>
                        </div>
                    </div>
                    <div class="model-stats" style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.85em;">
                        <div class="stat">
                            <div style="color: var(--text-secondary);">Win Rate</div>
                            <div style="color: var(--success); font-weight: bold; font-size: 1.1em;">${winRate}%</div>
                        </div>
                        <div class="stat">
                            <div style="color: var(--text-secondary);">Debates</div>
                            <div style="color: var(--text-primary); font-weight: bold;">${model.total_debates || 0}</div>
                        </div>
                        <div class="stat">
                            <div style="color: var(--text-secondary);">Wins</div>
                            <div style="color: var(--success);">${model.wins || 0}</div>
                        </div>
                        <div class="stat">
                            <div style="color: var(--text-secondary);">Losses</div>
                            <div style="color: var(--danger);">${model.losses || 0}</div>
                        </div>
                    </div>
                    <div class="model-actions" style="margin-top: 12px; display: flex; gap: 6px;">
                        <button onclick="intelligenceArena.viewModelHistory('${model.model_name || model.name}')" style="flex: 1; background: transparent; border: 1px solid ${rankColor}; color: ${rankColor}; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 0.8em;">History</button>
                        <button onclick="intelligenceArena.challengeModel('${model.model_name || model.name}')" style="flex: 1; background: ${rankColor}; color: var(--bg-primary); border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 0.8em;">Challenge</button>
                    </div>
                </div>
            `;
        });

        html += '</div>';

        // Add summary statistics
        const totalDebates = sortedModels.reduce((sum, model) => sum + (model.total_debates || 0), 0);
        const avgWinRate = sortedModels.reduce((sum, model) => {
            const winRate = (model.wins || 0) / Math.max(model.total_debates || 1, 1);
            return sum + winRate;
        }, 0) / Math.max(sortedModels.length, 1) * 100;

        html += `
            <div class="arena-summary" style="margin-top: 20px; padding: 16px; background: rgba(0,0,0,0.3); border-radius: 8px; display: flex; justify-content: space-around; text-align: center;">
                <div>
                    <div style="color: var(--accent-cyan); font-size: 1.2em; font-weight: bold;">${sortedModels.length}</div>
                    <div style="color: var(--text-secondary); font-size: 0.8em;">Active Models</div>
                </div>
                <div>
                    <div style="color: var(--accent-cyan); font-size: 1.2em; font-weight: bold;">${totalDebates}</div>
                    <div style="color: var(--text-secondary); font-size: 0.8em;">Total Debates</div>
                </div>
                <div>
                    <div style="color: var(--accent-cyan); font-size: 1.2em; font-weight: bold;">${avgWinRate.toFixed(1)}%</div>
                    <div style="color: var(--text-secondary); font-size: 0.8em;">Avg Win Rate</div>
                </div>
            </div>
        `;

        container.innerHTML = html;
    }

    updateDebateDisplay() {
        // Update live debate display if there's an active debate
        if (this.debateData && this.debateData.debate_id) {
            this.updateDebateCards(this.debateData);
        }
    }

    updateDebateCards(debateData) {
        // Update Model A card
        const cardA = document.getElementById('debate-text-a');
        if (cardA && debateData.model_a_response) {
            cardA.innerHTML = debateData.model_a_response;
            cardA.parentElement.style.borderTopColor = 'var(--accent-cyan)';
        }

        // Update Model B card
        const cardB = document.getElementById('debate-text-b');
        if (cardB && debateData.model_b_response) {
            cardB.innerHTML = debateData.model_b_response;
            cardB.parentElement.style.borderTopColor = 'var(--danger)';
        }

        // Update Judge card
        const cardJudge = document.getElementById('debate-text-judge');
        if (cardJudge && debateData.judge_verdict) {
            cardJudge.innerHTML = debateData.judge_verdict;
            cardJudge.parentElement.style.borderTopColor = 'var(--accent-purple)';
        }

        // Update debate status
        const statusElement = document.getElementById('debate-status');
        if (statusElement) {
            statusElement.textContent = debateData.status || 'ACTIVE';
            statusElement.className = `status-badge ${debateData.status === 'completed' ? 'status-offline' : 'status-online'}`;
        }
    }

    updateDebateHistory(debates) {
        const container = document.getElementById('debate-history-container');
        if (!container) return;

        if (debates.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 20px; color: var(--text-secondary);">
                    <div style="font-size: 1.5em; margin-bottom: 8px;">📜</div>
                    <div>No debate history available</div>
                </div>
            `;
            return;
        }

        const historyHtml = debates.map(debate => {
            const date = new Date(debate.timestamp || debate.created_at).toLocaleDateString();
            const time = new Date(debate.timestamp || debate.created_at).toLocaleTimeString();
            const winner = debate.winner || 'Draw';
            const winnerColor = winner === 'Model A' ? 'var(--accent-cyan)' :
                winner === 'Model B' ? 'var(--danger)' : 'var(--text-secondary)';

            return `
                <div class="debate-history-item" style="padding: 12px; margin-bottom: 8px; background: rgba(255,255,255,0.05); border-radius: 8px; border-left: 3px solid ${winnerColor};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <div style="font-weight: bold; color: var(--text-primary);">${debate.topic || 'Unknown Topic'}</div>
                        <div style="font-size: 0.8em; color: var(--text-secondary);">${date} ${time}</div>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.9em;">
                        <div style="color: var(--text-secondary);">
                            ${debate.model_a || 'Model A'} vs ${debate.model_b || 'Model B'}
                        </div>
                        <div style="color: ${winnerColor}; font-weight: bold;">Winner: ${winner}</div>
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = historyHtml;
    }

    showStatsError(message) {
        const container = document.getElementById('model-statistics-container');
        if (container) {
            container.innerHTML = `
                <div style="text-align: center; padding: 40px; color: var(--danger);">
                    <div style="font-size: 2em; margin-bottom: 10px;">⚠️</div>
                    <div style="margin-bottom: 12px;">${message}</div>
                    <button onclick="intelligenceArena.retry()" style="background: var(--danger); color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">Retry</button>
                </div>
            `;
        }
    }

    showConnectionError(message) {
        console.warn('🧠 Intelligence Arena:', message);
    }

    async loadAllModels() {
        try {
            const models = ['phi3.5:3.8b', 'llama3.1:8b', 'qwen2.5-coder:7b', 'deepseek-r1:8b'];

            for (const model of models) {
                const response = await fetch(`http://${SERVER_HOST}:9200/v1/models/${model}/load`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                if (response.ok) {
                    console.log(`✅ Model ${model} loading initiated`);
                } else {
                    console.warn(`⚠️ Failed to load model ${model}`);
                }
            }

            // Refresh statistics after a delay
            setTimeout(() => this.fetchModelStatistics(), 5000);

        } catch (error) {
            console.error('❌ Error loading models:', error);
        }
    }

    async startDebate() {
        try {
            const response = await fetch(`http://${SERVER_HOST}:9200/v1/debate/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model_a: 'phi3.5:3.8b',
                    model_b: 'llama3.1:8b',
                    topic: 'The future of artificial intelligence'
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.currentDebateId = data.debate_id;
                console.log('✅ Debate started:', data.debate_id);
            } else {
                console.error('❌ Failed to start debate');
            }
        } catch (error) {
            console.error('❌ Error starting debate:', error);
        }
    }

    async viewModelHistory(modelName) {
        console.log(`📊 Viewing history for ${modelName}`);
        // Could open a modal or navigate to detailed view
    }

    async challengeModel(modelName) {
        console.log(`⚔️ Challenging ${modelName}`);
        // Could start a specific debate against this model
    }

    async refreshData() {
        console.log('🔄 Refreshing Intelligence Arena data...');
        await this.fetchModelStatistics();
        await this.fetchDebateHistory();
    }

    retry() {
        console.log('🔄 Retrying Intelligence Arena connection...');
        this.initializeWebSocket();
        this.fetchModelStatistics();
    }

    destroy() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        if (this.wsManager) {
            this.wsManager.disconnect('debates');
        }
        this.isInitialized = false;
    }
}

// Global Intelligence Arena Panel instance

// === SYSTEM MONITOR REAL-TIME LOGIC ===
function updateMonitorUI(stats) {
    if (!stats) return;
    // Update Metrics
    document.getElementById('monitor-uptime').textContent = formatUptime(stats.uptime_seconds || 0);
    document.getElementById('monitor-rps').textContent = `${stats.requests_total || 0} total`;
    const errRate = stats.requests_total > 0 ? ((stats.error_count / stats.requests_total) * 100).toFixed(1) : "0.0";
    document.getElementById('monitor-errors').textContent = `${errRate}%`;
    // Update Bars
    const cpu = stats.cpu_percent || 0;
    document.getElementById('cpu-val').textContent = `${cpu}%`;
    document.getElementById('cpu-bar').style.width = `${cpu}%`;
    const mem = stats.memory_mb || 0;
    document.getElementById('mem-val').textContent = `${mem} MB`;
    document.getElementById('mem-bar').style.width = `${Math.min(mem / 10, 100)}%`;
    // Disk Usage
    const disk = stats.disk_percent || 0;
    document.getElementById('disk-val').textContent = `${disk}%`;
    document.getElementById('disk-bar').style.width = `${disk}%`;
    // Network Usage (show as KB/s or MB/s)
    let net = stats.network_kbps || 0;
    let netDisplay = net > 1024 ? `${(net / 1024).toFixed(1)} MB/s` : `${net.toFixed(1)} KB/s`;
    document.getElementById('network-val').textContent = netDisplay;
    document.getElementById('network-bar').style.width = `${Math.min(net / 10, 100)}%`;
    // GPU Usage (may be N/A)
    let gpu = (typeof stats.gpu_percent === 'number') ? stats.gpu_percent : null;
    document.getElementById('gpu-val').textContent = (gpu !== null) ? `${gpu}%` : 'N/A';
    document.getElementById('gpu-bar').style.width = (gpu !== null) ? `${gpu}%` : '0%';
    // Temperature (may be N/A)
    let temp = (typeof stats.temperature_c === 'number') ? stats.temperature_c : null;
    document.getElementById('temp-val').textContent = (temp !== null) ? `${temp}°C` : 'N/A';
    document.getElementById('temp-bar').style.width = (temp !== null) ? `${Math.min(temp, 100)}%` : '0%';
}

// === DEBATE LOGIC ===
async function triggerDebate() {
    try {
        await fetch(`${ML_BACKEND_URL}/api/debate/simulate`, { method: 'POST' });
        pushUiAlert('Verify Debate in "Intelligence" View', 'success');
    } catch (e) {
        pushUiAlert('Failed to trigger debate', 'error');
    }
}

// Widget Toggle Function
function toggleWidget(widgetName) {
    const panel = document.getElementById(`panel-${widgetName}`);
    const icon = document.getElementById(`widget-${widgetName}`);

    // If clicking the same widget, close it
    if (activeWidget === widgetName) {
        panel.classList.remove('visible');
        icon.classList.remove('active');
        activeWidget = null;
        return;
    }

    // Close any currently open panel
    if (activeWidget) {
        const oldPanel = document.getElementById(`panel-${activeWidget}`);
        const oldIcon = document.getElementById(`widget-${activeWidget}`);
        if (oldPanel) oldPanel.classList.remove('visible');
        if (oldIcon) oldIcon.classList.remove('active');
    }

    // Open the new panel
    panel.classList.add('visible');
    icon.classList.add('active');
    activeWidget = widgetName;

    // Special handling for HNSC panel - render layers
    if (widgetName === 'hnsc') {
        renderHNSCPanel();
    }
}

// Update widget status dots based on service health
function updateWidgetDots() {
    const mcpDot = document.getElementById('mcp-dot');
    const aiDot = document.getElementById('ai-dot');

    if (mcpDot) {
        mcpDot.className = backendOnline ? 'status-dot' : 'status-dot offline';
    }
    if (aiDot) {
        aiDot.className = backendOnline ? 'status-dot' : 'status-dot offline';
    }
}

// Global AI System Panel instance

// === GOVERNANCE PANEL CLASS ===
class GovernancePanel {
    constructor() {
        this.wsManager = null;
        this.roleData = null;
        this.auditData = null;
        this.isInitialized = false;
        this.updateInterval = null;
        this.roleEngineUrl = `${window.location.protocol}//${window.location.hostname}:9206`;
    }

    initialize() {
        if (this.isInitialized) return;

        // Initialize WebSocket manager if not already done
        if (!window.wsManager) {
            window.wsManager = new WebSocketManager();
        }
        this.wsManager = window.wsManager;

        // Connect to governance WebSocket
        this.initializeWebSocket();

        // Set up periodic updates as fallback
        this.setupPeriodicUpdates();

        this.isInitialized = true;
        console.log('🛡️ Governance Panel initialized');
    }

    initializeWebSocket() {
        this.wsManager.connect(
            'governance',
            (data) => this.handleGovernanceUpdate(data),
            (error) => this.handleConnectionError(error)
        );
    }

    handleGovernanceUpdate(data) {
        if (data.type === 'governance_update') {
            this.roleData = data.roles;
            this.auditData = data.audit_logs;
            this.updateDisplay();
            console.log('🛡️ Governance Panel: Data updated via WebSocket');
        }
    }

    handleConnectionError(error) {
        console.warn('🛡️ Governance Panel WebSocket error:', error);
        this.showConnectionError('WebSocket connection failed, using HTTP fallback');
    }

    setupPeriodicUpdates() {
        // Update every 15 seconds as fallback
        this.updateInterval = setInterval(() => {
            if (this.wsManager.getStatus('governance') !== 'connected') {
                this.fetchGovernanceDataHTTP();
            }
        }, 15000);
    }

    async fetchGovernanceDataHTTP() {
        console.log("🛡️ Fetching governance data from", this.roleEngineUrl);

        // Fetch Roles
        try {
            const response = await fetchWithTimeout(`${this.roleEngineUrl}/api/governance/roles`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            }, 8000);

            if (response.ok) {
                const data = await response.json();
                this.roleData = data;
                this.renderRoleTree();
            } else {
                this.showRoleError(`Failed to load roles (Status ${response.status})`);
            }
        } catch (error) {
            console.error("Role fetch error:", error);
            this.showRoleError(`Role Engine unreachable at ${this.roleEngineUrl}. Ensure Aura Role Engine is running on port 9206.`);
        }

        // Fetch Audit Log
        try {
            const response = await fetchWithTimeout(`${this.roleEngineUrl}/api/governance/audit-logs?limit=50`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            }, 8000);

            if (response.ok) {
                const data = await response.json();
                this.auditData = data.events || data;
                this.renderAuditLog();
            } else {
                this.showAuditError('Audit Log Unavailable');
            }
        } catch (error) {
            console.warn("Audit fetch error:", error);
            this.showAuditError('Audit service unreachable');
        }
    }

    updateDisplay() {
        this.renderRoleTree();
        this.renderAuditLog();
    }

    renderRoleTree() {
        const container = document.getElementById('role-tree-container');
        if (!container) return;

        if (!this.roleData) {
            container.innerHTML = `
                <div style="text-align: center; padding: 20px; color: var(--text-secondary);">
                    <div style="font-size: 1.5em; margin-bottom: 8px;">🔄</div>
                    <div>Loading role hierarchy...</div>
                </div>
            `;
            return;
        }

        // Handle different data structures
        let rolesObj = this.roleData.roles || this.roleData;
        let rolesArray = [];

        if (rolesObj && typeof rolesObj === 'object' && !Array.isArray(rolesObj)) {
            rolesArray = Object.keys(rolesObj).map(key => ({
                name: key,
                ...rolesObj[key]
            }));
        } else if (Array.isArray(rolesObj)) {
            rolesArray = rolesObj;
        }

        if (rolesArray.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 20px; color: var(--text-muted);">
                    <div style="font-size: 1.5em; margin-bottom: 8px;">👥</div>
                    <div>No roles configured</div>
                    <button onclick="governancePanel.createDefaultRoles()" style="margin-top: 10px; background: var(--accent-cyan); color: var(--bg-primary); border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer;">Create Default Roles</button>
                </div>
            `;
            return;
        }

        // Sort roles: Admin first, then by name
        const sorted = rolesArray.sort((a, b) => {
            if (a.name === 'Admin') return -1;
            if (b.name === 'Admin') return 1;
            return a.name.localeCompare(b.name);
        });

        let html = '<div class="role-tree">';

        sorted.forEach(role => {
            const color = this.getRoleColor(role.name);
            const icon = this.getRoleIcon(role.name);
            const capabilities = role.capabilities || [];
            const trustLevel = role.trust_level || 'medium';

            html += `
                <div class="role-item" style="margin-bottom: 12px; padding: 12px; background: rgba(255,255,255,0.05); border-radius: 8px; border-left: 4px solid ${color};">
                    <div class="role-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 1.2em;">${icon}</span>
                            <span style="color: ${color}; font-weight: bold; font-size: 1.1em;">${role.name}</span>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <span class="trust-badge" style="font-size: 0.7em; color: var(--text-muted); background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px;">Trust: ${trustLevel}</span>
                            <span class="version-badge" style="font-size: 0.7em; color: var(--text-muted); background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px;">v${role.version || '1.0'}</span>
                        </div>
                    </div>
                    <div class="role-description" style="font-size: 0.9em; color: var(--text-secondary); margin-bottom: 8px; line-height: 1.4;">
                        ${role.purpose || role.description || 'No description available'}
                    </div>
                    ${capabilities.length > 0 ? `
                        <div class="role-capabilities" style="margin-top: 8px;">
                            <div style="font-size: 0.8em; color: var(--text-muted); margin-bottom: 4px;">Capabilities:</div>
                            <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                                ${capabilities.map(cap => `
                                    <span style="font-size: 0.7em; background: rgba(0, 212, 255, 0.2); color: var(--accent-cyan); padding: 2px 6px; border-radius: 3px;">${cap}</span>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            `;
        });

        html += '</div>';
        container.innerHTML = html;
    }

    renderAuditLog() {
        const tbody = document.getElementById('audit-log-body');
        if (!tbody) return;

        if (!this.auditData || this.auditData.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: center; padding: 20px; color: var(--text-muted);">
                        <div style="margin-bottom: 8px;">📋</div>
                        <div>No recent audit events</div>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = this.auditData.slice(0, 20).map(event => {
            const timestamp = event.timestamp || (event.ts ? event.ts * 1000 : Date.now());
            const time = new Date(timestamp).toLocaleTimeString();
            const date = new Date(timestamp).toLocaleDateString();

            const eventType = event.action || event.type || event.event || 'Unknown';
            const actor = event.actor || event.user || event.source || 'System';
            const result = event.result || event.status || 'Success';
            const risk = event.risk_score || event.risk || 0;

            // Determine colors based on event type and risk
            let eventColor = 'var(--success)';
            let resultColor = 'var(--success)';

            if (risk > 0.7 || result.toLowerCase().includes('fail') || result.toLowerCase().includes('error')) {
                eventColor = 'var(--danger)';
                resultColor = 'var(--danger)';
            } else if (risk > 0.4 || result.toLowerCase().includes('warn') || eventType.toLowerCase().includes('warn')) {
                eventColor = 'var(--warning)';
                resultColor = 'var(--warning)';
            }

            return `
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <td style="padding: 8px; color: var(--text-muted); font-family: monospace; font-size: 0.8em;">
                        <div>${time}</div>
                        <div style="font-size: 0.7em; opacity: 0.7;">${date}</div>
                    </td>
                    <td style="padding: 8px; color: var(--text-primary); font-weight: 500;">${actor}</td>
                    <td style="padding: 8px; color: ${eventColor};">${eventType}</td>
                    <td style="padding: 8px; color: ${resultColor}; font-weight: 500;">${result}</td>
                </tr>
            `;
        }).join('');
    }

    getRoleColor(roleName) {
        const colors = {
            'Admin': 'var(--accent-purple)',
            'Operator': 'var(--accent-cyan)',
            'User': 'var(--success)',
            'Guest': 'var(--text-secondary)'
        };
        return colors[roleName] || 'var(--text-secondary)';
    }

    getRoleIcon(roleName) {
        const icons = {
            'Admin': '👑',
            'Operator': '⚡',
            'User': '👤',
            'Guest': '👥',
            'System': '🤖'
        };
        return icons[roleName] || '👤';
    }

    showRoleError(message) {
        const container = document.getElementById('role-tree-container');
        if (container) {
            container.innerHTML = `
                <div style="text-align: center; padding: 20px; color: var(--danger);">
                    <div style="font-size: 1.5em; margin-bottom: 8px;">⚠️</div>
                    <div style="margin-bottom: 12px;">${message}</div>
                    <button onclick="governancePanel.retry()" style="background: var(--danger); color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer;">Retry</button>
                </div>
            `;
        }
    }

    showAuditError(message) {
        const tbody = document.getElementById('audit-log-body');
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: center; padding: 20px; color: var(--warning);">
                        <div style="margin-bottom: 8px;">⚠️</div>
                        <div>${message}</div>
                    </td>
                </tr>
            `;
        }
    }

    showConnectionError(message) {
        console.warn('🛡️ Governance Panel:', message);
        // Could add a connection status indicator here
    }

    async createDefaultRoles() {
        try {
            const response = await fetch(`${this.roleEngineUrl}/api/governance/roles/create-defaults`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (response.ok) {
                console.log('✅ Default roles created');
                setTimeout(() => this.fetchGovernanceDataHTTP(), 1000);
            } else {
                console.error('❌ Failed to create default roles');
            }
        } catch (error) {
            console.error('❌ Error creating default roles:', error);
        }
    }

    async refreshData() {
        console.log('🔄 Refreshing governance data...');
        await this.fetchGovernanceDataHTTP();
    }

    retry() {
        console.log('🔄 Retrying Governance Panel connection...');
        this.initializeWebSocket();
        this.fetchGovernanceDataHTTP();
    }

    destroy() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        if (this.wsManager) {
            this.wsManager.disconnect('governance');
        }
        this.isInitialized = false;
    }
}

// Global Governance Panel instance

// === INTELLIGENCE ARENA PANEL CLASS ===
class IntelligenceArenaPanel {
    constructor() {
        this.wsManager = null;
        this.modelStats = null;
        this.debateData = null;
        this.isInitialized = false;
        this.updateInterval = null;
        this.currentDebateId = null;
    }

    initialize() {
        if (this.isInitialized) return;

        // Initialize WebSocket manager if not already done
        if (!window.wsManager) {
            window.wsManager = new WebSocketManager();
        }
        this.wsManager = window.wsManager;

        // Connect to debates WebSocket
        this.initializeWebSocket();

        // Set up periodic updates as fallback
        this.setupPeriodicUpdates();

        // Load initial data
        this.fetchModelStatistics();

        this.isInitialized = true;
        console.log('🧠 Intelligence Arena Panel initialized');
    }

    initializeWebSocket() {
        this.wsManager.connect(
            'debates',
            (data) => this.handleDebateUpdate(data),
            (error) => this.handleConnectionError(error)
        );
    }

    handleDebateUpdate(data) {
        if (data.type === 'debate_update') {
            this.debateData = data;
            this.updateDebateDisplay();
            console.log('🧠 Intelligence Arena: Debate data updated via WebSocket');
        } else if (data.type === 'model_stats_update') {
            this.modelStats = data.stats;
            this.updateModelStatistics();
            console.log('🧠 Intelligence Arena: Model stats updated via WebSocket');
        }
    }

    handleConnectionError(error) {
        console.warn('🧠 Intelligence Arena WebSocket error:', error);
        this.showConnectionError('WebSocket connection failed, using HTTP fallback');
    }

    setupPeriodicUpdates() {
        // Update every 30 seconds as fallback
        this.updateInterval = setInterval(() => {
            if (this.wsManager.getStatus('debates') !== 'connected') {
                this.fetchModelStatistics();
            }
        }, 30000);
    }

    async fetchModelStatistics() {
        try {
            // Fetch model statistics from debate leaderboard
            const response = await fetchWithTimeout(`http://${SERVER_HOST}:9200/v1/debate/leaderboard`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            }, 8000);

            if (response.ok) {
                const data = await response.json();
                this.modelStats = data;
                this.updateModelStatistics();
            } else {
                this.showStatsError('Failed to load model statistics');
            }
        } catch (error) {
            console.error('Model statistics fetch error:', error);
            this.showStatsError('Statistics service unavailable');
        }
    }

    async fetchDebateHistory() {
        try {
            const response = await fetchWithTimeout(`http://${SERVER_HOST}:9200/v1/debate/history?limit=10`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            }, 8000);

            if (response.ok) {
                const data = await response.json();
                this.updateDebateHistory(data.debates || []);
            }
        } catch (error) {
            console.error('Debate history fetch error:', error);
        }
    }

    updateModelStatistics() {
        const container = document.getElementById('model-statistics-container');
        if (!container) return;

        if (!this.modelStats || this.modelStats.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 40px; color: var(--text-secondary);">
                    <div style="font-size: 2em; margin-bottom: 10px;">🤖</div>
                    <div style="margin-bottom: 10px;">No model statistics available</div>
                    <button onclick="intelligenceArena.loadAllModels()" style="background: var(--accent-cyan); color: var(--bg-primary); border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">Load All Models</button>
                </div>
            `;
            return;
        }

        // Sort models by ELO rating or win rate
        const sortedModels = [...this.modelStats].sort((a, b) => (b.elo_rating || b.win_rate || 0) - (a.elo_rating || a.win_rate || 0));

        let html = '<div class="model-stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 15px;">';

        sortedModels.forEach((model, index) => {
            const winRate = ((model.wins || 0) / Math.max(model.total_debates || 1, 1) * 100).toFixed(1);
            const eloRating = model.elo_rating || 1200;
            const rankColor = index === 0 ? 'var(--accent-cyan)' : index === 1 ? 'var(--success)' : 'var(--text-secondary)';
            const rankIcon = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : '🤖';

            html += `
                <div class="model-stat-card" style="background: rgba(0, 212, 255, 0.1); border: 1px solid ${rankColor}; border-radius: 12px; padding: 16px; position: relative;">
                    <div class="model-rank" style="position: absolute; top: -8px; right: -8px; background: ${rankColor}; color: var(--bg-primary); width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.8em; font-weight: bold;">
                        ${index + 1}
                    </div>
                    <div class="model-header" style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
                        <span style="font-size: 1.5em;">${rankIcon}</span>
                        <div>
                            <h4 style="color: ${rankColor}; margin: 0; font-size: 1em;">${model.model_name || model.name || 'Unknown'}</h4>
                            <div style="font-size: 0.8em; color: var(--text-secondary);">ELO: ${eloRating}</div>
                        </div>
                    </div>
                    <div class="model-stats" style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.85em;">
                        <div class="stat">
                            <div style="color: var(--text-secondary);">Win Rate</div>
                            <div style="color: var(--success); font-weight: bold; font-size: 1.1em;">${winRate}%</div>
                        </div>
                        <div class="stat">
                            <div style="color: var(--text-secondary);">Debates</div>
                            <div style="color: var(--text-primary); font-weight: bold;">${model.total_debates || 0}</div>
                        </div>
                        <div class="stat">
                            <div style="color: var(--text-secondary);">Wins</div>
                            <div style="color: var(--success);">${model.wins || 0}</div>
                        </div>
                        <div class="stat">
                            <div style="color: var(--text-secondary);">Losses</div>
                            <div style="color: var(--danger);">${model.losses || 0}</div>
                        </div>
                    </div>
                    <div class="model-actions" style="margin-top: 12px; display: flex; gap: 6px;">
                        <button onclick="intelligenceArena.viewModelHistory('${model.model_name || model.name}')" style="flex: 1; background: transparent; border: 1px solid ${rankColor}; color: ${rankColor}; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 0.8em;">History</button>
                        <button onclick="intelligenceArena.challengeModel('${model.model_name || model.name}')" style="flex: 1; background: ${rankColor}; color: var(--bg-primary); border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 0.8em;">Challenge</button>
                    </div>
                </div>
            `;
        });

        html += '</div>';

        // Add summary statistics
        const totalDebates = sortedModels.reduce((sum, model) => sum + (model.total_debates || 0), 0);
        const avgWinRate = sortedModels.reduce((sum, model) => {
            const winRate = (model.wins || 0) / Math.max(model.total_debates || 1, 1);
            return sum + winRate;
        }, 0) / Math.max(sortedModels.length, 1) * 100;

        html += `
            <div class="arena-summary" style="margin-top: 20px; padding: 16px; background: rgba(0,0,0,0.3); border-radius: 8px; display: flex; justify-content: space-around; text-align: center;">
                <div>
                    <div style="color: var(--accent-cyan); font-size: 1.2em; font-weight: bold;">${sortedModels.length}</div>
                    <div style="color: var(--text-secondary); font-size: 0.8em;">Active Models</div>
                </div>
                <div>
                    <div style="color: var(--accent-cyan); font-size: 1.2em; font-weight: bold;">${totalDebates}</div>
                    <div style="color: var(--text-secondary); font-size: 0.8em;">Total Debates</div>
                </div>
                <div>
                    <div style="color: var(--accent-cyan); font-size: 1.2em; font-weight: bold;">${avgWinRate.toFixed(1)}%</div>
                    <div style="color: var(--text-secondary); font-size: 0.8em;">Avg Win Rate</div>
                </div>
            </div>
        `;

        container.innerHTML = html;
    }

    updateDebateDisplay() {
        // Update live debate display if there's an active debate
        if (this.debateData && this.debateData.debate_id) {
            this.updateDebateCards(this.debateData);
        }
    }

    updateDebateCards(debateData) {
        // Update Model A card
        const cardA = document.getElementById('debate-text-a');
        if (cardA && debateData.model_a_response) {
            cardA.innerHTML = debateData.model_a_response;
            cardA.parentElement.style.borderTopColor = 'var(--accent-cyan)';
        }

        // Update Model B card
        const cardB = document.getElementById('debate-text-b');
        if (cardB && debateData.model_b_response) {
            cardB.innerHTML = debateData.model_b_response;
            cardB.parentElement.style.borderTopColor = 'var(--danger)';
        }

        // Update Judge card
        const cardJudge = document.getElementById('debate-text-judge');
        if (cardJudge && debateData.judge_verdict) {
            cardJudge.innerHTML = debateData.judge_verdict;
            cardJudge.parentElement.style.borderTopColor = 'var(--accent-purple)';
        }

        // Update debate status
        const statusElement = document.getElementById('debate-status');
        if (statusElement) {
            statusElement.textContent = debateData.status || 'ACTIVE';
            statusElement.className = `status-badge ${debateData.status === 'completed' ? 'status-offline' : 'status-online'}`;
        }
    }

    updateDebateHistory(debates) {
        const container = document.getElementById('debate-history-container');
        if (!container) return;

        if (debates.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 20px; color: var(--text-secondary);">
                    <div style="font-size: 1.5em; margin-bottom: 8px;">📜</div>
                    <div>No debate history available</div>
                </div>
            `;
            return;
        }

        const historyHtml = debates.map(debate => {
            const date = new Date(debate.timestamp || debate.created_at).toLocaleDateString();
            const time = new Date(debate.timestamp || debate.created_at).toLocaleTimeString();
            const winner = debate.winner || 'Draw';
            const winnerColor = winner === 'Model A' ? 'var(--accent-cyan)' :
                winner === 'Model B' ? 'var(--danger)' : 'var(--text-secondary)';

            return `
                <div class="debate-history-item" style="padding: 12px; margin-bottom: 8px; background: rgba(255,255,255,0.05); border-radius: 8px; border-left: 3px solid ${winnerColor};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <div style="font-weight: bold; color: var(--text-primary);">${debate.topic || 'Unknown Topic'}</div>
                        <div style="font-size: 0.8em; color: var(--text-secondary);">${date} ${time}</div>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.9em;">
                        <div style="color: var(--text-secondary);">
                            ${debate.model_a || 'Model A'} vs ${debate.model_b || 'Model B'}
                        </div>
                        <div style="color: ${winnerColor}; font-weight: bold;">Winner: ${winner}</div>
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = historyHtml;
    }

    showStatsError(message) {
        const container = document.getElementById('model-statistics-container');
        if (container) {
            container.innerHTML = `
                <div style="text-align: center; padding: 40px; color: var(--danger);">
                    <div style="font-size: 2em; margin-bottom: 10px;">⚠️</div>
                    <div style="margin-bottom: 12px;">${message}</div>
                    <button onclick="intelligenceArena.retry()" style="background: var(--danger); color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">Retry</button>
                </div>
            `;
        }
    }

    showConnectionError(message) {
        console.warn('🧠 Intelligence Arena:', message);
    }

    async loadAllModels() {
        try {
            const models = ['phi3.5:3.8b', 'llama3.1:8b', 'qwen2.5-coder:7b', 'deepseek-r1:8b'];

            for (const model of models) {
                const response = await fetch(`http://${SERVER_HOST}:9200/v1/models/${model}/load`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                if (response.ok) {
                    console.log(`✅ Model ${model} loading initiated`);
                } else {
                    console.warn(`⚠️ Failed to load model ${model}`);
                }
            }

            // Refresh statistics after a delay
            setTimeout(() => this.fetchModelStatistics(), 5000);

        } catch (error) {
            console.error('❌ Error loading models:', error);
        }
    }

    async startDebate() {
        try {
            const response = await fetch(`http://${SERVER_HOST}:9200/v1/debate/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model_a: 'phi3.5:3.8b',
                    model_b: 'llama3.1:8b',
                    topic: 'The future of artificial intelligence'
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.currentDebateId = data.debate_id;
                console.log('✅ Debate started:', data.debate_id);
            } else {
                console.error('❌ Failed to start debate');
            }
        } catch (error) {
            console.error('❌ Error starting debate:', error);
        }
    }

    async viewModelHistory(modelName) {
        console.log(`📊 Viewing history for ${modelName}`);
        // Could open a modal or navigate to detailed view
    }

    async challengeModel(modelName) {
        console.log(`⚔️ Challenging ${modelName}`);
        // Could start a specific debate against this model
    }

    async refreshData() {
        console.log('🔄 Refreshing Intelligence Arena data...');
        await this.fetchModelStatistics();
        await this.fetchDebateHistory();
    }

    retry() {
        console.log('🔄 Retrying Intelligence Arena connection...');
        this.initializeWebSocket();
        this.fetchModelStatistics();
    }

    destroy() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        if (this.wsManager) {
            this.wsManager.disconnect('debates');
        }
        this.isInitialized = false;
    }
}

// Global Intelligence Arena Panel instance

// === SYSTEM MONITOR REAL-TIME LOGIC ===
function updateMonitorUI(stats) {
    if (!stats) return;
    // Update Metrics
    document.getElementById('monitor-uptime').textContent = formatUptime(stats.uptime_seconds || 0);
    document.getElementById('monitor-rps').textContent = `${stats.requests_total || 0} total`;
    const errRate = stats.requests_total > 0 ? ((stats.error_count / stats.requests_total) * 100).toFixed(1) : "0.0";
    document.getElementById('monitor-errors').textContent = `${errRate}%`;
    // Update Bars
    const cpu = stats.cpu_percent || 0;
    document.getElementById('cpu-val').textContent = `${cpu}%`;
    document.getElementById('cpu-bar').style.width = `${cpu}%`;
    const mem = stats.memory_mb || 0;
    document.getElementById('mem-val').textContent = `${mem} MB`;
    document.getElementById('mem-bar').style.width = `${Math.min(mem / 10, 100)}%`;
    // Disk Usage
    const disk = stats.disk_percent || 0;
    document.getElementById('disk-val').textContent = `${disk}%`;
    document.getElementById('disk-bar').style.width = `${disk}%`;
    // Network Usage (show as KB/s or MB/s)
    let net = stats.network_kbps || 0;
    let netDisplay = net > 1024 ? `${(net / 1024).toFixed(1)} MB/s` : `${net.toFixed(1)} KB/s`;
    document.getElementById('network-val').textContent = netDisplay;
    document.getElementById('network-bar').style.width = `${Math.min(net / 10, 100)}%`;
    // GPU Usage (may be N/A)
    let gpu = (typeof stats.gpu_percent === 'number') ? stats.gpu_percent : null;
    document.getElementById('gpu-val').textContent = (gpu !== null) ? `${gpu}%` : 'N/A';
    document.getElementById('gpu-bar').style.width = (gpu !== null) ? `${gpu}%` : '0%';
    // Temperature (may be N/A)
    let temp = (typeof stats.temperature_c === 'number') ? stats.temperature_c : null;
    document.getElementById('temp-val').textContent = (temp !== null) ? `${temp}°C` : 'N/A';
    document.getElementById('temp-bar').style.width = (temp !== null) ? `${Math.min(temp, 100)}%` : '0%';
    // History
    pushHistory(monitorHistory.cpu, stats.cpu_percent || 0);
    pushHistory(monitorHistory.mem, stats.memory_mb || 0);
    pushHistory(monitorHistory.disk, stats.disk_percent || 0);
    pushHistory(monitorHistory.network, stats.network_kbps || 0);
    pushHistory(monitorHistory.gpu, typeof stats.gpu_percent === 'number' ? stats.gpu_percent : 0);
    pushHistory(monitorHistory.temp, typeof stats.temperature_c === 'number' ? stats.temperature_c : 0);
    // Render sparklines
    renderSparkline('cpu-spark', monitorHistory.cpu, '#00d4ff');
    renderSparkline('mem-spark', monitorHistory.mem, '#a259ff');
    renderSparkline('disk-spark', monitorHistory.disk, '#00ffff');
    renderSparkline('network-spark', monitorHistory.network, '#00ff00');
    renderSparkline('gpu-spark', monitorHistory.gpu, '#ff0044');
    renderSparkline('temp-spark', monitorHistory.temp, '#ffaa00');
    // Threshold alerts
    setThresholdColor(stats.cpu_percent, 70, 90, document.getElementById('cpu-val'));
    setThresholdColor(stats.memory_mb, 12000, 16000, document.getElementById('mem-val'));
    setThresholdColor(stats.disk_percent, 80, 95, document.getElementById('disk-val'));
    setThresholdColor(stats.network_kbps, 5000, 20000, document.getElementById('network-val'));
    setThresholdColor(stats.gpu_percent, 80, 95, document.getElementById('gpu-val'));
    setThresholdColor(stats.temperature_c, 70, 85, document.getElementById('temp-val'));
}

// === DEBATE LOGIC ===
async function triggerDebate() {
    try {
        await fetch(`${ML_BACKEND_URL}/api/debate/simulate`, { method: 'POST' });
        pushUiAlert('Verify Debate in "Intelligence" View', 'success');
    } catch (e) {
        pushUiAlert('Failed to trigger debate', 'error');
    }
}

// Widget Toggle Function
function toggleWidget(widgetName) {
    const panel = document.getElementById(`panel-${widgetName}`);
    const icon = document.getElementById(`widget-${widgetName}`);

    // If clicking the same widget, close it
    if (activeWidget === widgetName) {
        panel.classList.remove('visible');
        icon.classList.remove('active');
        activeWidget = null;
        return;
    }

    // Close any currently open panel
    if (activeWidget) {
        const oldPanel = document.getElementById(`panel-${activeWidget}`);
        const oldIcon = document.getElementById(`widget-${activeWidget}`);
        if (oldPanel) oldPanel.classList.remove('visible');
        if (oldIcon) oldIcon.classList.remove('active');
    }

    // Open the new panel
    panel.classList.add('visible');
    icon.classList.add('active');
    activeWidget = widgetName;

    // Special handling for HNSC panel - render layers
    if (widgetName === 'hnsc') {
        renderHNSCPanel();
    }
}

// Update widget status dots based on service health
function updateWidgetDots() {
    const mcpDot = document.getElementById('mcp-dot');
    const aiDot = document.getElementById('ai-dot');

    if (mcpDot) {
        mcpDot.className = backendOnline ? 'status-dot' : 'status-dot offline';
    }
    if (aiDot) {
        aiDot.className = backendOnline ? 'status-dot' : 'status-dot offline';
    }
}

// Global AI System Panel instance

// === GOVERNANCE PANEL CLASS ===
class GovernancePanel {
    constructor() {
        this.wsManager = null;
        this.roleData = null;
        this.auditData = null;
        this.isInitialized = false;
        this.updateInterval = null;
        this.roleEngineUrl = `${window.location.protocol}//${window.location.hostname}:9206`;
    }

    initialize() {
        if (this.isInitialized) return;

        // Initialize WebSocket manager if not already done
        if (!window.wsManager) {
            window.wsManager = new WebSocketManager();
        }
        this.wsManager = window.wsManager;

        // Connect to governance WebSocket
        this.initializeWebSocket();

        // Set up periodic updates as fallback
        this.setupPeriodicUpdates();

        this.isInitialized = true;
        console.log('🛡️ Governance Panel initialized');
    }

    initializeWebSocket() {
        this.wsManager.connect(
            'governance',
            (data) => this.handleGovernanceUpdate(data),
            (error) => this.handleConnectionError(error)
        );
    }

    handleGovernanceUpdate(data) {
        if (data.type === 'governance_update') {
            this.roleData = data.roles;
            this.auditData = data.audit_logs;
            this.updateDisplay();
            console.log('🛡️ Governance Panel: Data updated via WebSocket');
        }
    }

    handleConnectionError(error) {
        console.warn('🛡️ Governance Panel WebSocket error:', error);
        this.showConnectionError('WebSocket connection failed, using HTTP fallback');
    }

    setupPeriodicUpdates() {
        // Update every 15 seconds as fallback
        this.updateInterval = setInterval(() => {
            if (this.wsManager.getStatus('governance') !== 'connected') {
                this.fetchGovernanceDataHTTP();
            }
        }, 15000);
    }

    async fetchGovernanceDataHTTP() {
        console.log("🛡️ Fetching governance data from", this.roleEngineUrl);

        // Fetch Roles
        try {
            const response = await fetchWithTimeout(`${this.roleEngineUrl}/api/governance/roles`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            }, 8000);

            if (response.ok) {
                const data = await response.json();
                this.roleData = data;
                this.renderRoleTree();
            } else {
                this.showRoleError(`Failed to load roles (Status ${response.status})`);
            }
        } catch (error) {
            console.error("Role fetch error:", error);
            this.showRoleError(`Role Engine unreachable at ${this.roleEngineUrl}. Ensure Aura Role Engine is running on port 9206.`);
        }

        // Fetch Audit Log
        try {
            const response = await fetchWithTimeout(`${this.roleEngineUrl}/api/governance/audit-logs?limit=50`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            }, 8000);

            if (response.ok) {
                const data = await response.json();
                this.auditData = data.events || data;
                this.renderAuditLog();
            } else {
                this.showAuditError('Audit Log Unavailable');
            }
        } catch (error) {
            console.warn("Audit fetch error:", error);
            this.showAuditError('Audit service unreachable');
        }
    }

    updateDisplay() {
        this.renderRoleTree();
        this.renderAuditLog();
    }

