"""
Home Assistant Integration Service for Aura IA MCP

Full bidirectional integration with Home Assistant:
- Control lights, switches, climate, scenes
- Query sensors, presence, weather
- Monitor energy usage
- Natural language command routing

Author: Herman Swanepoel
Created: December 14, 2025
Location: Brackenfell, Western Cape, South Africa
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class DeviceType(str, Enum):
    """Types of Home Assistant devices."""
    LIGHT = "light"
    SWITCH = "switch"
    CLIMATE = "climate"
    SENSOR = "sensor"
    SCENE = "scene"
    AUTOMATION = "automation"
    PERSON = "person"
    WEATHER = "weather"
    UNKNOWN = "unknown"


class TimeOfDay(str, Enum):
    """Time periods for smart automation."""
    MORNING = "morning"      # 5:00 - 11:59
    AFTERNOON = "afternoon"  # 12:00 - 17:59
    EVENING = "evening"      # 18:00 - 21:59
    NIGHT = "night"          # 22:00 - 4:59


@dataclass
class HAConfig:
    """Home Assistant configuration."""
    # Gateway proxy URL (preferred - works from any container)
    gateway_url: str = "http://aura-ia-gateway:8000"
    # Direct HA URL (only works from containers on macvlan network)
    base_url: str = ""  # Set via HA_URL env var
    # Fallback URL if primary fails
    fallback_url: str = ""  # Set via HA_FALLBACK_URL env var
    token: str = ""
    timeout: float = 30.0
    # Use gateway proxy (recommended for ML backend)
    use_gateway_proxy: bool = True
    # Smart defaults
    default_ac_temp_day: int = 22
    default_ac_temp_night: int = 24
    geyser_auto_off_hours: int = 2  # Auto-off after 2 hours


# Room name mappings to entity IDs
ROOM_MAPPINGS: dict[str, list[str]] = {
    # Master Bedroom
    "bedroom": ["switch.main_bedroom_switch_socket_1"],
    "master bedroom": ["switch.main_bedroom_switch_socket_1"],
    "my bedroom": ["switch.main_bedroom_switch_socket_1"],
    "main bedroom": ["switch.main_bedroom_switch_socket_1"],
    
    # En-suite Bathroom
    "bathroom": ["switch.main_bedroom_switch_socket_2"],
    "my bathroom": ["switch.main_bedroom_switch_socket_2"],
    "ensuite": ["switch.main_bedroom_switch_socket_2"],
    "en-suite": ["switch.main_bedroom_switch_socket_2"],
    "ensuite bathroom": ["switch.main_bedroom_switch_socket_2"],
    
    # Main Bathroom
    "main bathroom": ["switch.hallway_switch_socket_2"],
    
    # Kitchen
    "kitchen": ["switch.kitchen_switch_1", "switch.kitchen_switch_3"],
    "kitchen main": ["switch.kitchen_switch_1"],
    "kitchen big": ["switch.kitchen_switch_1"],
    "kitchen down": ["switch.kitchen_switch_3"],
    "kitchen small": ["switch.kitchen_switch_3"],
    "scullery": ["switch.kitchen_2_switch_socket_1"],
    "kitchen door": ["switch.kitchen_2_switch_socket_1"],
    
    # Lounge
    "lounge": ["switch.lounge_switch_socket_2"],
    "living room": ["switch.lounge_switch_socket_2"],
    
    # Hallway
    "hallway": ["switch.hallway_switch_socket_1"],
    "passage": ["switch.hallway_switch_socket_1"],
    
    # Study
    "study": ["switch.study_switch_socket_1"],
    "server room": ["switch.study_switch_socket_1"],
    "office": ["switch.study_switch_socket_1"],
    
    # Spare Room
    "spare room": ["switch.spare_room_switch_socket_1"],
    "guest room": ["switch.spare_room_switch_socket_1"],
    "guest bedroom": ["switch.spare_room_switch_socket_1"],
    
    # Outside
    "front yard": ["switch.lounge_switch_socket_1"],
    "porch": ["switch.lounge_switch_socket_1"],
    "front door": ["switch.lounge_switch_socket_1"],
    "backyard": ["switch.kitchen_switch_2"],
    "back yard": ["switch.kitchen_switch_2"],
    "outside": ["switch.lounge_switch_socket_1", "switch.kitchen_switch_2"],
    
    # All lights
    "all": ["switch.main_bedroom_switch_socket_1", "switch.main_bedroom_switch_socket_2",
            "switch.kitchen_switch_1", "switch.kitchen_switch_3", "switch.kitchen_2_switch_socket_1",
            "switch.lounge_switch_socket_2", "switch.hallway_switch_socket_1",
            "switch.study_switch_socket_1", "switch.spare_room_switch_socket_1"],
}

# Friendly names for entities
ENTITY_FRIENDLY_NAMES: dict[str, str] = {
    "switch.main_bedroom_switch_socket_1": "Bedroom Light",
    "switch.main_bedroom_switch_socket_2": "Bathroom Light",
    "switch.hallway_switch_socket_1": "Hallway Light",
    "switch.hallway_switch_socket_2": "Main Bathroom Light",
    "switch.kitchen_switch_1": "Kitchen Main Light",
    "switch.kitchen_switch_2": "Backyard Lights",
    "switch.kitchen_switch_3": "Kitchen Down Lights",
    "switch.kitchen_2_switch_socket_1": "Scullery Light",
    "switch.lounge_switch_socket_1": "Front Yard Light",
    "switch.lounge_switch_socket_2": "Lounge Light",
    "switch.spare_room_switch_socket_1": "Spare Room Light",
    "switch.study_switch_socket_1": "Study Light",
    "switch.geyser": "Geyser",
    "climate.room_air_conditioner": "AC",
}

# Smart scene definitions for contextual automation
SMART_SCENES: dict[str, dict] = {
    "movie_time": {
        "description": "Dim lights for movie watching",
        "actions": [
            {"entity": "switch.lounge_switch_socket_2", "action": "off"},
            {"entity": "switch.kitchen_switch_1", "action": "off"},
            {"entity": "switch.kitchen_switch_3", "action": "off"},
            {"entity": "climate.room_air_conditioner", "action": "climate", "mode": "cool", "temp": 22},
        ],
    },
    "goodnight": {
        "description": "Turn off all lights except security",
        "actions": [
            {"entity": "switch.main_bedroom_switch_socket_1", "action": "off"},
            {"entity": "switch.main_bedroom_switch_socket_2", "action": "off"},
            {"entity": "switch.lounge_switch_socket_2", "action": "off"},
            {"entity": "switch.kitchen_switch_1", "action": "off"},
            {"entity": "switch.kitchen_switch_3", "action": "off"},
            {"entity": "switch.kitchen_2_switch_socket_1", "action": "off"},
            {"entity": "switch.study_switch_socket_1", "action": "off"},
            {"entity": "switch.spare_room_switch_socket_1", "action": "off"},
            # Keep security lights on
            {"entity": "switch.lounge_switch_socket_1", "action": "on"},  # Front yard
            {"entity": "switch.kitchen_switch_2", "action": "on"},  # Backyard
        ],
    },
    "leaving_home": {
        "description": "Secure the house when leaving",
        "actions": [
            {"entity": "switch.main_bedroom_switch_socket_1", "action": "off"},
            {"entity": "switch.main_bedroom_switch_socket_2", "action": "off"},
            {"entity": "switch.lounge_switch_socket_2", "action": "off"},
            {"entity": "switch.kitchen_switch_1", "action": "off"},
            {"entity": "switch.kitchen_switch_3", "action": "off"},
            {"entity": "switch.kitchen_2_switch_socket_1", "action": "off"},
            {"entity": "switch.study_switch_socket_1", "action": "off"},
            {"entity": "switch.geyser", "action": "off"},
            {"entity": "climate.room_air_conditioner", "action": "climate", "mode": "off"},
        ],
    },
    "coming_home": {
        "description": "Welcome home setup",
        "actions": [
            {"entity": "switch.lounge_switch_socket_2", "action": "on"},
            {"entity": "switch.kitchen_switch_3", "action": "on"},
            {"entity": "climate.room_air_conditioner", "action": "climate", "mode": "cool", "temp": 23},
        ],
    },
    "wake_up": {
        "description": "Morning routine",
        "actions": [
            {"entity": "switch.main_bedroom_switch_socket_1", "action": "on"},
            {"entity": "switch.main_bedroom_switch_socket_2", "action": "on"},
            {"entity": "switch.kitchen_switch_1", "action": "on"},
            {"entity": "switch.geyser", "action": "on"},
        ],
    },
    "work_mode": {
        "description": "Study/work setup",
        "actions": [
            {"entity": "switch.study_switch_socket_1", "action": "on"},
            {"entity": "climate.room_air_conditioner", "action": "climate", "mode": "cool", "temp": 22},
        ],
    },
    "relax": {
        "description": "Relaxation mode - dim ambient lighting",
        "actions": [
            {"entity": "switch.kitchen_switch_1", "action": "off"},
            {"entity": "switch.kitchen_switch_3", "action": "on"},  # Down lights only
            {"entity": "switch.lounge_switch_socket_2", "action": "on"},
        ],
    },
}

# Energy monitoring thresholds
ENERGY_THRESHOLDS = {
    "ac_high_usage_kwh_day": 15.0,  # Alert if AC uses more than 15kWh/day
    "geyser_max_on_hours": 3,  # Warn if geyser on for more than 3 hours
}

# Comfort ranges
COMFORT_RANGES = {
    "temperature": {"min": 18, "max": 26, "ideal": 22},
    "humidity": {"min": 30, "max": 60, "ideal": 45},
}


@dataclass
class EntityState:
    """Represents the state of a Home Assistant entity."""
    entity_id: str
    state: str
    friendly_name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    last_changed: Optional[str] = None
    
    @property
    def is_on(self) -> bool:
        return self.state.lower() in ("on", "home", "cool", "heat", "auto", "dry", "fan_only")
    
    @property
    def is_available(self) -> bool:
        return self.state.lower() not in ("unavailable", "unknown")


class HomeAssistantService:
    """
    Home Assistant integration service.
    
    Provides:
    - Device control (lights, switches, climate)
    - State queries (sensors, presence)
    - Scene activation
    - Natural language command parsing
    """
    
    def __init__(self, config: Optional[HAConfig] = None):
        self.config = config or HAConfig(
            token=os.getenv("HA_TOKEN", ""),
            # Direct HA access (ML backend is on macvlan network)
            use_gateway_proxy=os.getenv("HA_USE_GATEWAY", "false").lower() == "true",
            gateway_url=os.getenv("HA_GATEWAY_URL", "http://aura-ia-gateway:8000"),
        )
        self._client: Optional[httpx.AsyncClient] = None
        self._entity_cache: dict[str, EntityState] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 30
        
        mode = "gateway proxy" if self.config.use_gateway_proxy else "direct"
        url = self.config.gateway_url if self.config.use_gateway_proxy else self.config.base_url
        logger.info(f"HomeAssistantService initialized: {url} (mode: {mode})")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client.
        
        Creates a fresh client for each call to avoid event loop issues.
        The client is lightweight and httpx handles connection pooling internally.
        """
        # Always create fresh client to avoid "Event loop is closed" errors
        # when client is reused across different async contexts
        headers = {"Content-Type": "application/json"}
        if not self.config.use_gateway_proxy:
            headers["Authorization"] = f"Bearer {self.config.token}"
        return httpx.AsyncClient(
            timeout=self.config.timeout,
            headers=headers
        )
    
    def _get_api_url(self, path: str) -> str:
        """Get the appropriate API URL based on mode."""
        if self.config.use_gateway_proxy:
            # Route through gateway proxy
            return f"{self.config.gateway_url}/api/ha{path}"
        else:
            # Direct HA access
            return f"{self.config.base_url}/api{path}"
    
    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    # ─────────────────────────────────────────────────────────────────────
    # STATE QUERIES
    # ─────────────────────────────────────────────────────────────────────
    
    async def get_all_states(self, use_cache: bool = True) -> list[EntityState]:
        """Get all entity states from Home Assistant."""
        # Check cache
        if use_cache and self._cache_time:
            age = (datetime.now() - self._cache_time).total_seconds()
            if age < self._cache_ttl_seconds and self._entity_cache:
                return list(self._entity_cache.values())
        
        client = await self._get_client()
        try:
            response = await client.get(self._get_api_url("/states"))
            
            if response.status_code == 200:
                states = []
                for item in response.json():
                    entity = EntityState(
                        entity_id=item.get("entity_id", ""),
                        state=item.get("state", "unknown"),
                        friendly_name=item.get("attributes", {}).get("friendly_name", ""),
                        attributes=item.get("attributes", {}),
                        last_changed=item.get("last_changed"),
                    )
                    states.append(entity)
                    self._entity_cache[entity.entity_id] = entity
                
                self._cache_time = datetime.now()
                return states
            else:
                logger.error(f"HA API error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to get HA states: {e}")
            return []
    
    async def get_entity_state(self, entity_id: str) -> Optional[EntityState]:
        """Get state of a specific entity."""
        client = await self._get_client()
        try:
            response = await client.get(self._get_api_url(f"/states/{entity_id}"))
            
            if response.status_code == 200:
                item = response.json()
                return EntityState(
                    entity_id=item.get("entity_id", ""),
                    state=item.get("state", "unknown"),
                    friendly_name=item.get("attributes", {}).get("friendly_name", ""),
                    attributes=item.get("attributes", {}),
                    last_changed=item.get("last_changed"),
                )
            return None
            
        except Exception as e:
            logger.error(f"Failed to get entity {entity_id}: {e}")
            return None
    
    # ─────────────────────────────────────────────────────────────────────
    # DEVICE CONTROL
    # ─────────────────────────────────────────────────────────────────────
    
    async def call_service(
        self,
        domain: str,
        service: str,
        entity_id: str,
        data: Optional[dict] = None
    ) -> dict[str, Any]:
        """Call a Home Assistant service."""
        client = await self._get_client()
        
        payload = {"entity_id": entity_id}
        if data:
            payload.update(data)
        
        try:
            response = await client.post(
                self._get_api_url(f"/services/{domain}/{service}"),
                json=payload
            )
            
            if response.status_code in [200, 201]:
                # Invalidate cache for this entity
                self._entity_cache.pop(entity_id, None)
                return {
                    "success": True,
                    "entity_id": entity_id,
                    "service": f"{domain}.{service}",
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                }
                
        except Exception as e:
            logger.error(f"Service call failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def turn_on(self, entity_id: str, **kwargs) -> dict[str, Any]:
        """Turn on a switch or light."""
        domain = entity_id.split(".")[0]
        return await self.call_service(domain, "turn_on", entity_id, kwargs or None)
    
    async def turn_off(self, entity_id: str) -> dict[str, Any]:
        """Turn off a switch or light."""
        domain = entity_id.split(".")[0]
        return await self.call_service(domain, "turn_off", entity_id)
    
    async def toggle(self, entity_id: str) -> dict[str, Any]:
        """Toggle a switch or light."""
        domain = entity_id.split(".")[0]
        return await self.call_service(domain, "toggle", entity_id)
    
    # ─────────────────────────────────────────────────────────────────────
    # CLIMATE CONTROL
    # ─────────────────────────────────────────────────────────────────────
    
    async def set_ac_temperature(self, temperature: float) -> dict[str, Any]:
        """Set AC temperature."""
        return await self.call_service(
            "climate", "set_temperature",
            "climate.room_air_conditioner",
            {"temperature": temperature}
        )
    
    async def set_ac_mode(self, mode: str) -> dict[str, Any]:
        """Set AC HVAC mode (off, cool, heat, dry, fan_only, auto)."""
        return await self.call_service(
            "climate", "set_hvac_mode",
            "climate.room_air_conditioner",
            {"hvac_mode": mode}
        )
    
    async def set_ac_fan_mode(self, fan_mode: str) -> dict[str, Any]:
        """Set AC fan mode (auto, low, medium, high, turbo)."""
        return await self.call_service(
            "climate", "set_fan_mode",
            "climate.room_air_conditioner",
            {"fan_mode": fan_mode}
        )
    
    async def get_ac_status(self) -> dict[str, Any]:
        """Get current AC status."""
        state = await self.get_entity_state("climate.room_air_conditioner")
        if not state:
            return {"error": "AC not available"}
        
        return {
            "mode": state.state,
            "current_temp": state.attributes.get("current_temperature"),
            "target_temp": state.attributes.get("temperature"),
            "humidity": state.attributes.get("humidity"),
            "fan_mode": state.attributes.get("fan_mode"),
            "preset_mode": state.attributes.get("preset_mode"),
        }
    
    # ─────────────────────────────────────────────────────────────────────
    # SCENES
    # ─────────────────────────────────────────────────────────────────────
    
    async def activate_scene(self, scene_id: str) -> dict[str, Any]:
        """Activate a scene."""
        if not scene_id.startswith("scene."):
            scene_id = f"scene.{scene_id}"
        return await self.call_service("scene", "turn_on", scene_id)
    
    # ─────────────────────────────────────────────────────────────────────
    # SENSORS & MONITORING
    # ─────────────────────────────────────────────────────────────────────
    
    async def get_temperature(self) -> dict[str, Any]:
        """Get room temperature from AC sensor."""
        state = await self.get_entity_state("sensor.room_air_conditioner_temperature")
        if state and state.is_available:
            return {
                "temperature": float(state.state),
                "unit": "°C",
                "source": "AC sensor",
            }
        return {"error": "Temperature sensor unavailable"}
    
    async def get_humidity(self) -> dict[str, Any]:
        """Get room humidity from AC sensor."""
        state = await self.get_entity_state("sensor.room_air_conditioner_humidity")
        if state and state.is_available:
            return {
                "humidity": float(state.state),
                "unit": "%",
                "source": "AC sensor",
            }
        return {"error": "Humidity sensor unavailable"}
    
    async def get_energy_usage(self) -> dict[str, Any]:
        """Get AC energy usage."""
        total = await self.get_entity_state("sensor.room_air_conditioner_energy")
        power = await self.get_entity_state("sensor.room_air_conditioner_power")
        
        return {
            "total_energy_kwh": float(total.state) if total and total.is_available else None,
            "current_power_w": float(power.state) if power and power.is_available else None,
        }
    
    async def get_weather(self) -> dict[str, Any]:
        """Get current weather."""
        state = await self.get_entity_state("weather.forecast_home_4")
        if not state:
            return {"error": "Weather unavailable"}
        
        return {
            "condition": state.state,
            "temperature": state.attributes.get("temperature"),
            "humidity": state.attributes.get("humidity"),
            "wind_speed": state.attributes.get("wind_speed"),
            "pressure": state.attributes.get("pressure"),
        }
    
    async def get_presence(self) -> dict[str, Any]:
        """Get presence information."""
        states = await self.get_all_states()
        persons = [s for s in states if s.entity_id.startswith("person.")]
        
        result = {
            "anyone_home": False,
            "persons": [],
        }
        
        for person in persons:
            info = {
                "name": person.friendly_name or person.entity_id.split(".")[1],
                "state": person.state,
                "home": person.state == "home",
            }
            if person.attributes.get("latitude"):
                info["location"] = {
                    "lat": person.attributes.get("latitude"),
                    "lon": person.attributes.get("longitude"),
                }
            result["persons"].append(info)
            if person.state == "home":
                result["anyone_home"] = True
        
        return result

    # ─────────────────────────────────────────────────────────────────────
    # SMART AUTOMATION & INTELLIGENCE
    # ─────────────────────────────────────────────────────────────────────

    def get_time_of_day(self) -> TimeOfDay:
        """Get current time period."""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return TimeOfDay.MORNING
        elif 12 <= hour < 18:
            return TimeOfDay.AFTERNOON
        elif 18 <= hour < 22:
            return TimeOfDay.EVENING
        else:
            return TimeOfDay.NIGHT

    async def execute_smart_scene(self, scene_name: str) -> dict[str, Any]:
        """Execute a smart scene with multiple coordinated actions."""
        scene = SMART_SCENES.get(scene_name.lower().replace(" ", "_"))
        if not scene:
            return {
                "success": False,
                "error": f"Unknown scene: {scene_name}",
                "available_scenes": list(SMART_SCENES.keys()),
            }

        results = []
        for action in scene["actions"]:
            entity = action["entity"]
            
            if action["action"] == "on":
                result = await self.turn_on(entity)
            elif action["action"] == "off":
                result = await self.turn_off(entity)
            elif action["action"] == "climate":
                if action.get("mode"):
                    await self.set_ac_mode(action["mode"])
                if action.get("temp"):
                    result = await self.set_ac_temperature(action["temp"])
                else:
                    result = {"success": True}
            else:
                result = {"success": False, "error": f"Unknown action: {action['action']}"}
            
            results.append({
                "entity": ENTITY_FRIENDLY_NAMES.get(entity, entity),
                "action": action["action"],
                "success": result.get("success", False),
            })

        all_success = all(r["success"] for r in results)
        return {
            "success": all_success,
            "scene": scene_name,
            "description": scene["description"],
            "results": results,
        }

    async def get_comfort_analysis(self) -> dict[str, Any]:
        """Analyze current comfort levels and provide recommendations."""
        temp_data = await self.get_temperature()
        humidity_data = await self.get_humidity()
        weather = await self.get_weather()
        ac_status = await self.get_ac_status()

        analysis = {
            "comfort_score": 100,
            "issues": [],
            "recommendations": [],
        }

        # Temperature analysis
        if "error" not in temp_data:
            temp = temp_data["temperature"]
            ideal = COMFORT_RANGES["temperature"]["ideal"]
            
            if temp < COMFORT_RANGES["temperature"]["min"]:
                analysis["issues"].append(f"Room is cold ({temp}°C)")
                analysis["recommendations"].append("Consider turning on heating or raising AC temperature")
                analysis["comfort_score"] -= 20
            elif temp > COMFORT_RANGES["temperature"]["max"]:
                analysis["issues"].append(f"Room is warm ({temp}°C)")
                analysis["recommendations"].append("Consider lowering AC temperature or turning on fan")
                analysis["comfort_score"] -= 20
            
            analysis["temperature"] = {
                "current": temp,
                "ideal": ideal,
                "status": "optimal" if abs(temp - ideal) <= 2 else "suboptimal",
            }

        # Humidity analysis
        if "error" not in humidity_data:
            humidity = humidity_data["humidity"]
            
            if humidity < COMFORT_RANGES["humidity"]["min"]:
                analysis["issues"].append(f"Air is dry ({humidity}%)")
                analysis["comfort_score"] -= 10
            elif humidity > COMFORT_RANGES["humidity"]["max"]:
                analysis["issues"].append(f"Air is humid ({humidity}%)")
                analysis["recommendations"].append("Consider using AC dry mode")
                analysis["comfort_score"] -= 10
            
            analysis["humidity"] = {
                "current": humidity,
                "ideal": COMFORT_RANGES["humidity"]["ideal"],
                "status": "optimal" if COMFORT_RANGES["humidity"]["min"] <= humidity <= COMFORT_RANGES["humidity"]["max"] else "suboptimal",
            }

        # Weather-based recommendations
        if "error" not in weather:
            outside_temp = weather.get("temperature", 20)
            
            if outside_temp > 30 and ac_status.get("mode") == "off":
                analysis["recommendations"].append("It's hot outside - consider turning on AC")
            elif outside_temp < 15 and ac_status.get("mode") == "cool":
                analysis["recommendations"].append("It's cool outside - consider turning off AC")

        # Time-based recommendations
        time_of_day = self.get_time_of_day()
        if time_of_day == TimeOfDay.NIGHT and ac_status.get("target_temp", 22) < 23:
            analysis["recommendations"].append("Consider raising AC temp for comfortable sleep (23-24°C)")

        analysis["comfort_score"] = max(0, analysis["comfort_score"])
        return analysis

    async def get_energy_insights(self) -> dict[str, Any]:
        """Get energy usage insights and recommendations."""
        energy = await self.get_energy_usage()
        geyser = await self.get_entity_state("switch.geyser")
        ac_status = await self.get_ac_status()
        lights = await self.get_lights_status()

        insights = {
            "current_usage": {},
            "recommendations": [],
            "warnings": [],
        }

        # AC energy
        if energy.get("current_power_w") is not None:
            power = energy["current_power_w"]
            insights["current_usage"]["ac_power_w"] = power
            
            if power > 1500:
                insights["warnings"].append(f"AC using high power ({power}W)")

        if energy.get("total_energy_kwh") is not None:
            insights["current_usage"]["ac_total_kwh"] = energy["total_energy_kwh"]

        # Geyser status
        if geyser and geyser.is_on:
            insights["current_usage"]["geyser"] = "on"
            insights["recommendations"].append("Remember to turn off geyser after use to save energy")

        # Lights
        lights_on_count = lights.get("total_on", 0)
        insights["current_usage"]["lights_on"] = lights_on_count
        
        if lights_on_count > 5:
            insights["recommendations"].append(f"{lights_on_count} lights are on - consider turning off unused ones")

        # Time-based recommendations
        time_of_day = self.get_time_of_day()
        if time_of_day == TimeOfDay.NIGHT:
            if lights_on_count > 2:
                insights["recommendations"].append("It's nighttime - consider using fewer lights")

        return insights

    async def get_smart_suggestion(self) -> dict[str, Any]:
        """Get contextual smart suggestions based on current state."""
        time_of_day = self.get_time_of_day()
        presence = await self.get_presence()
        weather = await self.get_weather()
        ac_status = await self.get_ac_status()
        lights = await self.get_lights_status()
        geyser = await self.get_entity_state("switch.geyser")

        suggestions = []

        # Morning suggestions
        if time_of_day == TimeOfDay.MORNING:
            if geyser and not geyser.is_on:
                suggestions.append({
                    "action": "Turn on geyser",
                    "reason": "Morning - you might want hot water",
                    "command": "turn on geyser",
                })

        # Evening suggestions
        if time_of_day == TimeOfDay.EVENING:
            if lights.get("total_on", 0) == 0:
                suggestions.append({
                    "action": "Turn on some lights",
                    "reason": "It's evening and all lights are off",
                    "command": "turn on lounge light",
                })

        # Night suggestions
        if time_of_day == TimeOfDay.NIGHT:
            if lights.get("total_on", 0) > 3:
                suggestions.append({
                    "action": "Goodnight scene",
                    "reason": "It's late - time to wind down?",
                    "command": "goodnight",
                })

        # Weather-based
        if "error" not in weather:
            outside_temp = weather.get("temperature", 20)
            
            if outside_temp > 28 and ac_status.get("mode") == "off":
                suggestions.append({
                    "action": "Turn on AC",
                    "reason": f"It's {outside_temp}°C outside",
                    "command": "turn on ac",
                })

        # Presence-based
        if not presence.get("anyone_home"):
            if lights.get("total_on", 0) > 0 or (geyser and geyser.is_on):
                suggestions.append({
                    "action": "Leaving home scene",
                    "reason": "Nobody detected at home",
                    "command": "leaving home",
                })

        return {
            "time_of_day": time_of_day.value,
            "suggestions": suggestions,
            "context": {
                "anyone_home": presence.get("anyone_home"),
                "lights_on": lights.get("total_on", 0),
                "ac_mode": ac_status.get("mode"),
                "outside_temp": weather.get("temperature") if "error" not in weather else None,
            },
        }
    
    # ─────────────────────────────────────────────────────────────────────
    # LIGHT STATUS
    # ─────────────────────────────────────────────────────────────────────
    
    async def get_lights_status(self) -> dict[str, Any]:
        """Get status of all lights/switches."""
        states = await self.get_all_states()
        switches = [s for s in states if s.entity_id.startswith("switch.") and s.entity_id != "switch.geyser"]
        
        lights_on = []
        lights_off = []
        unavailable = []
        
        for switch in switches:
            name = ENTITY_FRIENDLY_NAMES.get(switch.entity_id, switch.friendly_name)
            if not switch.is_available:
                unavailable.append(name)
            elif switch.is_on:
                lights_on.append(name)
            else:
                lights_off.append(name)
        
        return {
            "on": lights_on,
            "off": lights_off,
            "unavailable": unavailable,
            "total_on": len(lights_on),
            "total_off": len(lights_off),
        }
    
    # ─────────────────────────────────────────────────────────────────────
    # NATURAL LANGUAGE PARSING
    # ─────────────────────────────────────────────────────────────────────
    
    def parse_room_from_message(self, message: str) -> list[str]:
        """Extract room/entity from natural language message."""
        msg_lower = message.lower()
        
        # Check each room mapping
        for room_name, entities in ROOM_MAPPINGS.items():
            if room_name in msg_lower:
                return entities
        
        # Check for specific entity mentions
        if "geyser" in msg_lower or "geezer" in msg_lower:
            return ["switch.geyser"]
        if "ac" in msg_lower or "air con" in msg_lower or "aircon" in msg_lower:
            return ["climate.room_air_conditioner"]
        
        return []
    
    def parse_action_from_message(self, message: str) -> tuple[str, dict]:
        """Extract action and parameters from message."""
        msg_lower = message.lower()
        
        # On/Off actions
        if any(word in msg_lower for word in ["turn on", "switch on", "enable", "activate"]):
            return "turn_on", {}
        if any(word in msg_lower for word in ["turn off", "switch off", "disable", "deactivate"]):
            return "turn_off", {}
        if "toggle" in msg_lower:
            return "toggle", {}
        
        # AC temperature
        temp_match = re.search(r"(\d+)\s*(?:degrees?|°|deg)", msg_lower)
        if temp_match:
            return "set_temperature", {"temperature": int(temp_match.group(1))}
        
        # AC mode
        if "cool" in msg_lower:
            return "set_hvac_mode", {"hvac_mode": "cool"}
        if "heat" in msg_lower:
            return "set_hvac_mode", {"hvac_mode": "heat"}
        if "fan only" in msg_lower or "fan mode" in msg_lower:
            return "set_hvac_mode", {"hvac_mode": "fan_only"}
        if "dry" in msg_lower:
            return "set_hvac_mode", {"hvac_mode": "dry"}
        if "auto" in msg_lower and "ac" in msg_lower:
            return "set_hvac_mode", {"hvac_mode": "auto"}
        
        # AC fan speed
        for fan in ["turbo", "high", "medium", "low"]:
            if f"fan {fan}" in msg_lower or f"{fan} fan" in msg_lower:
                return "set_fan_mode", {"fan_mode": fan}
        
        return "unknown", {}
    
    async def process_command(self, message: str) -> dict[str, Any]:
        """Process a natural language command."""
        entities = self.parse_room_from_message(message)
        action, params = self.parse_action_from_message(message)
        
        if not entities:
            return {
                "success": False,
                "error": "Could not identify which device to control",
                "hint": "Try: 'Turn on bedroom light' or 'Set AC to 22 degrees'",
            }
        
        if action == "unknown":
            return {
                "success": False,
                "error": "Could not understand the action",
                "hint": "Try: 'turn on', 'turn off', 'set to X degrees'",
            }
        
        results = []
        for entity_id in entities:
            if action == "turn_on":
                result = await self.turn_on(entity_id)
            elif action == "turn_off":
                result = await self.turn_off(entity_id)
            elif action == "toggle":
                result = await self.toggle(entity_id)
            elif action == "set_temperature":
                result = await self.set_ac_temperature(params["temperature"])
            elif action == "set_hvac_mode":
                result = await self.set_ac_mode(params["hvac_mode"])
            elif action == "set_fan_mode":
                result = await self.set_ac_fan_mode(params["fan_mode"])
            else:
                result = {"success": False, "error": f"Unknown action: {action}"}
            
            result["entity"] = ENTITY_FRIENDLY_NAMES.get(entity_id, entity_id)
            results.append(result)
        
        all_success = all(r.get("success") for r in results)
        return {
            "success": all_success,
            "action": action,
            "results": results,
        }
    
    # ─────────────────────────────────────────────────────────────────────
    # STATUS SUMMARY
    # ─────────────────────────────────────────────────────────────────────
    
    async def get_home_summary(self, include_suggestions: bool = True) -> str:
        """Get a human-readable home status summary with smart suggestions."""
        time_of_day = self.get_time_of_day()
        time_emoji = {"morning": "🌅", "afternoon": "☀️", "evening": "🌆", "night": "🌙"}.get(time_of_day.value, "🕐")
        
        lines = [f"🏠 **Home Status** {time_emoji} {time_of_day.value.title()}\n"]
        
        # Lights
        lights = await self.get_lights_status()
        if lights["on"]:
            lines.append(f"💡 **Lights on ({lights['total_on']}):** {', '.join(lights['on'])}")
        else:
            lines.append("💡 **Lights:** All off")
        
        # AC
        ac = await self.get_ac_status()
        if "error" not in ac:
            mode_emoji = {"cool": "❄️", "heat": "🔥", "off": "⭕", "dry": "💧", "fan_only": "🌀"}.get(ac["mode"], "🌡️")
            lines.append(f"\n{mode_emoji} **AC:** {ac['mode'].title()} at {ac['target_temp']}°C (Room: {ac['current_temp']}°C)")
            lines.append(f"   Fan: {ac['fan_mode']} | Humidity: {ac.get('humidity', 'N/A')}%")
        
        # Geyser
        geyser = await self.get_entity_state("switch.geyser")
        if geyser:
            geyser_emoji = "🔥" if geyser.is_on else "⭕"
            lines.append(f"\n{geyser_emoji} **Geyser:** {'On' if geyser.is_on else 'Off'}")
        
        # Weather
        weather = await self.get_weather()
        if "error" not in weather:
            condition = weather['condition'].replace('_', ' ').title()
            lines.append(f"\n🌤️ **Outside:** {condition}, {weather['temperature']}°C, {weather.get('humidity', 'N/A')}% humidity")
        
        # Presence
        presence = await self.get_presence()
        home_persons = [p["name"] for p in presence["persons"] if p["home"]]
        if home_persons:
            lines.append(f"\n👥 **Home:** {', '.join(home_persons)}")
        else:
            lines.append("\n👥 **Home:** Nobody detected")

        # Energy insights
        energy = await self.get_energy_usage()
        if energy.get("current_power_w") is not None and energy["current_power_w"] > 0:
            lines.append(f"\n⚡ **AC Power:** {energy['current_power_w']}W")

        # Smart suggestions
        if include_suggestions:
            suggestions = await self.get_smart_suggestion()
            if suggestions.get("suggestions"):
                lines.append("\n💡 **Suggestions:**")
                for s in suggestions["suggestions"][:3]:  # Max 3 suggestions
                    lines.append(f"   • {s['action']} - {s['reason']}")
                    lines.append(f"     Say: \"{s['command']}\"")

        return "\n".join(lines)

    async def get_detailed_report(self) -> dict[str, Any]:
        """Get a comprehensive home report with all data."""
        return {
            "timestamp": datetime.now().isoformat(),
            "time_of_day": self.get_time_of_day().value,
            "lights": await self.get_lights_status(),
            "climate": await self.get_ac_status(),
            "geyser": (await self.get_entity_state("switch.geyser")).state if await self.get_entity_state("switch.geyser") else "unknown",
            "weather": await self.get_weather(),
            "presence": await self.get_presence(),
            "energy": await self.get_energy_usage(),
            "comfort": await self.get_comfort_analysis(),
            "energy_insights": await self.get_energy_insights(),
            "suggestions": await self.get_smart_suggestion(),
        }


# Global singleton
_ha_service: Optional[HomeAssistantService] = None


def get_home_assistant_service() -> HomeAssistantService:
    """Get or create the Home Assistant service."""
    global _ha_service
    if _ha_service is None:
        _ha_service = HomeAssistantService()
    return _ha_service
