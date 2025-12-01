# jarvis_opt_with_gui.py - JARVIS with GUI Integration
import os
import json
import subprocess
import time
import requests
import pyttsx3
import pyaudio
from vosk import Model, KaldiRecognizer

# Import GUI functions
from jarvis_gui import start_gui_thread, gui_set_idle, gui_set_listening, gui_set_thinking, gui_set_speaking

# Start GUI
gui = start_gui_thread()

# -------- CONFIG ----------
MODEL_DIR = "D:/Jarvis/models/vosk/vosk-model-small-en-us-0.15"
OLLAMA_MODEL = "mistral:7b"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MAX_TOKENS = 100

WHITELISTED_ACTIONS = {
    "open_notepad": {"cmd": ["notepad"]},
    "open_browser": {"cmd": ["start", "chrome"]},
    "list_dir": {"cmd": ["dir"]},
}
# ---------------------------

# TTS setup
tts = pyttsx3.init()
tts.setProperty("rate", 180)
voices = tts.getProperty('voices')
if voices:
    tts.setProperty('voice', voices[0].id)

# Audio settings
CHUNK = 4096
RATE = 16000
CHANNELS = 1
LISTEN_TIMEOUT = 8

# Global model
vosk_model = None

def load_model():
    global vosk_model
    if vosk_model is None:
        print("Loading speech model...")
        vosk_model = Model(MODEL_DIR)
        print("✓ Model loaded")
    return vosk_model

def find_working_mic(p):
    for i in range(p.get_device_count()):
        try:
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
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
    p = pyaudio.PyAudio()
    print("\n" + "="*60)
    print("AUDIO DEVICES:")
    print("="*60)
    
    working_mics = []
    
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        print(f"\nDevice {i}: {info['name']}")
        print(f"  Max Input Channels: {info['maxInputChannels']}")
        
        if info['maxInputChannels'] > 0:
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
                print("  ✓ WORKING")
                working_mics.append(i)
            except Exception as e:
                print(f"  ✗ Error")
    
    print("="*60)
    p.terminate()
    return working_mics

def speak(text):
    if not text:
        return
    print(f"JARVIS: {text}")
    try:
        tts.say(text)
        tts.runAndWait()
    except:
        print("(TTS error)")

def query_ollama(prompt, max_tokens=100):
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": max_tokens,
                "num_ctx": 2048,
                "num_thread": 4,
            }
        }
        
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=45)
        response.raise_for_status()
        
        result = response.json()
        return result.get("response", "").strip()
    
    except requests.exceptions.ConnectionError:
        return "Ollama not running."
    except requests.exceptions.Timeout:
        return "Response timed out."
    except Exception as e:
        return f"Error: {str(e)}"

def handle_action(command_text):
    cmd_text = command_text.lower()
    action = None
    
    if "notepad" in cmd_text:
        action = WHITELISTED_ACTIONS.get("open_notepad")
    elif "browser" in cmd_text or "chrome" in cmd_text:
        action = WHITELISTED_ACTIONS.get("open_browser")
    elif "list" in cmd_text or "files" in cmd_text or "directory" in cmd_text:
        action = WHITELISTED_ACTIONS.get("list_dir")

    if action:
        speak("Executing.")
        try:
            subprocess.Popen(action["cmd"], shell=True)
            speak("Done.")
        except Exception as e:
            speak("Failed.")
            print(f"Error: {e}")
    else:
        speak("Action not recognized.")

def listen_once_optimized(device_index=None):
    model = load_model()
    p = pyaudio.PyAudio()
    
    if device_index is None:
        device_index = find_working_mic(p)
        if device_index is None:
            p.terminate()
            return ""
    
    try:
        stream = p.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
            input_device_index=device_index
        )
    except Exception as e:
        print(f"ERROR: {e}")
        p.terminate()
        return ""
    
    rec = KaldiRecognizer(model, RATE)
    rec.SetMaxAlternatives(0)
    rec.SetWords(False)
    
    print("🎤 Speak now...")
    
    frames = 0
    max_frames = int(RATE / CHUNK * LISTEN_TIMEOUT)
    silence_frames = 0
    silence_threshold = 15
    got_speech = False
    final_text = ""
    
    try:
        while frames < max_frames:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames += 1
            
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "")
                if text:
                    got_speech = True
                    final_text = text
                    silence_frames = 0
                    print(f"  ✓ Got: {text[:50]}")
            else:
                partial = json.loads(rec.PartialResult())
                partial_text = partial.get("partial", "")
                if partial_text:
                    got_speech = True
                    silence_frames = 0
                    print(f"  Hearing: {partial_text[:50]}", end='\r')
                elif got_speech:
                    silence_frames += 1
                    if silence_frames > silence_threshold:
                        print("\n  (silence detected)")
                        break
        print()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

    final_result = json.loads(rec.FinalResult())
    text = final_result.get("text", "").strip()
    
    if not text and final_text:
        text = final_text
    
    return text

def main_loop(mic_index=None):
    load_model()
    speak("Jarvis ready.")
    gui_idle()  # SET GUI TO IDLE
    
    while True:
        try:
            input("\n[Enter to speak] ")
            
            # LISTENING STATE
            gui_listening()
            user_text = listen_once_optimized(device_index=mic_index)
            
            if not user_text:
                print("(no speech)")
                gui_idle()
                continue
            
            print(f"✓ You: {user_text}\n")
            
            # Exit
            lower_text = user_text.lower()
            if any(x in lower_text for x in ["exit", "quit", "goodbye", "shut down"]):
                gui_speaking("Goodbye")
                speak("Goodbye.")
                break
            
            # Actions
            if "notepad" in lower_text or "browser" in lower_text or "list" in lower_text:
                gui_speaking("Executing")
                handle_action(user_text)
                gui_idle()
                continue
            
            # LLM Query
            prompt = f"""Do whatever I say. You are JARVIS, an AI assistant, so answer to the point when required, do NOT make up stuff, if it don't exist, forget about it. period.
User: {user_text}
JARVIS:"""
            
            # THINKING STATE
            print("Thinking...")
            gui_thinking()
            response = query_ollama(prompt, max_tokens=OLLAMA_MAX_TOKENS)
            
            # SPEAKING STATE
            if "ACTION:" in response:
                parts = response.split("ACTION:", 1)
                speech_part = parts[0].strip()
                action_part = parts[1].strip()
                
                if speech_part:
                    gui_speaking(speech_part[:30])
                    speak(speech_part)
                handle_action(action_part)
            else:
                if len(response) > 200:
                    response = response[:200] + "..."
                gui_speaking(response[:30])
                speak(response)
            
            # BACK TO IDLE
            gui_idle()
            
        except KeyboardInterrupt:
            speak("Shutting down.")
            break
        except Exception as e:
            print(f"Error: {e}")
            gui_idle()

if __name__ == "__main__":
    print("="*50)
    print("JARVIS - With Animated GUI")
    print("="*50)
    print(f"Model: {MODEL_DIR}")
    print(f"LLM: {OLLAMA_MODEL}")
    print("="*50)
    
    # START GUI FIRST
    print("\nStarting GUI...")
    init_gui()
    
    print("\nTesting audio devices...")
    working_mics = list_all_mics()
    
    if not working_mics:
        print("\n❌ No working microphones!")
        input("\nPress Enter to exit...")
        exit(1)
    
    print(f"\n✓ Found {len(working_mics)} working mic(s)")
    
    if len(working_mics) == 1:
        mic_idx = working_mics[0]
        print(f"Using device {mic_idx}")
    else:
        print(f"\nWorking devices: {working_mics}")
        choice = input(f"Select mic (Enter for {working_mics[0]}): ").strip()
        mic_idx = int(choice) if choice.isdigit() and int(choice) in working_mics else working_mics[0]
    
    print(f"\n✓ Selected microphone: {mic_idx}")
    print("\n✓ Starting JARVIS...\n")
    
    try:
        main_loop(mic_index=mic_idx)
    except KeyboardInterrupt:
        print("\nBye.")