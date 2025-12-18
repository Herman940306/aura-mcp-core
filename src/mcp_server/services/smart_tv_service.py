"""
LG WebOS Smart TV Service for Aura IA MCP

Direct WebOS control for LG OLED55CXPVA (CX Series):
- Power on/off (Wake-on-LAN)
- Volume control
- Input switching
- App launching
- Remote button commands
- Screen notifications

Author: Herman Swanepoel
Created: December 14, 2025
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TVApp(str, Enum):
    """Common TV apps with their IDs."""
    NETFLIX = "netflix"
    YOUTUBE = "youtube.leanback.v4"
    PLEX = "cdp-30"
    AMAZON_PRIME = "amazon"
    DISNEY_PLUS = "com.disney.disneyplus-prod"
    APPLE_TV = "com.apple.appletv"
    SPOTIFY = "spotify-beehive"
    BROWSER = "com.webos.app.browser"
    SETTINGS = "com.webos.app.settings"
    LIVE_TV = "com.webos.app.livetv"
    HDMI1 = "com.webos.app.hdmi1"
    HDMI2 = "com.webos.app.hdmi2"
    HDMI3 = "com.webos.app.hdmi3"
    HDMI4 = "com.webos.app.hdmi4"


# App name aliases for natural language
APP_ALIASES: dict[str, TVApp] = {
    "netflix": TVApp.NETFLIX,
    "youtube": TVApp.YOUTUBE,
    "plex": TVApp.PLEX,
    "amazon": TVApp.AMAZON_PRIME,
    "prime": TVApp.AMAZON_PRIME,
    "disney": TVApp.DISNEY_PLUS,
    "disney+": TVApp.DISNEY_PLUS,
    "apple tv": TVApp.APPLE_TV,
    "spotify": TVApp.SPOTIFY,
    "browser": TVApp.BROWSER,
    "settings": TVApp.SETTINGS,
    "live tv": TVApp.LIVE_TV,
    "hdmi1": TVApp.HDMI1,
    "hdmi2": TVApp.HDMI2,
    "hdmi3": TVApp.HDMI3,
    "hdmi4": TVApp.HDMI4,
    "playstation": TVApp.HDMI1,
    "ps5": TVApp.HDMI1,
    "xbox": TVApp.HDMI2,
}


@dataclass
class TVConfig:
    """LG TV configuration."""
    ip_address: str = ""  # Set via SMART_TV_IP env var
    mac_address: str = ""  # Set via SMART_TV_MAC env var
    name: str = "LG OLED CX"
    client_key: str = ""
    timeout: float = 10.0
    ws_port: int = 3000


@dataclass
class TVState:
    """Current TV state."""
    is_on: bool = False
    volume: int = 0
    muted: bool = False
    current_app: str = ""
    current_app_name: str = ""


class SmartTVService:
    """LG WebOS Smart TV control service."""
    
    def __init__(self, config: Optional[TVConfig] = None):
        self.config = config or TVConfig(
            ip_address=os.getenv("SMART_TV_IP", ""),
            mac_address=os.getenv("SMART_TV_MAC", ""),
            client_key=os.getenv("SMART_TV_CLIENT_KEY", ""),
        )
        self._ws = None
        self._state = TVState()
        self._connected = False
        self._command_id = 0
        logger.info(f"SmartTVService initialized for {self.config.name} at {self.config.ip_address}")

    # ─────────────────────────────────────────────────────────────────────
    # CONNECTION MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────
    
    async def connect(self) -> bool:
        """Connect to TV via WebSocket."""
        try:
            import websockets
            uri = f"ws://{self.config.ip_address}:{self.config.ws_port}"
            self._ws = await asyncio.wait_for(
                websockets.connect(uri),
                timeout=self.config.timeout
            )
            await self._register()
            self._connected = True
            logger.info(f"Connected to TV at {self.config.ip_address}")
            return True
        except ImportError:
            logger.error("websockets library not installed")
            return False
        except asyncio.TimeoutError:
            logger.warning("TV connection timeout - TV may be off")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to TV: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from TV."""
        if self._ws:
            await self._ws.close()
            self._ws = None
        self._connected = False
    
    async def _register(self):
        """Register with TV (pairing handshake)."""
        registration = {
            "type": "register",
            "id": "register_0",
            "payload": {
                "forcePairing": False,
                "pairingType": "PROMPT",
                "client-key": self.config.client_key or "",
                "manifest": {
                    "manifestVersion": 1,
                    "appVersion": "1.1",
                    "permissions": [
                        "LAUNCH", "CONTROL_AUDIO", "CONTROL_DISPLAY",
                        "CONTROL_INPUT_MEDIA_PLAYBACK", "CONTROL_POWER",
                        "READ_APP_STATUS", "READ_RUNNING_APPS",
                        "WRITE_NOTIFICATION_TOAST", "READ_POWER_STATE"
                    ]
                }
            }
        }
        await self._ws.send(json.dumps(registration))
        response = await asyncio.wait_for(self._ws.recv(), timeout=30.0)
        data = json.loads(response)
        
        if data.get("type") == "registered":
            new_key = data.get("payload", {}).get("client-key", "")
            if new_key and new_key != self.config.client_key:
                self.config.client_key = new_key
                logger.info(f"TV paired! Client key: {new_key}")
            return True
        return False
    
    async def _send_command(self, uri: str, payload: Optional[dict] = None) -> dict:
        """Send a command to the TV."""
        if not self._connected:
            if not await self.connect():
                return {"error": "Not connected to TV"}
        
        self._command_id += 1
        message = {"type": "request", "id": f"cmd_{self._command_id}", "uri": uri}
        if payload:
            message["payload"] = payload
        
        try:
            await self._ws.send(json.dumps(message))
            response = await asyncio.wait_for(self._ws.recv(), timeout=self.config.timeout)
            return json.loads(response)
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return {"error": str(e)}
    
    # ─────────────────────────────────────────────────────────────────────
    # POWER CONTROL
    # ─────────────────────────────────────────────────────────────────────
    
    def wake_on_lan(self) -> bool:
        """Send Wake-on-LAN magic packet to turn on TV."""
        try:
            mac = self.config.mac_address.replace(":", "").replace("-", "")
            mac_bytes = bytes.fromhex(mac)
            magic_packet = b'\xff' * 6 + mac_bytes * 16
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(magic_packet, ('255.255.255.255', 9))
            sock.close()
            
            logger.info(f"WoL packet sent to {self.config.mac_address}")
            return True
        except Exception as e:
            logger.error(f"WoL failed: {e}")
            return False
    
    async def power_on(self) -> dict[str, Any]:
        """Turn on the TV using Wake-on-LAN."""
        success = self.wake_on_lan()
        if success:
            await asyncio.sleep(3)
            connected = await self.connect()
            return {"success": True, "message": "TV power on signal sent", "connected": connected}
        return {"success": False, "error": "Failed to send WoL packet"}
    
    async def power_off(self) -> dict[str, Any]:
        """Turn off the TV."""
        result = await self._send_command("ssap://system/turnOff")
        if "error" not in result:
            self._state.is_on = False
            await self.disconnect()
        return {"success": "error" not in result, "result": result}
    
    async def get_power_state(self) -> dict[str, Any]:
        """Check if TV is on."""
        try:
            result = await self._send_command("ssap://com.webos.service.tvpower/power/getPowerState")
            state = result.get("payload", {}).get("state", "Unknown")
            self._state.is_on = state in ["Active", "Screen On"]
            return {"is_on": self._state.is_on, "state": state}
        except Exception:
            return {"is_on": False, "state": "Off/Unreachable"}

    # ─────────────────────────────────────────────────────────────────────
    # VOLUME CONTROL
    # ─────────────────────────────────────────────────────────────────────
    
    async def get_volume(self) -> dict[str, Any]:
        """Get current volume."""
        result = await self._send_command("ssap://audio/getVolume")
        if "error" not in result:
            payload = result.get("payload", {})
            self._state.volume = payload.get("volume", 0)
            self._state.muted = payload.get("muted", False)
            return {"volume": self._state.volume, "muted": self._state.muted}
        return result
    
    async def set_volume(self, volume: int) -> dict[str, Any]:
        """Set volume (0-100)."""
        volume = max(0, min(100, volume))
        result = await self._send_command("ssap://audio/setVolume", {"volume": volume})
        if "error" not in result:
            self._state.volume = volume
        return {"success": "error" not in result, "volume": volume}
    
    async def volume_up(self) -> dict[str, Any]:
        """Increase volume."""
        return await self._send_command("ssap://audio/volumeUp")
    
    async def volume_down(self) -> dict[str, Any]:
        """Decrease volume."""
        return await self._send_command("ssap://audio/volumeDown")
    
    async def mute(self, muted: bool = True) -> dict[str, Any]:
        """Mute or unmute."""
        result = await self._send_command("ssap://audio/setMute", {"mute": muted})
        if "error" not in result:
            self._state.muted = muted
        return {"success": "error" not in result, "muted": muted}
    
    # ─────────────────────────────────────────────────────────────────────
    # APP CONTROL
    # ─────────────────────────────────────────────────────────────────────
    
    async def launch_app(self, app_id: str) -> dict[str, Any]:
        """Launch an app by ID."""
        # Check aliases
        if app_id.lower() in APP_ALIASES:
            app_id = APP_ALIASES[app_id.lower()].value
        
        result = await self._send_command("ssap://system.launcher/launch", {"id": app_id})
        return {"success": "error" not in result, "app": app_id, "result": result}
    
    async def get_current_app(self) -> dict[str, Any]:
        """Get currently running app."""
        result = await self._send_command("ssap://com.webos.applicationManager/getForegroundAppInfo")
        if "error" not in result:
            payload = result.get("payload", {})
            self._state.current_app = payload.get("appId", "")
            return {"app_id": self._state.current_app, "app_name": payload.get("appName", "")}
        return result
    
    async def get_app_list(self) -> dict[str, Any]:
        """Get list of installed apps."""
        result = await self._send_command("ssap://com.webos.applicationManager/listApps")
        if "error" not in result:
            apps = result.get("payload", {}).get("apps", [])
            return {"apps": [{"id": a.get("id"), "title": a.get("title")} for a in apps]}
        return result
    
    async def close_app(self, app_id: str) -> dict[str, Any]:
        """Close an app."""
        result = await self._send_command("ssap://system.launcher/close", {"id": app_id})
        return {"success": "error" not in result}
    
    # ─────────────────────────────────────────────────────────────────────
    # INPUT CONTROL
    # ─────────────────────────────────────────────────────────────────────
    
    async def get_inputs(self) -> dict[str, Any]:
        """Get available inputs."""
        result = await self._send_command("ssap://tv/getExternalInputList")
        if "error" not in result:
            inputs = result.get("payload", {}).get("devices", [])
            return {"inputs": [{"id": i.get("id"), "label": i.get("label")} for i in inputs]}
        return result
    
    async def set_input(self, input_id: str) -> dict[str, Any]:
        """Switch to an input (HDMI_1, HDMI_2, etc)."""
        result = await self._send_command("ssap://tv/switchInput", {"inputId": input_id})
        return {"success": "error" not in result, "input": input_id}
    
    # ─────────────────────────────────────────────────────────────────────
    # MEDIA CONTROL
    # ─────────────────────────────────────────────────────────────────────
    
    async def play(self) -> dict[str, Any]:
        """Play media."""
        return await self._send_command("ssap://media.controls/play")
    
    async def pause(self) -> dict[str, Any]:
        """Pause media."""
        return await self._send_command("ssap://media.controls/pause")
    
    async def stop(self) -> dict[str, Any]:
        """Stop media."""
        return await self._send_command("ssap://media.controls/stop")
    
    async def rewind(self) -> dict[str, Any]:
        """Rewind media."""
        return await self._send_command("ssap://media.controls/rewind")
    
    async def fast_forward(self) -> dict[str, Any]:
        """Fast forward media."""
        return await self._send_command("ssap://media.controls/fastForward")
    
    # ─────────────────────────────────────────────────────────────────────
    # NOTIFICATIONS
    # ─────────────────────────────────────────────────────────────────────
    
    async def show_notification(self, message: str) -> dict[str, Any]:
        """Show a toast notification on TV."""
        result = await self._send_command(
            "ssap://system.notifications/createToast",
            {"message": message}
        )
        return {"success": "error" not in result}
    
    # ─────────────────────────────────────────────────────────────────────
    # STATUS
    # ─────────────────────────────────────────────────────────────────────
    
    async def get_status(self) -> dict[str, Any]:
        """Get comprehensive TV status."""
        power = await self.get_power_state()
        if not power.get("is_on"):
            return {"is_on": False, "state": "Off/Unreachable"}
        
        volume = await self.get_volume()
        app = await self.get_current_app()
        
        return {
            "is_on": True,
            "volume": volume.get("volume"),
            "muted": volume.get("muted"),
            "current_app": app.get("app_name") or app.get("app_id"),
        }


# Global singleton
_tv_service: Optional[SmartTVService] = None


def get_smart_tv_service() -> SmartTVService:
    """Get or create the Smart TV service."""
    global _tv_service
    if _tv_service is None:
        _tv_service = SmartTVService()
    return _tv_service
