# jarvis.py - Optimized for Low-End PC
import os
import json
import subprocess
import time
import requests
import pyttsx3
import pyaudio
from vosk import Model, KaldiRecognizer
import wave
import tempfile

# -------- CONFIG ----------
# Use the lightweight model - download vosk-model-small-en-us-0.15 or the "lgraph" variant
# lgraph models are faster: vosk-model-en-us-0.22-lgraph (128MB) - good balance
MODEL_DIR = "D:/Jarvis/models/vosk/vosk-model-small-en-us-0.15"

OLLAMA_MODEL = "mistral:7b"
OLLAMA_API_URL = "http://localhost:11434/api/generate"

# Reduce these if still too slow
OLLAMA_MAX_TOKENS = 100  # Reduced from 150

WHITELISTED_ACTIONS = {
    "open_notepad": {"cmd": ["notepad"]},
    "open_browser": {"cmd": ["start", "chrome"]},
    "list_dir": {"cmd": ["dir"]},
}
# ---------------------------

# TTS setup - optimize for speed
tts = pyttsx3.init()
tts.setProperty("rate", 180)  # Faster speech
voices = tts.getProperty('voices')
if voices:
    tts.setProperty('voice', voices[0].id)  # Use first voice (usually faster)

# Audio settings - optimized for low-end PC
CHUNK = 4096  # Smaller chunks = less memory
RATE = 16000
CHANNELS = 1

# Recognition settings
LISTEN_TIMEOUT = 8  # Give more time to speak

# Global model variable to load once
vosk_model = None

def load_model():
    """Load Vosk model once at startup"""
    global vosk_model
    if vosk_model is None:
        print("Loading speech model (one-time load)...")
        vosk_model = Model(MODEL_DIR)
        print("✓ Model loaded")
    return vosk_model

def find_working_mic(p):
    """Find the first working microphone"""
    for i in range(p.get_device_count()):
        try:
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                # Try to open it
                test_stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK,
                    input_device_index=i
                )
                test_stream.close()
                print(f"✓ Using microphone: {info['name']}")
                return i
        except:
            continue
    return None

def list_all_mics():
    """List all audio devices with detailed info"""
    p = pyaudio.PyAudio()
    print("\n" + "="*60)
    print("AUDIO DEVICES:")
    print("="*60)
    
    working_mics = []
    
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        print(f"\nDevice {i}: {info['name']}")
        print(f"  Max Input Channels: {info['maxInputChannels']}")
        print(f"  Max Output Channels: {info['maxOutputChannels']}")
        print(f"  Default Sample Rate: {int(info['defaultSampleRate'])}")
        
        if info['maxInputChannels'] > 0:
            # Test if it actually works
            try:
                test_stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    frames_per_buffer=1024,
                    input_device_index=i
                )
                test_stream.close()
                print("  ✓ WORKING INPUT DEVICE")
                working_mics.append(i)
            except Exception as e:
                print(f"  ✗ Error: {str(e)[:50]}")
    
    print("="*60)
    p.terminate()
    
    return working_mics

def speak(text):
    """Speak text using TTS"""
    if not text:
        return
    print(f"JARVIS: {text}")
    try:
        tts.say(text)
        tts.runAndWait()
    except:
        print("(TTS error, continuing...)")

def query_ollama(prompt, max_tokens=100):
    """Query Ollama - optimized for low-end PC"""
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": max_tokens,
                "num_ctx": 2048,  # Reduced context window
                "num_thread": 4,  # Use all 4 cores of i5-6500T
            }
        }
        
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=45)
        response.raise_for_status()
        
        result = response.json()
        text = result.get("response", "Error generating response.")
        # Clean up response
        text = text.strip()
        return text
    
    except requests.exceptions.ConnectionError:
        return "Ollama not running. Start it with: ollama serve"
    except requests.exceptions.Timeout:
        return "Response timed out. Try a simpler question."
    except Exception as e:
        return f"Error: {str(e)}"

def handle_action(command_text):
    """Execute whitelisted system actions"""
    cmd_text = command_text.lower()
    action = None
    
    if "notepad" in cmd_text or "text editor" in cmd_text:
        action = WHITELISTED_ACTIONS.get("open_notepad")
        speak("Opening notepad.")
    elif "browser" in cmd_text or "chrome" in cmd_text or "internet" in cmd_text or "web" in cmd_text:
        action = WHITELISTED_ACTIONS.get("open_browser")
        speak("Opening browser.")
    elif "list" in cmd_text or "files" in cmd_text or "directory" in cmd_text or "folder" in cmd_text:
        action = WHITELISTED_ACTIONS.get("list_dir")
        speak("Listing files.")

    if action:
        try:
            subprocess.Popen(action["cmd"], shell=True)
            time.sleep(0.5)
            speak("Done.")
            return True
        except Exception as e:
            speak("Failed.")
            print(f"Error: {e}")
            return False
    else:
        return False

def listen_once_optimized(device_index=None):
    """
    Optimized speech recognition for low-end PC
    - Loads model once globally
    - Uses smaller chunks
    - Stops on silence
    """
    model = load_model()
    
    p = pyaudio.PyAudio()
    
    # If no device specified, find a working one
    if device_index is None:
        device_index = find_working_mic(p)
        if device_index is None:
            print("ERROR: No working microphone found!")
            p.terminate()
            return ""
    
    stream_params = {
        "format": pyaudio.paInt16,
        "channels": CHANNELS,
        "rate": RATE,
        "input": True,
        "frames_per_buffer": CHUNK,
        "input_device_index": device_index
    }
    
    try:
        stream = p.open(**stream_params)
    except Exception as e:
        print(f"ERROR opening audio stream: {e}")
        print("Try running with microphone selection (list mics at startup)")
        p.terminate()
        return ""
    rec = KaldiRecognizer(model, RATE)
    rec.SetMaxAlternatives(0)
    rec.SetWords(False)  # Disable word-level timestamps for speed
    
    print("🎤 Speak now...")
    
    frames_recorded = 0
    max_frames = int(RATE / CHUNK * LISTEN_TIMEOUT)  # Max frames based on timeout
    silence_frames = 0
    silence_threshold = 15  # Wait longer before stopping (1.5s of silence)
    got_speech = False
    final_text = ""
    
    try:
        while frames_recorded < max_frames:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames_recorded += 1
            
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "")
                if text:
                    got_speech = True
                    final_text = text  # Store the recognized text
                    silence_frames = 0
                    print(f"  ✓ Got: {text[:50]}")
            else:
                partial = json.loads(rec.PartialResult())
                partial_text = partial.get("partial", "")
                if partial_text:
                    got_speech = True
                    silence_frames = 0
                    # Show what we're hearing
                    print(f"  Hearing: {partial_text[:50]}", end='\r')
                elif got_speech:
                    # Silence after speech detected
                    silence_frames += 1
                    if silence_frames > silence_threshold:
                        # Stop early if silence detected after speech
                        print("\n  (silence detected, stopping)")
                        break
        
        print()  # New line
        
    except Exception as e:
        print(f"Recording error: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

    # Get final result
    final_result = json.loads(rec.FinalResult())
    text = final_result.get("text", "").strip()
    
    # If final result is empty but we stored text from AcceptWaveform, use that
    if not text and final_text:
        text = final_text
    
    if not text and got_speech:
        print("⚠ Speech detected but transcription unclear")
    
    return text

def main_loop(mic_index=None):
    """Main loop - optimized"""
    
    # Pre-load model
    load_model()
    
    speak("Jarvis ready.")
    
    while True:
        try:
            input("\n[Enter to speak] ")
            
            # Listen
            user_text = listen_once_optimized(device_index=mic_index)
            
            if not user_text:
                print("(no speech detected)")
                continue
            
            print(f"✓ You: {user_text}\n")
            
            # Exit commands
            lower_text = user_text.lower()
            if any(x in lower_text for x in ["exit", "quit", "goodbye", "shut down"]):
                speak("Goodbye.")
                break
            
            # DIRECT COMMAND DETECTION - Check for actions FIRST before calling LLM
            action_keywords = {
                "notepad": ["notepad", "text editor", "open notepad"],
                "browser": ["browser", "chrome", "internet", "open chrome", "open browser", "web"],
                "list": ["list files", "show files", "list directory", "show directory"]
            }
            
            action_detected = False
            for action_type, keywords in action_keywords.items():
                if any(keyword in lower_text for keyword in keywords):
                    # Direct action execution without LLM
                    action_detected = handle_action(user_text)
                    if action_detected:
                        continue  # Skip LLM entirely
            
            if action_detected:
                continue  # Go to next loop iteration
            
            # If no direct action, use LLM for conversation
            prompt = f"""You are JARVIS, a concise AI assistant. Answer in 1-2 sentences maximum.

User: {user_text}
JARVIS:"""
            
            # Query LLM
            print("Thinking...")
            response = query_ollama(prompt, max_tokens=OLLAMA_MAX_TOKENS)
            
            # Clean up response and limit length for faster TTS
            response = response.strip()
            if len(response) > 250:
                response = response[:250] + "..."
            
            speak(response)
            
        except KeyboardInterrupt:
            speak("Shutting down.")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    print("="*50)
    print("JARVIS - Lightweight Mode")
    print("="*50)
    print(f"Model: {MODEL_DIR}")
    print(f"LLM: {OLLAMA_MODEL}")
    print("="*50)
    
    # Always list and test microphones first
    print("\nTesting audio devices...")
    working_mics = list_all_mics()
    
    if not working_mics:
        print("\n❌ ERROR: No working microphones found!")
        print("\nTroubleshooting:")
        print("1. Check if your microphone is plugged in")
        print("2. Check Windows Sound settings (right-click speaker icon)")
        print("3. Make sure mic isn't disabled in Device Manager")
        print("4. Try running as Administrator")
        input("\nPress Enter to exit...")
        exit(1)
    
    print(f"\n✓ Found {len(working_mics)} working microphone(s)")
    
    # Let user choose
    if len(working_mics) == 1:
        mic_idx = working_mics[0]
        print(f"Using device {mic_idx}")
    else:
        print(f"\nWorking devices: {working_mics}")
        choice = input(f"Select mic index (or Enter for {working_mics[0]}): ").strip()
        if choice.isdigit() and int(choice) in working_mics:
            mic_idx = int(choice)
        else:
            mic_idx = working_mics[0]
    
    print(f"\n✓ Selected microphone index: {mic_idx}")
    print("\n✓ Starting JARVIS...\n")
    
    try:
        main_loop(mic_index=mic_idx)
    except KeyboardInterrupt:
        print("\nBye.")