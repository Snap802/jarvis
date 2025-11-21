# jarvis.py
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import pyttsx3
import pyaudio
from vosk import Model, KaldiRecognizer

# -------- CONFIG ----------
MODEL_DIR = "D:/Jarvis/models/vosk/vosk-model-small-en-us-0.15"
LLAMA_CPP_EXE = "D:/Jarvis/llama.cpp/main.exe"
LLAMA_MODEL = "D:/Jarvis/models/llm/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
WHITELISTED_ACTIONS = {
    "open_notepad": {"cmd": ["notepad"]},            # example Windows
    "list_dir": {"cmd": ["ls", "-la"]},              # example linux
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
    print("JARVIS:", text)
    tts.say(text)
    tts.runAndWait()

def run_llama(prompt, max_tokens=200):
    """
    Call llama.cpp in interactive/prompt mode. We pass prompt via stdin and capture stdout.
    Adjust flags to match your build (this example assumes a typical main).
    """
    cmd = [
        LLAMA_CPP_EXE,
        "-m", LLAMA_MODEL,
        "-p", prompt,
        "-n", str(max_tokens),
        "--temp", "0.7",
        "--repeat_penalty", "1.1",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        out = result.stdout.strip()
        return out if out else "I couldn't generate a response."
    except subprocess.TimeoutExpired:
        return "Model timed out."

def handle_action(command_text):
    """
    Very small action parser: interpret special tokens from the LLM to run safe actions.
    For production, implement robust parsing and confirmation prompts.
    """
    cmd_text = command_text.lower()
    if "open notepad" in cmd_text or "open text editor" in cmd_text:
        action = WHITELISTED_ACTIONS.get("open_notepad")
    elif "list directory" in cmd_text or "list files" in cmd_text:
        action = WHITELISTED_ACTIONS.get("list_dir")
    else:
        action = None

    if action:
        speak("Okay, executing action.")
        try:
            out = subprocess.check_output(action["cmd"], stderr=subprocess.STDOUT, text=True, timeout=15)
            speak("Action completed.")
            print(out)
        except Exception as e:
            speak("Action failed: " + str(e))
    else:
        speak("No safe action identified.")

def listen_once():
    # open audio stream
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=CHUNK, input_device_index=17)
    model = Model(MODEL_DIR)
    rec = KaldiRecognizer(model, RATE)
    rec.SetWords(True)

    print("Listening... speak now (5 seconds).")
    frames = []
    start = time.time()
    timeout = 5  # seconds max for this prototype

    while time.time() - start < timeout:
        data = stream.read(CHUNK, exception_on_overflow=False)
        if rec.AcceptWaveform(data):
            res = rec.Result()
            frames.append(res)
        else:
            pass

    stream.stop_stream()
    stream.close()
    p.terminate()

    # get final transcription
    final = rec.FinalResult()
    # crude extraction of text
    import json
    try:
        j = json.loads(final)
        text = j.get("text", "")
    except Exception:
        text = ""
    return text

def main_loop():
    speak("Jarvis ready. Press Enter to speak.")
    while True:
        input("Press Enter to speak...")
        user_text = listen_once()
        if not user_text.strip():
            speak("I didn't catch that. Try again.")
            continue
        print("You said:", user_text)
        # Create a prompt for the model
        prompt = f"You are a helpful assistant named Jarvis. The user said: \"{user_text}\". Answer concisely. If the user asked to run a system action, output a line starting with ACTION: followed by the intent. Otherwise just answer normally."
        response = run_llama(prompt, max_tokens=150)
        print("Raw model response:\n", response)
        # simple action detection
        if "ACTION:" in response:
            # split
            parts = response.split("ACTION:", 1)
            say = parts[0].strip()
            act = parts[1].strip()
            if say:
                speak(say)
            print("Detected action:", act)
            handle_action(act)
        else:
            speak(response)

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("Bye.")
