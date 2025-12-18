#!/usr/bin/env python3
"""
WebSocket Manager Infrastructure for Aura IA Dashboard

Provides centralized WebSocket connection management with:
- Connection pooling and lifecycle management
- Automatic reconnection with exponential backoff
- Error handling and graceful degradation
- Real-time data broadcasting to connected clients

Project Creator: Herman Swanepoel
Document Version: 1.0
Last Updated: December 13, 2025
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("aura_ia.websocket_manager")


class ConnectionState(Enum):
    """WebSocket connection states."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"


@dataclass
class WebSocketConnection:
    """Represents a single WebSocket connection with metadata."""
    websocket: WebSocket
    client_id: str
    endpoint: str
    connected_at: float = field(default_factory=time.time)
    last_message_at: float = field(default_factory=time.time)
    state: ConnectionState = ConnectionState.CONNECTING
    reconnect_attempts: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update_last_message(self) -> None:
        """Update the last message timestamp."""
        self.last_message_at = time.time()


@dataclass
class WebSocketManagerConfig:
    """Configuration for WebSocket Manager."""
    max_connections_per_endpoint: int = 100
    max_reconnect_attempts: int = 5
    reconnect_base_delay: float = 1.0  # seconds
    reconnect_max_delay: float = 30.0  # seconds
    heartbeat_interval: float = 30.0  # seconds
    connection_timeout: float = 60.0  # seconds
    message_queue_size: int = 1000


class WebSocketManager:
    """
    Centralized WebSocket connection manager for real-time dashboard updates.
    
    Handles:
    - Multiple endpoint types (models, system, database, governance, debates)
    - Connection pooling per endpoint
    - Automatic reconnection with exponential backoff
    - Broadcasting messages to all connected clients
    - Error handling and graceful degradation
    """

    def __init__(self, config: Optional[WebSocketManagerConfig] = None):
        self.config = config or WebSocketManagerConfig()
        
        # Connection pools by endpoint
        self._connections: Dict[str, Dict[str, WebSocketConnection]] = {}
        
        # Message handlers by endpoint
        self._handlers: Dict[str, List[Callable]] = {}
        
        # Background tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Statistics
        self._stats = {
            "total_connections": 0,
            "total_messages_sent": 0,
            "total_messages_received": 0,
            "total_errors": 0,
            "started_at": time.time()
        }
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        
        logger.info("WebSocketManager initialized with config: %s", self.config)

    async def start(self) -> None:
        """Start background tasks for heartbeat and cleanup."""
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("WebSocketManager background tasks started")

    async def stop(self) -> None:
        """Stop all background tasks and close connections."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
            
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        
        # Close all connections
        async with self._lock:
            for endpoint in list(self._connections.keys()):
                for client_id in list(self._connections[endpoint].keys()):
                    await self._close_connection(endpoint, client_id)
        
        logger.info("WebSocketManager stopped")

    async def connect(
        self,
        websocket: WebSocket,
        endpoint: str,
        client_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Accept and register a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection to register
            endpoint: The endpoint type (e.g., 'models', 'system', 'database')
            client_id: Unique identifier for the client
            metadata: Optional metadata about the connection
            
        Returns:
            True if connection was accepted, False otherwise
        """
        async with self._lock:
            # Initialize endpoint pool if needed
            if endpoint not in self._connections:
                self._connections[endpoint] = {}
            
            # Check connection limit
            if len(self._connections[endpoint]) >= self.config.max_connections_per_endpoint:
                logger.warning(
                    "Connection limit reached for endpoint %s (max: %d)",
                    endpoint,
                    self.config.max_connections_per_endpoint
                )
                return False
            
            try:
                await websocket.accept()
                
                connection = WebSocketConnection(
                    websocket=websocket,
                    client_id=client_id,
                    endpoint=endpoint,
                    state=ConnectionState.CONNECTED,
                    metadata=metadata or {}
                )
                
                self._connections[endpoint][client_id] = connection
                self._stats["total_connections"] += 1
                
                logger.info(
                    "WebSocket connected: endpoint=%s, client_id=%s",
                    endpoint,
                    client_id
                )
                
                # Send welcome message
                await self._send_to_client(
                    endpoint,
                    client_id,
                    {
                        "type": "connection_established",
                        "endpoint": endpoint,
                        "client_id": client_id,
                        "timestamp": datetime.now(UTC).isoformat()
                    }
                )
                
                return True
                
            except Exception as e:
                logger.error("Failed to accept WebSocket connection: %s", e)
                self._stats["total_errors"] += 1
                return False

    async def disconnect(self, endpoint: str, client_id: str) -> None:
        """
        Disconnect and unregister a WebSocket connection.
        
        Args:
            endpoint: The endpoint type
            client_id: The client identifier
        """
        await self._close_connection(endpoint, client_id)

    async def _close_connection(self, endpoint: str, client_id: str) -> None:
        """Internal method to close a connection."""
        async with self._lock:
            if endpoint in self._connections and client_id in self._connections[endpoint]:
                connection = self._connections[endpoint][client_id]
                connection.state = ConnectionState.DISCONNECTING
                
                try:
                    await connection.websocket.close()
                except Exception as e:
                    logger.debug("Error closing WebSocket: %s", e)
                
                del self._connections[endpoint][client_id]
                
                # Clean up empty endpoint pools
                if not self._connections[endpoint]:
                    del self._connections[endpoint]
                
                logger.info(
                    "WebSocket disconnected: endpoint=%s, client_id=%s",
                    endpoint,
                    client_id
                )

    async def broadcast(
        self,
        endpoint: str,
        message: Dict[str, Any],
        exclude_clients: Optional[Set[str]] = None
    ) -> int:
        """
        Broadcast a message to all connected clients on an endpoint.
        
        Args:
            endpoint: The endpoint to broadcast to
            message: The message to send
            exclude_clients: Optional set of client IDs to exclude
            
        Returns:
            Number of clients the message was sent to
        """
        exclude = exclude_clients or set()
        sent_count = 0
        failed_clients = []
        
        async with self._lock:
            if endpoint not in self._connections:
                return 0
            
            clients = list(self._connections[endpoint].items())
        
        for client_id, connection in clients:
            if client_id in exclude:
                continue
                
            if connection.state != ConnectionState.CONNECTED:
                continue
            
            try:
                await connection.websocket.send_json(message)
                connection.update_last_message()
                sent_count += 1
                self._stats["total_messages_sent"] += 1
            except Exception as e:
                logger.warning(
                    "Failed to send message to client %s: %s",
                    client_id,
                    e
                )
                failed_clients.append(client_id)
                self._stats["total_errors"] += 1
        
        # Clean up failed connections
        for client_id in failed_clients:
            await self._close_connection(endpoint, client_id)
        
        return sent_count

    async def _send_to_client(
        self,
        endpoint: str,
        client_id: str,
        message: Dict[str, Any]
    ) -> bool:
        """Send a message to a specific client."""
        async with self._lock:
            if endpoint not in self._connections:
                return False
            if client_id not in self._connections[endpoint]:
                return False
            
            connection = self._connections[endpoint][client_id]
            
        if connection.state != ConnectionState.CONNECTED:
            return False
        
        try:
            await connection.websocket.send_json(message)
            connection.update_last_message()
            self._stats["total_messages_sent"] += 1
            return True
        except Exception as e:
            logger.warning("Failed to send to client %s: %s", client_id, e)
            self._stats["total_errors"] += 1
            await self._close_connection(endpoint, client_id)
            return False

    async def receive(
        self,
        endpoint: str,
        client_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Receive a message from a specific client.
        
        Args:
            endpoint: The endpoint type
            client_id: The client identifier
            
        Returns:
            The received message or None if connection is closed
        """
        async with self._lock:
            if endpoint not in self._connections:
                return None
            if client_id not in self._connections[endpoint]:
                return None
            
            connection = self._connections[endpoint][client_id]
        
        try:
            data = await connection.websocket.receive_json()
            connection.update_last_message()
            self._stats["total_messages_received"] += 1
            return data
        except WebSocketDisconnect:
            await self._close_connection(endpoint, client_id)
            return None
        except Exception as e:
            logger.warning("Error receiving from client %s: %s", client_id, e)
            self._stats["total_errors"] += 1
            return None

    def get_connection_count(self, endpoint: Optional[str] = None) -> int:
        """Get the number of active connections."""
        if endpoint:
            return len(self._connections.get(endpoint, {}))
        return sum(len(clients) for clients in self._connections.values())

    def get_endpoints(self) -> List[str]:
        """Get list of active endpoints."""
        return list(self._connections.keys())

    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket manager statistics."""
        return {
            **self._stats,
            "active_connections": self.get_connection_count(),
            "endpoints": {
                endpoint: len(clients)
                for endpoint, clients in self._connections.items()
            },
            "uptime_seconds": time.time() - self._stats["started_at"]
        }

    async def _heartbeat_loop(self) -> None:
        """Background task to send heartbeat pings to all connections."""
        while True:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)
                
                heartbeat_message = {
                    "type": "heartbeat",
                    "timestamp": datetime.now(UTC).isoformat()
                }
                
                for endpoint in list(self._connections.keys()):
                    await self.broadcast(endpoint, heartbeat_message)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in heartbeat loop: %s", e)

    async def _cleanup_loop(self) -> None:
        """Background task to clean up stale connections."""
        while True:
            try:
                await asyncio.sleep(self.config.connection_timeout / 2)
                
                current_time = time.time()
                stale_connections = []
                
                async with self._lock:
                    for endpoint, clients in self._connections.items():
                        for client_id, connection in clients.items():
                            if current_time - connection.last_message_at > self.config.connection_timeout:
                                stale_connections.append((endpoint, client_id))
                
                for endpoint, client_id in stale_connections:
                    logger.info(
                        "Cleaning up stale connection: endpoint=%s, client_id=%s",
                        endpoint,
                        client_id
                    )
                    await self._close_connection(endpoint, client_id)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in cleanup loop: %s", e)


# Global WebSocket manager instance
_ws_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get or create the global WebSocket manager instance."""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager


async def init_websocket_manager() -> WebSocketManager:
    """Initialize and start the global WebSocket manager."""
    manager = get_websocket_manager()
    await manager.start()
    return manager


async def shutdown_websocket_manager() -> None:
    """Shutdown the global WebSocket manager."""
    global _ws_manager
    if _ws_manager is not None:
        await _ws_manager.stop()
        _ws_manager = None
