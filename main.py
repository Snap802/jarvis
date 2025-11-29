import queue
import sounddevice as sd
import vosk
import json
import pyttsx3
import requests
from datetime import datetime

# === Voice Engine ===
engine = pyttsx3.init()
engine.setProperty('rate', 170)
engine.setProperty('volume', 1.0)

def speak(text):
    print("Jarvis:", text)
    engine.say(text)
    engine.runAndWait()

# === Speech Recognition (Offline via Vosk) ===
MODEL_PATH = "D:\Jarvis\models\vosk\vosk-model-small-en-us-0.15"
sample_rate = 16000
model = vosk.Model(MODEL_PATH)
q = queue.Queue()

def callback(indata, frames, time, status):
    q.put(bytes(indata))

def listen():
    with sd.RawInputStream(samplerate=sample_rate, blocksize=8000, dtype='int16',
                           channels=1, callback=callback):
        rec = vosk.KaldiRecognizer(model, sample_rate)
        speak("Listening...")
        while True:
            data = q.get()
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "")
                if text:
                    print("You:", text)
                    return text.lower()

# === Local LLM (Ollama) ===
def generate_reply(prompt):
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "mistral::7b", "prompt": prompt},
            timeout=300
        )
        data = response.json()
        return data.get("response", "I couldn’t generate a response.")
    except Exception as e:
        print("Error:", e)
        return "Local model unavailable."

# === Main Loop ===
def main():
    speak("Jarvis is fully operational and offline.")
    while True:
        query = listen()
        if not query:
            continue
        if "stop" in query or "exit" in query:
            speak("Goodbye Neil.")
            break
        elif "time" in query:
            speak("The time is " + datetime.now().strftime("%I:%M %p"))
        elif "hello" in query:
            speak("Hello Neil, how can I help?")
        else:
            reply = generate_reply(query)
            speak(reply)

if __name__ == "__main__":
    main()
