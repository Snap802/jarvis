# jarvis.py
import os
import json
import subprocess
import time
import requests
import pyaudio
import pyttsx3
from vosk import Model, KaldiRecognizer

# -------- CONFIG ----------
MODEL_DIR = "D:/Jarvis/models/vosk/vosk-model-en-us-0.22"
OLLAMA_MODEL = "mistral:7b"  # or just "mistral" depending on your ollama setup
OLLAMA_API_URL = "http://localhost:11434/api/generate"

WHITELISTED_ACTIONS = {
    "open_notepad": {"cmd": ["notepad"]},
    "open_browser": {"cmd": ["start", "chrome"]},  # Windows
    "list_dir": {"cmd": ["dir"]},  # Windows (use ["ls", "-la"] for Linux)
    # add your allowed actions here
}
# ---------------------------

# TTS setup
tts = pyttsx3.init()
tts.setProperty("rate", 170)

# VOSK audio setup
CHUNK = 4096
RATE = 16000

def speak(text):
    """Speak text using TTS"""
    print("JARVIS:", text)
    tts.say(text)
    tts.runAndWait()

def query_ollama(prompt, max_tokens=200):
    """
    Query Ollama API with streaming disabled for simpler response handling.
    Returns the complete response text.
    """
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": max_tokens,
            }
        }
        
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        return result.get("response", "I couldn't generate a response.")
    
    except requests.exceptions.ConnectionError:
        return "Error: Could not connect to Ollama. Make sure Ollama is running (try 'ollama serve' in terminal)."
    except requests.exceptions.Timeout:
        return "Error: Request timed out."
    except Exception as e:
        return f"Error querying Ollama: {str(e)}"

def handle_action(command_text):
    """
    Parse and execute whitelisted system actions.
    """
    cmd_text = command_text.lower()
    action = None
    
    if "open notepad" in cmd_text or "notepad" in cmd_text:
        action = WHITELISTED_ACTIONS.get("open_notepad")
    elif "open browser" in cmd_text or "open chrome" in cmd_text:
        action = WHITELISTED_ACTIONS.get("open_browser")
    elif "list directory" in cmd_text or "list files" in cmd_text or "show files" in cmd_text:
        action = WHITELISTED_ACTIONS.get("list_dir")

    if action:
        speak("Executing action.")
        try:
            result = subprocess.run(
                action["cmd"], 
                capture_output=True, 
                text=True, 
                timeout=15,
                shell=True  # needed for Windows commands like 'dir' and 'start'
            )
            speak("Action completed.")
            if result.stdout:
                print(result.stdout)
        except Exception as e:
            speak(f"Action failed: {str(e)}")
    else:
        speak("No safe action identified for that command.")

def listen_once(device_index=None):
    """
    Listen for speech and return transcribed text.
    Set device_index to None to use default microphone, or specify your device index.
    """
    p = pyaudio.PyAudio()
    
    # Use default device if device_index is None
    stream_params = {
        "format": pyaudio.paInt16,
        "channels": 1,
        "rate": RATE,
        "input": True,
        "frames_per_buffer": CHUNK
    }
    if device_index is not None:
        stream_params["input_device_index"] = device_index
    
    stream = p.open(**stream_params)
    model = Model(MODEL_DIR)
    rec = KaldiRecognizer(model, RATE)
    rec.SetWords(True)

    print("Listening... (speak now, 5 second timeout)")
    start = time.time()
    timeout = 5

    try:
        while time.time() - start < timeout:
            data = stream.read(CHUNK, exception_on_overflow=False)
            if rec.AcceptWaveform(data):
                pass  # partial result
    except Exception as e:
        print(f"Error during recording: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

    # Get final transcription
    final = rec.FinalResult()
    try:
        j = json.loads(final)
        text = j.get("text", "")
    except Exception:
        text = ""
    
    return text.strip()

def main_loop():
    """Main interaction loop"""
    speak("Jarvis online. Press Enter to speak.")
    
    # Conversation history for context (optional)
    conversation_history = []
    
    while True:
        try:
            input("\n[Press Enter to speak...]\n")
            user_text = listen_once()  # Remove device_index parameter or set to your mic index
            
            if not user_text:
                speak("I didn't catch that. Try again.")
                continue
            
            print(f"\nYou said: {user_text}")
            
            # Check for exit commands
            if any(word in user_text.lower() for word in ["exit", "quit", "goodbye", "shut down"]):
                speak("Goodbye sir.")
                break
            
            # Build prompt for Ollama
            system_context = """You are JARVIS, an AI assistant. Be concise and helpful.
If the user asks you to perform a system action (open notepad, open browser, list files), 
respond naturally AND include 'ACTION:' followed by the action name on a new line.

Examples:
User: "Open notepad"
You: "Opening notepad for you, sir.
ACTION: open notepad"

User: "What's the weather like?"
You: "I don't have access to weather data, but you can check your local weather service."
"""
            
            prompt = f"{system_context}\n\nUser: {user_text}\nJARVIS:"
            
            # Query Ollama
            print("Thinking...")
            response = query_ollama(prompt, max_tokens=150)
            
            print(f"\nRaw response:\n{response}\n")
            
            # Check for action commands
            if "ACTION:" in response:
                parts = response.split("ACTION:", 1)
                speech_text = parts[0].strip()
                action_text = parts[1].strip()
                
                if speech_text:
                    speak(speech_text)
                
                print(f"Detected action: {action_text}")
                handle_action(action_text)
            else:
                speak(response)
            
        except KeyboardInterrupt:
            print("\nInterrupted by user.")
            speak("Shutting down.")
            break
        except Exception as e:
            print(f"Error: {e}")
            speak("An error occurred. Please try again.")

if __name__ == "__main__":
    print("="*50)
    print("JARVIS - AI Assistant")
    print("="*50)
    print("\nMake sure Ollama is running: ollama serve")
    print(f"Using model: {OLLAMA_MODEL}")
    print("="*50)
    
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\nGoodbye.")