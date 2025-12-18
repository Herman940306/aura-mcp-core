"""Semantic Intent Classifier for Aura IA MCP.

Uses lightweight LLM inference to classify user intents when keyword
matching fails. This enables natural language understanding without
hardcoding every possible phrase variation.

Architecture:
1. Fast keyword matching (no LLM) - handles obvious commands
2. Semantic classification (lightweight LLM) - handles ambiguous commands
3. Parameter extraction - extracts entities from the message

Project Creator: Herman Swanepoel
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import httpx


class Intent(Enum):
    """Supported intent categories."""
    
    # Home Automation
    HOME_LIGHT_CONTROL = "home_light_control"
    HOME_AC_CONTROL = "home_ac_control"
    HOME_STATUS = "home_status"
    HOME_SCENE = "home_scene"
    HOME_PRESENCE = "home_presence"
    HOME_ENERGY = "home_energy"
    HOME_COMFORT = "home_comfort"
    
    # Media Automation
    MEDIA_SEARCH = "media_search"
    MEDIA_DOWNLOAD = "media_download"
    MEDIA_QUEUE = "media_queue"
    MEDIA_CONFIRM = "media_confirm"
    MEDIA_STATS = "media_stats"
    
    # System/MCP
    SYSTEM_STATUS = "system_status"
    SYSTEM_TIME = "system_time"
    SYSTEM_WEATHER = "system_weather"
    SYSTEM_LOCATION = "system_location"
    SYSTEM_SEARCH = "system_search"
    SYSTEM_HELP = "system_help"
    SYSTEM_TOOLS = "system_tools"
    
    # General
    GENERAL_CHAT = "general_chat"
    UNKNOWN = "unknown"


@dataclass
class ClassifiedIntent:
    """Result of intent classification."""
    
    intent: Intent
    confidence: float
    parameters: dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""
    classification_time_ms: int = 0
    used_llm: bool = False


# Intent descriptions for the classifier prompt
INTENT_DESCRIPTIONS = {
    Intent.HOME_LIGHT_CONTROL: "Control lights - turn on/off, dim, change color. Params: room, action (on/off/toggle/dim), brightness",
    Intent.HOME_AC_CONTROL: "Control AC/aircon - temperature, mode, fan speed. Params: action (set_temp/set_mode/set_fan/status), temperature, mode (cool/heat/auto/dry/fan_only/off), fan (auto/low/medium/high/turbo)",
    Intent.HOME_STATUS: "Get home status - what lights are on, overall home state",
    Intent.HOME_SCENE: "Activate scenes - movie time, goodnight, leaving home, etc. Params: scene_name",
    Intent.HOME_PRESENCE: "Check who is home, presence detection",
    Intent.HOME_ENERGY: "Energy usage, power consumption reports",
    Intent.HOME_COMFORT: "Comfort analysis - temperature, humidity comfort levels",
    Intent.MEDIA_SEARCH: "Search for movies/shows without downloading. Params: query, media_type (movie/series/anime)",
    Intent.MEDIA_DOWNLOAD: "Download/add movies or shows. Params: query, media_type",
    Intent.MEDIA_QUEUE: "Check download queue status",
    Intent.MEDIA_CONFIRM: "Confirm a pending download",
    Intent.MEDIA_STATS: "Get media tracking statistics",
    Intent.SYSTEM_STATUS: "System health, service status",
    Intent.SYSTEM_TIME: "Current time, date, timezone queries. Params: timezone",
    Intent.SYSTEM_WEATHER: "Weather information. Params: location",
    Intent.SYSTEM_LOCATION: "User location queries",
    Intent.SYSTEM_SEARCH: "Web search. Params: query",
    Intent.SYSTEM_HELP: "Help, capabilities, what can you do",
    Intent.SYSTEM_TOOLS: "List available tools",
    Intent.GENERAL_CHAT: "General conversation, jokes, questions not fitting other categories",
}

# Room name variations for normalization
ROOM_ALIASES = {
    "bedroom": ["bedroom", "bed room", "my room", "master bedroom", "main bedroom"],
    "lounge": ["lounge", "living room", "living", "front room", "sitting room"],
    "kitchen": ["kitchen", "cooking area"],
    "bathroom": ["bathroom", "bath room", "ensuite", "en-suite", "toilet", "restroom"],
    "hallway": ["hallway", "hall", "passage", "corridor"],
    "study": ["study", "office", "server room", "work room"],
    "spare": ["spare room", "spare", "guest room", "guest bedroom", "guest"],
    "outside": ["outside", "front yard", "backyard", "back yard", "porch", "front door"],
    "scullery": ["scullery", "laundry", "utility"],
}

# AC mode variations
AC_MODE_ALIASES = {
    "cool": ["cool", "cooling", "cold", "colder"],
    "heat": ["heat", "heating", "warm", "warmer", "hot"],
    "auto": ["auto", "automatic", "smart"],
    "dry": ["dry", "dehumidify", "dehumidifier"],
    "fan_only": ["fan", "fan only", "fan mode", "ventilate"],
    "off": ["off", "turn off", "switch off", "stop"],
}


class IntentClassifier:
    """Semantic intent classifier using lightweight LLM inference."""
    
    def __init__(
        self,
        ollama_url: str | None = None,
        model: str = "phi3.5:3.8b",
        timeout: float = 10.0,
    ):
        """Initialize the classifier.
        
        Args:
            ollama_url: Ollama API URL
            model: Model to use for classification (should be fast)
            timeout: Request timeout in seconds
        """
        self.ollama_url = ollama_url or os.getenv(
            "OLLAMA_BASE_URL", "http://aura-ia-ollama:11434"
        )
        self.model = model
        self.timeout = timeout
        
        # Build classification prompt
        self._build_prompt_template()
    
    def _build_prompt_template(self):
        """Build the classification prompt template."""
        intent_list = "\n".join(
            f"- {intent.value}: {desc}"
            for intent, desc in INTENT_DESCRIPTIONS.items()
        )
        
        self.prompt_template = f"""You are an intent classifier. Classify the user message into ONE of these intents and extract parameters.

INTENTS:
{intent_list}

RULES:
1. Choose the MOST SPECIFIC intent that matches
2. Extract relevant parameters based on the intent
3. If unsure, use "general_chat"
4. Respond ONLY with valid JSON

OUTPUT FORMAT (JSON only, no markdown):
{{"intent": "intent_name", "confidence": 0.0-1.0, "parameters": {{}}}}

EXAMPLES:
User: "set ac to cool"
{{"intent": "home_ac_control", "confidence": 0.95, "parameters": {{"action": "set_mode", "mode": "cool"}}}}

User: "turn on bedroom light"
{{"intent": "home_light_control", "confidence": 0.98, "parameters": {{"room": "bedroom", "action": "on"}}}}

User: "what's the temperature"
{{"intent": "home_ac_control", "confidence": 0.85, "parameters": {{"action": "status"}}}}

User: "download dune"
{{"intent": "media_download", "confidence": 0.9, "parameters": {{"query": "dune", "media_type": "movie"}}}}

User: "tell me a joke"
{{"intent": "general_chat", "confidence": 0.95, "parameters": {{}}}}

User: "{{message}}"
"""
    
    def _normalize_room(self, text: str) -> str | None:
        """Normalize room name from various aliases."""
        text_lower = text.lower()
        for room, aliases in ROOM_ALIASES.items():
            if any(alias in text_lower for alias in aliases):
                return room
        return None
    
    def _normalize_ac_mode(self, text: str) -> str | None:
        """Normalize AC mode from various aliases."""
        text_lower = text.lower()
        for mode, aliases in AC_MODE_ALIASES.items():
            if any(alias in text_lower for alias in aliases):
                return mode
        return None
    
    def _extract_temperature(self, text: str) -> int | None:
        """Extract temperature value from text."""
        # Match patterns like "22", "22 degrees", "22°", "22c"
        patterns = [
            r"(\d{1,2})\s*(?:degrees?|°|c|celsius)?",
            r"(?:to|at)\s*(\d{1,2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                temp = int(match.group(1))
                if 15 <= temp <= 35:  # Reasonable AC range
                    return temp
        return None
    
    def _quick_classify(self, message: str) -> ClassifiedIntent | None:
        """Quick rule-based classification for obvious intents.
        
        Returns None if no confident match, allowing LLM fallback.
        This is the FAST PATH - no LLM call needed for these patterns.
        """
        msg = message.lower().strip()
        start = time.time()
        
        def _result(intent: Intent, confidence: float, params: dict = None) -> ClassifiedIntent:
            return ClassifiedIntent(
                intent=intent,
                confidence=confidence,
                parameters=params or {},
                classification_time_ms=int((time.time() - start) * 1000),
                used_llm=False,
            )
        
        # ─────────────────────────────────────────────────────────────────────
        # LIGHT CONTROL
        # ─────────────────────────────────────────────────────────────────────
        
        # Check if this is a light-related command
        is_light_cmd = re.search(r"(light|lamp|bedroom|lounge|kitchen|bathroom|hallway|study|spare|outside)", msg) and \
                       re.search(r"(turn|switch|on|off)", msg)
        
        if is_light_cmd:
            # Determine action - check for "off" anywhere in message
            action = "off" if " off" in msg else "on"
            room = self._normalize_room(msg)
            # Handle "all" lights
            if "all" in msg and not room:
                room = "all"
            return _result(Intent.HOME_LIGHT_CONTROL, 0.95, {"action": action, "room": room})
        
        # "lights on/off" (all lights) - standalone
        if re.search(r"^lights?\s+(on|off)$|^(all\s+)?lights\s+(on|off)", msg):
            action = "on" if " on" in msg else "off"
            return _result(Intent.HOME_LIGHT_CONTROL, 0.9, {"action": action, "room": "all"})
        
        # ─────────────────────────────────────────────────────────────────────
        # AC / CLIMATE CONTROL
        # ─────────────────────────────────────────────────────────────────────
        
        # AC status query - multiple patterns
        if re.search(r"(ac|aircon|air\s*con)\s*(status|temp|temperature)|what.*(ac|aircon).*(temp|set)|how\s*(cold|hot|warm)", msg):
            return _result(Intent.HOME_AC_CONTROL, 0.9, {"action": "status"})
        
        # "set mode X" or "mode X" or "ac X" where X is a mode
        # NOTE: "off" only counts as AC mode if "ac/aircon" is mentioned
        mode_pattern = r"(cool|heat|dry|fan)"  # Exclude auto/off - too ambiguous
        if re.search(rf"(set\s+)?(ac|aircon)\s*(mode\s+)?{mode_pattern}|{mode_pattern}\s+mode|(ac|aircon)\s+(off|auto)", msg):
            mode = self._normalize_ac_mode(msg)
            if mode:
                return _result(Intent.HOME_AC_CONTROL, 0.9, {"action": "set_mode", "mode": mode})
        
        # "set ac to cool/heat/etc" - very common pattern
        if re.search(r"(set|change|put|switch).*(ac|aircon|air\s*con).*(to|mode)", msg):
            mode = self._normalize_ac_mode(msg)
            if mode:
                return _result(Intent.HOME_AC_CONTROL, 0.9, {"action": "set_mode", "mode": mode})
        
        # AC temperature control - "set temp to 22" or "22 degrees"
        if re.search(r"(set|change).*(ac|aircon|temp|temperature).*\d|ac.*\d.*degree|\d+\s*degree", msg):
            temp = self._extract_temperature(msg)
            if temp:
                return _result(Intent.HOME_AC_CONTROL, 0.9, {"action": "set_temp", "temperature": temp})
        
        # Fan speed control
        if re.search(r"(fan\s*(speed|mode)|set\s*fan).*(auto|low|medium|high|turbo)", msg):
            fan_match = re.search(r"(auto|low|medium|high|turbo)", msg)
            if fan_match:
                return _result(Intent.HOME_AC_CONTROL, 0.9, {"action": "set_fan", "fan": fan_match.group(1)})
        
        # ─────────────────────────────────────────────────────────────────────
        # HOME STATUS
        # ─────────────────────────────────────────────────────────────────────
        
        # Only match status queries, not "is X off?" which should be light control
        if re.search(r"home\s*status|house\s*status|what\s*lights\s*(are\s*)?(on|off)?$|what.*(is|are)\s+(on|off)\s*$", msg):
            # But not if it's asking about a specific room's light
            if not re.search(r"(bedroom|lounge|kitchen|bathroom|hallway|study|spare|outside).*(on|off)", msg):
                return _result(Intent.HOME_STATUS, 0.95)
        
        # ─────────────────────────────────────────────────────────────────────
        # SCENES
        # ─────────────────────────────────────────────────────────────────────
        
        if re.search(r"(activate|run|start|set)\s*(scene|mode)\s+\w+|goodnight|movie\s*(time|mode)|leaving\s*home", msg):
            scene_match = re.search(r"(goodnight|movie|leaving|morning|evening|party|romantic)", msg)
            scene = scene_match.group(1) if scene_match else None
            return _result(Intent.HOME_SCENE, 0.9, {"scene_name": scene})
        
        # ─────────────────────────────────────────────────────────────────────
        # PRESENCE
        # ─────────────────────────────────────────────────────────────────────
        
        if re.search(r"who.*(home|here)|anyone\s*home|is\s*\w+\s*home", msg):
            return _result(Intent.HOME_PRESENCE, 0.95)
        
        # ─────────────────────────────────────────────────────────────────────
        # MEDIA AUTOMATION
        # ─────────────────────────────────────────────────────────────────────
        
        # Download queue status
        if re.search(r"what.*(download|queue)|download.*(status|queue)|what.*(downloading)", msg):
            return _result(Intent.MEDIA_QUEUE, 0.95)
        
        # Media download request
        if re.search(r"(download|get\s*me|add)\s+(the\s+)?(movie|show|series|anime)?\s*['\"]?[\w\s]+", msg):
            # Extract query - everything after download/get me/add
            query_match = re.search(r"(?:download|get\s*me|add)\s+(?:the\s+)?(?:movie|show|series|anime)?\s*['\"]?(.+?)['\"]?\s*$", msg)
            query = query_match.group(1).strip() if query_match else None
            media_type = "movie" if "movie" in msg else "series" if ("show" in msg or "series" in msg) else "anime" if "anime" in msg else None
            return _result(Intent.MEDIA_DOWNLOAD, 0.85, {"query": query, "media_type": media_type})
        
        # Confirm download
        if re.search(r"confirm\s*(download|add)|yes\s*(download|add)", msg):
            return _result(Intent.MEDIA_CONFIRM, 0.95)
        
        # Media tracking stats
        if re.search(r"(tracking|media)\s*stats|download\s*history", msg):
            return _result(Intent.MEDIA_STATS, 0.95)
        
        # ─────────────────────────────────────────────────────────────────────
        # SYSTEM / TIME / WEATHER
        # ─────────────────────────────────────────────────────────────────────
        
        # Time query
        if re.search(r"what\s*time|current\s*time|time\s*is\s*it|what.*(date|day)", msg):
            return _result(Intent.SYSTEM_TIME, 0.95)
        
        # Weather query
        if "weather" in msg:
            location_match = re.search(r"weather\s+(?:in|for|at)\s+(.+?)(?:\?|$)", msg)
            location = location_match.group(1).strip() if location_match else None
            return _result(Intent.SYSTEM_WEATHER, 0.95, {"location": location} if location else {})
        
        # System status
        if re.search(r"system\s*status|service\s*status|health\s*check|are\s*you\s*(ok|working|alive)", msg):
            return _result(Intent.SYSTEM_STATUS, 0.95)
        
        # Help / capabilities
        if re.search(r"what\s*can\s*you\s*do|help|capabilities|commands|how\s*do\s*i", msg):
            return _result(Intent.SYSTEM_HELP, 0.9)
        
        # List tools
        if re.search(r"list\s*tools|what\s*tools|available\s*tools", msg):
            return _result(Intent.SYSTEM_TOOLS, 0.95)
        
        # ─────────────────────────────────────────────────────────────────────
        # GREETINGS (route to general chat quickly)
        # ─────────────────────────────────────────────────────────────────────
        
        if re.search(r"^(hi|hello|hey|good\s*(morning|afternoon|evening)|howdy|sup|yo)\s*[!?.]?\s*$", msg):
            return _result(Intent.GENERAL_CHAT, 0.95)
        
        # No confident quick match - will use LLM
        return None
    
    async def classify(self, message: str, use_llm: bool = True) -> ClassifiedIntent:
        """Classify user intent.
        
        Args:
            message: User message to classify
            use_llm: Whether to use LLM for ambiguous cases
            
        Returns:
            ClassifiedIntent with intent, confidence, and parameters
        """
        start = time.time()
        
        # Try quick rule-based classification first
        quick_result = self._quick_classify(message)
        if quick_result and quick_result.confidence >= 0.85:
            return quick_result
        
        # If LLM disabled or quick match found with lower confidence, return it
        if not use_llm:
            if quick_result:
                return quick_result
            return ClassifiedIntent(
                intent=Intent.GENERAL_CHAT,
                confidence=0.5,
                parameters={},
                classification_time_ms=int((time.time() - start) * 1000),
                used_llm=False,
            )
        
        # Use LLM for classification with retry logic
        max_retries = 2
        last_error = None
        
        for attempt in range(max_retries):
            try:
                prompt = self.prompt_template.replace("{message}", message)
                
                # Use shorter timeout for retries
                timeout = self.timeout if attempt == 0 else self.timeout * 0.7
                
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        f"{self.ollama_url}/api/generate",
                        json={
                            "model": self.model,
                            "prompt": prompt,
                            "stream": False,
                            "options": {
                                "temperature": 0.1,  # Low temp for consistent classification
                                "num_predict": 100,  # Short response - just need JSON
                                "num_ctx": 512,  # Small context for speed
                            },
                        },
                    )
                    
                    if response.status_code != 200:
                        print(f"⚠️ Intent classifier HTTP {response.status_code} (attempt {attempt + 1})")
                        last_error = f"HTTP {response.status_code}"
                        continue
                    
                    data = response.json()
                    raw_response = data.get("response", "").strip()
                    
                    # Parse JSON response
                    result = self._parse_llm_response(raw_response, message)
                    
                    # If parsing failed (general_chat with low confidence), retry
                    if result.intent == Intent.GENERAL_CHAT and result.confidence <= 0.5 and attempt < max_retries - 1:
                        print(f"⚠️ Low confidence parse, retrying... (attempt {attempt + 1})")
                        continue
                    
                    result.classification_time_ms = int((time.time() - start) * 1000)
                    result.used_llm = True
                    result.raw_response = raw_response
                    
                    print(f"🎯 Intent: {result.intent.value} ({result.confidence:.0%}) in {result.classification_time_ms}ms")
                    return result
                    
            except httpx.TimeoutException:
                print(f"⚠️ Intent classifier timeout (attempt {attempt + 1})")
                last_error = "timeout"
            except Exception as e:
                print(f"⚠️ Intent classification error (attempt {attempt + 1}): {e}")
                last_error = str(e)
        
        print(f"⚠️ Intent classification failed after {max_retries} attempts: {last_error}")
        return self._fallback_result(message, start)
    
    def _extract_json(self, text: str) -> dict | None:
        """Extract first valid JSON object from text, handling extra content.
        
        LLMs sometimes add explanatory text before/after JSON. This extracts
        just the JSON portion.
        """
        text = text.strip()
        
        # Remove markdown code blocks
        if "```" in text:
            text = re.sub(r"```(?:json)?\s*", "", text)
            text = text.strip()
        
        # Try direct parse first (fastest path)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Find JSON object boundaries
        start_idx = text.find("{")
        if start_idx == -1:
            return None
        
        # Find matching closing brace
        depth = 0
        end_idx = -1
        in_string = False
        escape_next = False
        
        for i, char in enumerate(text[start_idx:], start_idx):
            if escape_next:
                escape_next = False
                continue
            if char == "\\":
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        
        if end_idx == -1:
            return None
        
        json_str = text[start_idx:end_idx + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None
    
    def _parse_llm_response(self, response: str, original_message: str) -> ClassifiedIntent:
        """Parse LLM JSON response into ClassifiedIntent.
        
        Handles cases where LLM returns extra text before/after JSON.
        """
        # Extract JSON from response
        data = self._extract_json(response)
        
        if data is None:
            print(f"⚠️ No valid JSON found in response: {response[:200]}")
            return ClassifiedIntent(
                intent=Intent.GENERAL_CHAT,
                confidence=0.5,
                parameters={},
            )
        
        try:
            intent_str = data.get("intent", "general_chat")
            confidence = float(data.get("confidence", 0.5))
            parameters = data.get("parameters", {})
            
            # Map string to Intent enum
            try:
                intent = Intent(intent_str)
            except ValueError:
                # Try partial match for common typos
                intent_lower = intent_str.lower()
                matched = False
                for valid_intent in Intent:
                    if valid_intent.value in intent_lower or intent_lower in valid_intent.value:
                        intent = valid_intent
                        matched = True
                        break
                if not matched:
                    intent = Intent.GENERAL_CHAT
                    confidence = 0.5
            
            # Normalize parameters
            if "room" in parameters and parameters["room"]:
                normalized = self._normalize_room(str(parameters["room"]))
                if normalized:
                    parameters["room"] = normalized
            
            if "mode" in parameters and parameters["mode"]:
                normalized = self._normalize_ac_mode(str(parameters["mode"]))
                if normalized:
                    parameters["mode"] = normalized
            
            # Clamp confidence to valid range
            confidence = max(0.0, min(1.0, confidence))
            
            return ClassifiedIntent(
                intent=intent,
                confidence=confidence,
                parameters=parameters,
            )
            
        except Exception as e:
            print(f"⚠️ Error parsing intent data: {e}")
            return ClassifiedIntent(
                intent=Intent.GENERAL_CHAT,
                confidence=0.5,
                parameters={},
            )
    
    def _fallback_result(self, message: str, start_time: float) -> ClassifiedIntent:
        """Return fallback result when classification fails."""
        # Try quick classify one more time
        quick = self._quick_classify(message)
        if quick:
            return quick
        
        return ClassifiedIntent(
            intent=Intent.GENERAL_CHAT,
            confidence=0.5,
            parameters={},
            classification_time_ms=int((time.time() - start_time) * 1000),
            used_llm=False,
        )


# Singleton instance
_classifier: IntentClassifier | None = None


def get_intent_classifier() -> IntentClassifier:
    """Get or create the singleton intent classifier."""
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier
