# jarvis_integrated_v3.py - JARVIS: Tkinter GUI with Gradient + Vosk STT + pyttsx3 TTS

# --- Imports (same as before) ---
import os
import json
import subprocess
import time
import threading
import tkinter as tk
import math
import random
import pyttsx3
import pyaudio
from vosk import Model, KaldiRecognizer

# --- 1. CONFIGURATION (Same as before) ---
VOSK_MODEL_DIR = "D:/Jarvis/models/vosk/vosk-model-small-en-us-0.15" # Check your path!
OLLAMA_MODEL = "mistral:7b"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MAX_TOKENS = 100
CHUNK = 4096
RATE = 16000
# Update whitelisted actions to your actual list
WHITELISTED_ACTIONS = {
    "open_notepad": {"cmd": ["notepad"]},
    "open_browser": {"cmd": ["start", "chrome"]},
}

# --- Color Definitions for Gradient (HEX) ---
COLOR_MAP = {
    "idle": ["#00BFFF", "#0080FF", "#00FFFF"],   # Deep Sky Blue to Cyan
    "listening": ["#7CFC00", "#32CD32", "#ADFF2F"], # Lawn Green to Yellow Green
    "thinking": ["#FF4500", "#FF8C00", "#FFA500"], # Red-Orange to Orange
    "speaking": ["#0000FF", "#4169E1", "#1E90FF"] # Blue to Royal Blue
}

# --- 2. JARVIS GUI (Modified draw_morphing_circle) ---
class JarvisGUI:
    def __init__(self, root):
        self.root = root
        
        # Floating, Frameless, Draggable setup
        self.root.attributes('-transparentcolor', 'black') 
        self.root.attributes('-topmost', True)           
        self.root.overrideredirect(True)                  
        
        self.width, self.height = 300, 300
        self.root.geometry(f"{self.width}x{self.height}+100+100")
        
        self.canvas = tk.Canvas(self.root, width=self.width, height=self.height, bg='black', highlightthickness=0)
        self.canvas.pack()
        
        self.status_label = tk.Label(self.root, text="JARVIS", font=("Arial", 12, "bold"), fg="#00D9FF", bg="black")
        self.status_label.place(x=self.width//2, y=self.height-30, anchor="center")
        
        self.center_x, self.center_y, self.base_radius = self.width // 2, self.height // 2, 60
        self.angle = 0
        self.thinking, self.listening = False, False
        self.morph_points, self.morph_offsets, self.morph_targets = 8, [0] * 8, [0] * 8
        self.current_state = "idle" # Track current state for color lookup
        
        # Dragging setup
        self.drag_data = {"x": 0, "y": 0}
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        
        self.set_idle()
        self.animate()
        
    # Draggable Methods (same as before)
    def start_drag(self, event): self.drag_data["x"], self.drag_data["y"] = event.x, event.y
    def on_drag(self, event):
        dx, dy = event.x - self.drag_data["x"], event.y - self.drag_data["y"]
        x, y = self.root.winfo_x() + dx, self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")
    
    # State Methods (modified to set current_state)
    def set_status(self, status): self.status_label.config(text=status)
    def set_idle(self):
        self.thinking, self.listening = False, False
        self.current_state = "idle"
        self.set_status("JARVIS - Idle")
    def set_listening(self):
        self.thinking, self.listening = False, True
        self.current_state = "listening"
        self.set_status("Listening...")
    def set_thinking(self):
        self.thinking, self.listening = True, False
        self.current_state = "thinking"
        self.set_status("Thinking...")
        for i in range(self.morph_points): self.morph_targets[i] = random.uniform(-15, 15)
    def set_speaking(self):
        self.thinking, self.listening = False, False
        self.current_state = "speaking"
        self.set_status("Speaking...")
    
    # *** MODIFIED: Draw Morphing Circle with Gradient ***
    def draw_morphing_circle(self):
        self.canvas.delete("all")
        
        # Update morph offsets smoothly
        for i in range(self.morph_points):
            diff = self.morph_targets[i] - self.morph_offsets[i]
            self.morph_offsets[i] += diff * 0.1
        
        # Calculate base radius with pulse/jiggle
        current_radius = self.base_radius
        if self.listening:
            current_radius += math.sin(self.angle * 2) * 10
        
        # --- Draw Concentric Gradient ---
        colors = COLOR_MAP[self.current_state]
        
        # The gradient is created by drawing a stack of transparent ovals
        # Each oval's size is based on the morphing shape
        
        for i in range(len(colors)):
            # Draw from inner to outer
            scale = 1.0 - (i * 0.2) 
            
            # Recalculate points for a smoother, layered morph
            points = []
            for j in range(self.morph_points):
                angle = (j / self.morph_points) * 2 * math.pi
                
                # Add jiggle when thinking
                jiggle = math.sin(self.angle * 3 + j) * 5 * scale if self.thinking else 0
                
                radius = current_radius * scale + self.morph_offsets[j] * scale + jiggle
                
                x = self.center_x + radius * math.cos(angle)
                y = self.center_y + radius * math.sin(angle)
                points.extend([x, y])
            
            # The innermost shape should be opaque (index 0)
            if i == 0:
                 fill_color = colors[i]
                 outline_width = 2
            else:
                 # Outer shapes provide the gradient / glow effect
                 fill_color = ""
                 outline_width = (len(colors) - i) * 3
                 
            self.canvas.create_polygon(
                points,
                fill=fill_color,
                outline=colors[i],
                width=outline_width,
                smooth=True
            )

        # Draw a bright center core (unchanged)
        core_size = 8
        if self.thinking:
            core_size += math.sin(self.angle * 5) * 3
        
        self.canvas.create_oval(
            self.center_x - core_size, self.center_y - core_size,
            self.center_x + core_size, self.center_y + core_size,
            fill="#FFFFFF", outline=""
        )
        
    def animate(self):
        self.angle += 0.1
        if self.thinking and random.random() > 0.95:
            idx = random.randint(0, self.morph_points - 1)
            self.morph_targets[idx] = random.uniform(-15, 15)
        if not self.thinking:
            for i in range(self.morph_points): self.morph_targets[i] *= 0.95
        
        self.draw_morphing_circle()
        self.root.after(33, self.animate)

# --- 3. BACKEND CORE & 4. CONTROLLER (Same as before, simplified) ---

# Global variables for speech engine and Vosk model
tts = pyttsx3.init()
tts.setProperty("rate", 180) 
vosk_model = None

def load_model():
    """Loads the Vosk model once."""
    global vosk_model
    if not os.path.isdir(VOSK_MODEL_DIR):
        raise FileNotFoundError(f"Vosk model not found at: {VOSK_MODEL_DIR}")
    if vosk_model is None:
        vosk_model = Model(VOSK_MODEL_DIR)

def speak(text, gui: JarvisGUI):
    """Speaks text and updates the GUI."""
    print("JARVIS:", text)
    gui.root.after(0, gui.set_speaking)
    
    def tts_thread():
        tts.say(text)
        tts.runAndWait()
        gui.root.after(0, gui.set_idle)

    threading.Thread(target=tts_thread, daemon=True).start()

def listen_once(gui: JarvisGUI, device_index=None):
    """Listens for a single phrase using Vosk."""
    if vosk_model is None: return ""
        
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=CHUNK, input_device_index=device_index)
    rec = KaldiRecognizer(vosk_model, RATE)
    
    gui.root.after(0, gui.set_listening)
    print("Listening...")

    for _ in range(0, int(RATE / CHUNK * 4)): 
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            if rec.AcceptWaveform(data): break
        except Exception: break

    stream.stop_stream(); stream.close(); p.terminate()
    
    final = rec.FinalResult()
    try:
        text = json.loads(final).get("text", "")
        print(f"✓ You: {text}")
        return text
    except Exception: return ""

def query_ollama(prompt):
    import requests
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "options": {"num_predict": OLLAMA_MAX_TOKENS}},
            timeout=30
        )
        data = response.json()
        return data.get("response", "Local model unavailable.").strip()
    except Exception as e:
        print(f"Ollama Error: {e}")
        return "I am having trouble connecting to the local model."

def handle_action(action_text):
    command = WHITELISTED_ACTIONS.get(action_text)
    if command:
        try:
            subprocess.Popen(command['cmd'], shell=True) 
            return "Command executed successfully."
        except Exception as e:
            return f"Failed to run command: {e}"
    return "Action not recognized."

class JarvisController:
    def __init__(self, gui: JarvisGUI, mic_index=None):
        self.gui = gui
        self.mic_index = mic_index
        self.running = True
        threading.Thread(target=self.run_loop, daemon=True).start()

    def run_loop(self):
        try:
            load_model()
        except FileNotFoundError as e:
            self.gui.root.after(0, lambda: self.gui.set_status("ERROR: Model Missing!"))
            return
            
        speak("Jarvis system online. Ready to serve.", self.gui)
        time.sleep(1)

        while self.running:
            time.sleep(2) 
            user_text = listen_once(self.gui, self.mic_index)
            
            if not user_text.strip():
                self.gui.root.after(0, self.gui.set_idle)
                continue

            lower_text = user_text.lower()
            
            if any(x in lower_text for x in ["exit", "shutdown", "goodbye"]):
                self.running = False
                speak("Goodbye. System shutting down.", self.gui)
                self.gui.root.after(1000, self.gui.root.quit)
                break

            self.gui.root.after(0, self.gui.set_thinking)
            
            prompt = f"You are a helpful and concise assistant named Jarvis. The user said: \"{user_text}\". Answer concisely. If the user asked to run a system action (like open notepad or list directory), output a single line starting with ACTION: followed by the action name exactly as defined in the list. Otherwise just answer normally."
            response = query_ollama(prompt)
            
            if "ACTION:" in response:
                parts = response.split("ACTION:", 1)
                speech_text = parts[0].strip()
                action_text = parts[1].strip()
                
                if speech_text: speak(speech_text, self.gui)
                
                action_result = handle_action(action_text)
                if not speech_text: speak(action_result, self.gui)
            else:
                speak(response, self.gui)
                
# --- 5. MAIN EXECUTION ---
if __name__ == "__main__":
    mic_index_to_use = None 
    
    root = tk.Tk()
    gui = JarvisGUI(root)
    controller = JarvisController(gui, mic_index_to_use)

    # Bind 'q' or 'Escape' to safely quit the application
    root.bind('q', lambda e: controller.running and gui.root.quit())
    root.bind('<Escape>', lambda e: controller.running and gui.root.quit())
    
    root.mainloop()