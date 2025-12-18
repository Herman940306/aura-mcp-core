"""Aura Voice Test - PC to MCP voice loop.

Tests the full voice pipeline:
1. Listen via PC microphone
2. Send text to MCP Gateway
3. Speak response via PC speakers (PL5)

Requirements:
    pip install SpeechRecognition pyttsx3 requests pyaudio

Usage:
    python aura_voice_test.py
"""

import speech_recognition as sr
import pyttsx3
import requests
import json

# Configuration - Set MCP_URL env var or update for your server
MCP_URL = os.getenv("MCP_URL", "http://localhost:9200/chat/send")
WAKE_WORD = "aura"  # Say "Aura" to activate

def speak(text: str, engine):
    """Speak text through speakers."""
    print(f"🔊 Aura: {text}")
    engine.say(text)
    engine.runAndWait()

def send_to_mcp(message: str) -> str:
    """Send message to MCP and get response."""
    try:
        response = requests.post(
            MCP_URL,
            json={"message": message, "mode": "auto"},
            timeout=60
        )
        data = response.json()
        
        if data.get("success"):
            resp = data.get("response", {})
            if isinstance(resp, dict):
                return resp.get("response", str(resp))
            return str(resp)
        else:
            return f"Error: {data.get('error', 'Unknown error')}"
    except Exception as e:
        return f"Connection error: {e}"

def listen(recognizer, mic) -> str | None:
    """Listen for speech and return text."""
    print("🎤 Listening...")
    try:
        with mic as source:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
        
        text = recognizer.recognize_google(audio)
        print(f"👤 You: {text}")
        return text.lower()
    except sr.WaitTimeoutError:
        return None
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        print(f"⚠️ Speech recognition error: {e}")
        return None

def main():
    print("=" * 50)
    print("🤖 Aura Voice Test")
    print(f"   MCP: {MCP_URL}")
    print(f"   Wake word: '{WAKE_WORD}'")
    print("   Say 'quit' or 'exit' to stop")
    print("=" * 50)
    
    # Initialize
    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    engine = pyttsx3.init()
    
    # Adjust for ambient noise
    print("🔧 Calibrating microphone...")
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
    
    speak("Aura voice test ready. Say Aura to activate.", engine)
    
    waiting_for_command = False
    
    while True:
        text = listen(recognizer, mic)
        
        if text is None:
            continue
        
        # Check for exit
        if text in ["quit", "exit", "stop", "goodbye"]:
            speak("Goodbye!", engine)
            break
        
        # Check for wake word
        if WAKE_WORD in text and not waiting_for_command:
            # Remove wake word from command
            command = text.replace(WAKE_WORD, "").strip()
            
            if command:
                # Wake word + command in same phrase
                print(f"📤 Sending: {command}")
                response = send_to_mcp(command)
                speak(response, engine)
            else:
                # Just wake word, wait for command
                speak("Yes?", engine)
                waiting_for_command = True
            continue
        
        if waiting_for_command:
            waiting_for_command = False
            print(f"📤 Sending: {text}")
            response = send_to_mcp(text)
            speak(response, engine)

if __name__ == "__main__":
    main()
