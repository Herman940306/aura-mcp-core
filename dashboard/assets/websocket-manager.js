/**
 * WebSocket Manager for Aura IA Dashboard
 * Handles real-time connections with automatic reconnection and fallback
 * 
 * Project Creator: Herman Swanepoel
 * Version: 1.0
 * Last Updated: December 13, 2025
 */

class WebSocketManager {
    constructor() {
        this.connections = new Map();
        this.reconnectAttempts = new Map();
        this.maxReconnectAttempts = 5;
        this.baseReconnectDelay = 1000; // Start with 1 second
        this.pollingIntervals = new Map();
        this.connectionStatus = new Map();
        this.messageHandlers = new Map();
        this.errorHandlers = new Map();
        
        // Auto-detect server host (works for localhost AND remote deployment)
        this.serverHost = window.location.hostname || 'localhost';
        
        // WebSocket endpoints configuration
        this.endpoints = {
            models: { port: 9200, path: '/ws/models' },
            system: { port: 9200, path: '/ws/system' },
            database: { port: 9200, path: '/ws/database' },
            governance: { port: 9206, path: '/ws/governance' },
            debates: { port: 9200, path: '/ws/debates' }
        };
        
        console.log('🔌 WebSocket Manager initialized for host:', this.serverHost);
    }
    
    /**
     * Connect to a WebSocket endpoint with automatic reconnection
     * @param {string} endpoint - Endpoint name (models, system, database, governance, debates)
     * @param {function} onMessage - Message handler function
     * @param {function} onError - Error handler function (optional)
     * @returns {boolean} - Success status
     */
    connect(endpoint, onMessage, onError = null) {
        if (!this.endpoints[endpoint]) {
            console.error(`❌ Unknown WebSocket endpoint: ${endpoint}`);
            return false;
        }
        
        // Store handlers
        this.messageHandlers.set(endpoint, onMessage);
        if (onError) {
            this.errorHandlers.set(endpoint, onError);
        }
        
        // If already connected, just update handlers
        if (this.connections.has(endpoint) && this.connections.get(endpoint).readyState === WebSocket.OPEN) {
            console.log(`🔄 WebSocket ${endpoint} already connected, updating handlers`);
            return true;
        }
        
        return this._establishConnection(endpoint);
    }
    
    /**
     * Establish WebSocket connection
     * @private
     */
    _establishConnection(endpoint) {
        const config = this.endpoints[endpoint];
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${this.serverHost}:${config.port}${config.path}`;
        
        console.log(`🔌 Connecting to ${endpoint} WebSocket at ${wsUrl}...`);
        
        try {
            const ws = new WebSocket(wsUrl);
            
            ws.onopen = () => {
                console.log(`✅ WebSocket ${endpoint} connected`);
                this.connections.set(endpoint, ws);
                this.connectionStatus.set(endpoint, 'connected');
                this.reconnectAttempts.set(endpoint, 0);
                this._updateConnectionIndicator(endpoint, 'connected');
                
                // Clear any polling fallback
                this._clearPollingFallback(endpoint);
            };
            
            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    const handler = this.messageHandlers.get(endpoint);
                    if (handler) {
                        handler(data);
                    }
                } catch (error) {
                    console.error(`❌ WebSocket ${endpoint} message parse error:`, error);
                }
            };
            
            ws.onclose = (event) => {
                console.log(`❌ WebSocket ${endpoint} disconnected (code: ${event.code})`);
                this.connectionStatus.set(endpoint, 'disconnected');
                this._updateConnectionIndicator(endpoint, 'disconnected');
                
                // Schedule reconnection
                this._scheduleReconnect(endpoint);
                
                // Enable polling fallback
                this._enablePollingFallback(endpoint);
            };
            
            ws.onerror = (error) => {
                console.error(`❌ WebSocket ${endpoint} error:`, error);
                this.connectionStatus.set(endpoint, 'error');
                this._updateConnectionIndicator(endpoint, 'error');
                
                const errorHandler = this.errorHandlers.get(endpoint);
                if (errorHandler) {
                    errorHandler(error);
                }
            };
            
            return true;
            
        } catch (error) {
            console.error(`❌ Failed to create WebSocket ${endpoint}:`, error);
            this._enablePollingFallback(endpoint);
            return false;
        }
    }
    
    /**
     * Disconnect from a WebSocket endpoint
     * @param {string} endpoint - Endpoint name
     */
    disconnect(endpoint) {
        const ws = this.connections.get(endpoint);
        if (ws) {
            ws.close();
            this.connections.delete(endpoint);
        }
        
        this.connectionStatus.set(endpoint, 'disconnected');
        this._updateConnectionIndicator(endpoint, 'disconnected');
        this._clearPollingFallback(endpoint);
        
        console.log(`🔌 WebSocket ${endpoint} disconnected`);
    }
    
    /**
     * Send data to a WebSocket endpoint
     * @param {string} endpoint - Endpoint name
     * @param {object} data - Data to send
     * @returns {boolean} - Success status
     */
    send(endpoint, data) {
        const ws = this.connections.get(endpoint);
        if (ws && ws.readyState === WebSocket.OPEN) {
            try {
                ws.send(JSON.stringify(data));
                return true;
            } catch (error) {
                console.error(`❌ Failed to send WebSocket ${endpoint} message:`, error);
                return false;
            }
        }
        
        console.warn(`⚠️ WebSocket ${endpoint} not connected, cannot send message`);
        return false;
    }
    
    /**
     * Get connection status for an endpoint
     * @param {string} endpoint - Endpoint name
     * @returns {string} - Connection status
     */
    getStatus(endpoint) {
        return this.connectionStatus.get(endpoint) || 'disconnected';
    }
    
    /**
     * Schedule reconnection with exponential backoff
     * @private
     */
    _scheduleReconnect(endpoint) {
        const attempts = this.reconnectAttempts.get(endpoint) || 0;
        
        if (attempts >= this.maxReconnectAttempts) {
            console.warn(`⚠️ WebSocket ${endpoint} max reconnection attempts reached`);
            this._updateConnectionIndicator(endpoint, 'failed');
            return;
        }
        
        const delay = this.baseReconnectDelay * Math.pow(2, attempts);
        this.reconnectAttempts.set(endpoint, attempts + 1);
        
        console.log(`🔄 WebSocket ${endpoint} reconnecting in ${delay}ms (attempt ${attempts + 1}/${this.maxReconnectAttempts})`);
        
        setTimeout(() => {
            if (this.connectionStatus.get(endpoint) !== 'connected') {
                this._establishConnection(endpoint);
            }
        }, delay);
    }
    
    /**
     * Enable HTTP polling fallback when WebSocket is unavailable
     * @private
     */
    _enablePollingFallback(endpoint) {
        // Clear any existing polling
        this._clearPollingFallback(endpoint);
        
        const config = this.endpoints[endpoint];
        const httpUrl = `http://${this.serverHost}:${config.port}/api${config.path.replace('/ws', '')}`;
        
        console.log(`🔄 Enabling HTTP polling fallback for ${endpoint}: ${httpUrl}`);
        
        const pollInterval = setInterval(async () => {
            try {
                const response = await fetch(httpUrl, {
                    method: 'GET',
                    headers: { 'Accept': 'application/json' },
                    timeout: 5000
                });
                
                if (response.ok) {
                    const data = await response.json();
                    const handler = this.messageHandlers.get(endpoint);
                    if (handler) {
                        handler(data);
                    }
                }
            } catch (error) {
                console.debug(`HTTP polling ${endpoint} failed:`, error.message);
            }
        }, 10000); // Poll every 10 seconds
        
        this.pollingIntervals.set(endpoint, pollInterval);
    }
    
    /**
     * Clear HTTP polling fallback
     * @private
     */
    _clearPollingFallback(endpoint) {
        const interval = this.pollingIntervals.get(endpoint);
        if (interval) {
            clearInterval(interval);
            this.pollingIntervals.delete(endpoint);
            console.log(`🔄 Cleared HTTP polling fallback for ${endpoint}`);
        }
    }
    
    /**
     * Update connection status indicator in UI
     * @private
     */
    _updateConnectionIndicator(endpoint, status) {
        // Update status dots for specific endpoints
        const statusDots = {
            models: 'ai-dot',
            system: 'system-dot',
            database: 'database-dot',
            governance: 'governance-dot',
            debates: 'debate-dot'
        };
        
        const dotId = statusDots[endpoint];
        if (dotId) {
            const dot = document.getElementById(dotId);
            if (dot) {
                dot.classList.remove('online', 'offline', 'checking');
                
                switch (status) {
                    case 'connected':
                        dot.classList.add('online');
                        break;
                    case 'disconnected':
                    case 'error':
                    case 'failed':
                        dot.classList.add('offline');
                        break;
                    default:
                        dot.classList.add('checking');
                }
            }
        }
        
        // Update connection status text if element exists
        const statusElement = document.getElementById(`${endpoint}-connection-status`);
        if (statusElement) {
            const statusText = {
                connected: '🟢 Connected',
                disconnected: '🔴 Disconnected',
                error: '🟡 Error',
                failed: '❌ Failed'
            };
            
            statusElement.textContent = statusText[status] || '🟡 Unknown';
            statusElement.className = `connection-status ${status}`;
        }
    }
    
    /**
     * Disconnect all WebSocket connections
     */
    disconnectAll() {
        console.log('🔌 Disconnecting all WebSocket connections...');
        
        for (const endpoint of this.connections.keys()) {
            this.disconnect(endpoint);
        }
        
        // Clear all polling intervals
        for (const interval of this.pollingIntervals.values()) {
            clearInterval(interval);
        }
        this.pollingIntervals.clear();
    }
    
    /**
     * Get connection statistics
     * @returns {object} - Connection statistics
     */
    getStats() {
        const stats = {
            total: this.endpoints.length,
            connected: 0,
            disconnected: 0,
            polling: this.pollingIntervals.size
        };
        
        for (const status of this.connectionStatus.values()) {
            if (status === 'connected') {
                stats.connected++;
            } else {
                stats.disconnected++;
            }
        }
        
        return stats;
    }
}

// Export for use in other scripts
window.WebSocketManager = WebSocketManager;

// Auto-cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.wsManager) {
        window.wsManager.disconnectAll();
    }
});

console.log('📡 WebSocket Manager loaded successfully');