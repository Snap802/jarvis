# jarvis_visual_test.py - SCALED 2X with DUAL-COLOR PARTICLE SWARM - FINAL VISUALS

import os
import sys
import json
import subprocess
import time
import math
import random
import threading
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw

# Core dependencies (Imported here to make the script self-contained)
import pyttsx3
import pyaudio
import requests 

# Vosk is optional but required for listening functionality
try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    print("Vosk not found. Speech recognition will be disabled.")

# -----------------------------------------------------------------------------
# --- 1. CONFIGURATION (SCALED & VISUAL TWEAKS) ---
# -----------------------------------------------------------------------------

# --- SCALING ---
SCALE_FACTOR = 2

# Tkinter/HUD Settings
WIDTH, HEIGHT = 300 * SCALE_FACTOR, 300 * SCALE_FACTOR # 600x600 window
FPS = 1000 
BG_COLOR_TK = 'black' 

# Particle Configuration
MAX_PARTICLES = 150 * SCALE_FACTOR 
PARTICLE_INIT_RADIUS_MIN = 5 * SCALE_FACTOR 
PARTICLE_INIT_RADIUS_MAX = 75 * SCALE_FACTOR 
PARTICLE_GROWTH_RATE = 1.6 
PARTICLE_POINT_SIZE = 2 

# Core and Ring Configuration
PULSE_RING_BASE_RADIUS = 65 * SCALE_FACTOR 
CORE_RING_BASE_RADIUS = 10 * SCALE_FACTOR 
CORE_PULSE_MAGNITUDE = 3 * SCALE_FACTOR   

# State Colors (HEX)
COLORS_HEX = {
    "idle": "#F0EC13",    # Primary Cyan (for Rings/Core Glow)
    "listening": "#00FF32", # Green
    "thinking": "#FF6400", # Orange
    "speaking": "#3264FF"  # Blue
}
# --- DUAL COLOR ---
SECONDARY_COLOR_HEX = "#FF00C8" # Deep Magenta (for Particles)

# Backend Config (Minimal, just to let the script run)
VOSK_MODEL_DIR = "D:/Jarvis/models/vosk/vosk-model-small-en-us-0.15" 
OLLAMA_MODEL = "mistral:7b"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MAX_TOKENS = 100
CHUNK = 4096
RATE = 16000
LISTEN_DURATION_SEC = 4
WHITELISTED_ACTIONS = {
    "open_notepad": {"cmd": ["notepad"]},
    "open_browser": {"cmd": ["start", "msedge"]},
}

# --- Global State ---
hud_state = {"state": "idle", "intensity": 0.5}

# -----------------------------------------------------------------------------
# --- 2. PARTICLE SYSTEM & PILLOW RENDERING (GUI) ---
# -----------------------------------------------------------------------------

class Particle:
    __slots__ = ('x', 'y', 'radius', 'angle', 'speed')

    def __init__(self, cx, cy):
        self.radius = random.uniform(PARTICLE_INIT_RADIUS_MIN, PARTICLE_INIT_RADIUS_MAX)
        self.angle = random.uniform(0, 2 * math.pi)
        self.x = cx + math.cos(self.angle) * self.radius
        self.y = cy + math.sin(self.angle) * self.radius
        self.speed = random.uniform(0.005, 0.01)

    def update(self, dt, cx, cy, intensity):
        self.angle += self.speed * 30 * intensity
        self.radius += PARTICLE_GROWTH_RATE * intensity
        self.x = cx + math.cos(self.angle) * self.radius
        self.y = cy + math.sin(self.angle) * self.radius

class JarvisGUI:
    def __init__(self, root):
        self.root = root
        
        # --- TKINTER WINDOW SETUP ---
        self.root.attributes('-transparentcolor', BG_COLOR_TK) 
        self.root.attributes('-topmost', True)           
        self.root.overrideredirect(True)                  
        self.root.geometry(f"{WIDTH}x{HEIGHT}+100+100")
        
        self.canvas = tk.Canvas(self.root, width=WIDTH, height=HEIGHT, 
                                bg=BG_COLOR_TK, highlightthickness=0)
        self.canvas.pack()
        
        # Status Label positioning scaled
        self.status_label = tk.Label(self.root, text="JARVIS", 
                                     font=("Arial", 12 * SCALE_FACTOR, "bold"), 
                                     fg=COLORS_HEX["idle"], bg=BG_COLOR_TK)
        self.status_label.place(x=WIDTH//2, y=HEIGHT - (30 * SCALE_FACTOR // 2), anchor="center")
        
        self.center_x, self.center_y = WIDTH // 2, HEIGHT // 2
        self.particles = []
        self.max_particles = MAX_PARTICLES
        self._photo = None 
        self.angle = 0
        
        # --- DRAGGABILITY FIX: Bind drag events to the root window ---
        self.drag_data = {"x": 0, "y": 0}
        self.root.bind("<ButtonPress-1>", self.start_drag) 
        self.root.bind("<B1-Motion>", self.on_drag)        
        
        self.animate()
        
    def start_drag(self, event): 
        self.drag_data["x"], self.drag_data["y"] = event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y()
    
    def on_drag(self, event):
        x = event.x_root - self.drag_data["x"]
        y = event.y_root - self.drag_data["y"]
        self.root.geometry(f"+{x}+{y}")
        
    def update_particles(self, intensity):
        """Updates and prunes particles."""
        self.particles = [p for p in self.particles if p.radius < self.center_x]
        
        current_max = int(self.max_particles * intensity)
        if len(self.particles) < current_max:
            for _ in range(5):
                if len(self.particles) < current_max:
                    self.particles.append(Particle(self.center_x, self.center_y))
        
        for p in self.particles:
            p.update(1, self.center_x, self.center_y, intensity) 

    def draw_hud_with_pillow(self, state, intensity):
        """Renders the HUD using Pillow for anti-aliasing and dual colors."""
        
        img = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # --- 1. Primary State Color (for Rings/Core Glow) ---
        current_color_hex = COLORS_HEX.get(state, COLORS_HEX["idle"])
        r, g, b = tuple(int(current_color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        
        # --- 2. Secondary Particle Color ---
        r2, g2, b2 = tuple(int(SECONDARY_COLOR_HEX.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))


        # 3. Draw the particles (using Secondary Color)
        for p in self.particles:
            alpha = max(0, 255 - int(p.radius * 255 / self.center_x))
            color_rgba = (r2, g2, b2, alpha) 
            
            p_size = PARTICLE_POINT_SIZE 
            box = (int(p.x - p_size), int(p.y - p_size), 
                   int(p.x + p_size), int(p.y + p_size))
            
            draw.ellipse(box, fill=color_rgba)
            
        # 4. Draw a static holographic circle outline (pulsing) (using Primary Color)
        pulse_base = PULSE_RING_BASE_RADIUS + (20 * SCALE_FACTOR * intensity)
        pulse = (math.sin(self.angle * 0.05) * (5 * SCALE_FACTOR)) + pulse_base
        
        outline_color = (r, g, b, 200) 
        
        r_int = int(pulse)
        box = [self.center_x - r_int, self.center_y - r_int,
               self.center_x + r_int, self.center_y + r_int]
               
        draw.ellipse(box, outline=outline_color, width=2)
        
        # 5. Draw the central core (ADAPTIVE FIX - 3 LAYER GLOW)
        core_size_base = CORE_RING_BASE_RADIUS + (CORE_PULSE_MAGNITUDE * intensity)
        core_size = (math.sin(self.angle * 0.1) * (CORE_PULSE_MAGNITUDE / 2)) + core_size_base
        
        # --- Layer 1: Outer Soft Aura (Primary Color, High Transparency) ---
        aura_size = core_size + (15 * SCALE_FACTOR)
        aura_box = [self.center_x - aura_size, self.center_y - aura_size,
                    self.center_x + aura_size, self.center_y + aura_size]
        # Use low alpha for a faint light spill
        draw.ellipse(aura_box, fill=(r, g, b, 50)) 
        
        # --- Layer 2: Inner Glow (Primary Color, Moderate Transparency) ---
        glow_size = core_size + (5 * SCALE_FACTOR)
        glow_box = [self.center_x - glow_size, self.center_y - glow_size,
                    self.center_x + glow_size, self.center_y + glow_size]
        # Use moderate alpha for the main glow effect
        draw.ellipse(glow_box, fill=(r, g, b, 150)) 
        
        # --- Layer 3: Opaque White Center (Visible on ANY background) ---
        white_core_size = core_size / 2
        white_core_box = [self.center_x - white_core_size, self.center_y - white_core_size,
                          self.center_x + white_core_size, self.center_y + white_core_size]
        # This solid white center provides the necessary contrast
        draw.ellipse(white_core_box, fill=(255, 255, 255, 255)) 

        # Convert Pillow Image to Tkinter PhotoImage and update canvas
        self._photo = ImageTk.PhotoImage(img)
        self.canvas.delete("HUDIMG")
        self.canvas.create_image(self.center_x, self.center_y, image=self._photo, tags="HUDIMG")
        
        # Update status label
        self.status_label.config(text=f" {state.capitalize()}", fg=current_color_hex)
        
    def animate(self):
        """Main animation loop driven by Tkinter."""
        self.angle += 1
        state, intensity = hud_state["state"], hud_state["intensity"]
        
        self.update_particles(intensity)
        self.draw_hud_with_pillow(state, intensity)
        
        self.root.after(int(1000 / FPS), self.animate)

# -----------------------------------------------------------------------------
# --- 3. BACKEND CORE (STT, TTS, LLM) --- (Unchanged)
# -----------------------------------------------------------------------------

tts = pyttsx3.init()
tts.setProperty("rate", 180) 
vosk_model = None

def load_model():
    global vosk_model
    if not VOSK_AVAILABLE: return False
    if not os.path.isdir(VOSK_MODEL_DIR):
        print(f"Vosk model not found at: {VOSK_MODEL_DIR}")
        return False
    if vosk_model is None: vosk_model = Model(VOSK_MODEL_DIR)
    return True

def speak(text):
    print("JARVIS:", text)
    hud_state["state"], hud_state["intensity"] = "speaking", 0.8
    tts.say(text)
    tts.runAndWait()
    hud_state["state"], hud_state["intensity"] = "idle", 0.5

def listen_once(device_index=None):
    if vosk_model is None: return ""
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True,
                    frames_per_buffer=CHUNK, input_device_index=device_index)
    rec = KaldiRecognizer(vosk_model, RATE)
    
    hud_state["state"], hud_state["intensity"] = "listening", 1.0
    print("Listening...")

    for _ in range(0, int(RATE / CHUNK * LISTEN_DURATION_SEC)):
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
    hud_state["state"], hud_state["intensity"] = "thinking", 0.7
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, 
                  "options": {"num_predict": OLLAMA_MAX_TOKENS}},
            timeout=30
        )
        data = response.json()
        return data.get("response", "Local model unavailable.").strip()
    except Exception as e:
        print(f"Ollama Error: {e}")
        return "I am having trouble connecting to the local model."

def handle_action(action_text):
    command = WHITELISTED_ACTIONS.get(action_text.lower().replace(" ", "_"))
    if command:
        try:
            subprocess.Popen(command['cmd'], shell=True) 
            return "Command executed successfully."
        except Exception:
            return f"Failed to run command: {action_text}"
    return "Action not recognized."

# -----------------------------------------------------------------------------
# --- 4. CONTROLLER (Connects Backend to HUD) --- (Unchanged)
# -----------------------------------------------------------------------------

class JarvisController(threading.Thread):
    def __init__(self, mic_index=None):
        super().__init__()
        self.mic_index = mic_index
        self.running = True
        self.daemon = True 

    def run(self):
        if not load_model():
            speak("Error: Voice model not found. Speech recognition is disabled.")
        else:
            speak("Jarvis system online. Press Enter in the console to activate.")
        time.sleep(1) 

        while self.running:
            try:
                input("\n[Press Enter to Speak]...")
                
                user_text = listen_once(self.mic_index)
                if not user_text.strip():
                    hud_state["state"], hud_state["intensity"] = "idle", 0.5
                    continue 

                lower_text = user_text.lower()
                
                if any(x in lower_text for x in ["exit", "shutdown", "goodbye"]):
                    self.running = False
                    speak("Goodbye. System shutting down.")
                    break 

                prompt = f"You are a helpful and concise assistant named Jarvis. The user said: \"{user_text}\". Answer concisely. If the user asked to run a whitelisted system action (like open notepad or open browser), output a single line starting with ACTION: followed by the action name exactly as defined in the list. Otherwise just answer normally."
                response = query_ollama(prompt)
                
                if "ACTION:" in response:
                    parts = response.split("ACTION:", 1)
                    speech_text = parts[0].strip()
                    action_text = parts[1].strip()
                    
                    if speech_text: speak(speech_text)
                    
                    action_result = handle_action(action_text)
                    if not speech_text: speak(action_result)
                else:
                    speak(response)
                    
            except KeyboardInterrupt:
                self.running = False
                speak("Interrupted. Shutting down.")
            except Exception as e:
                print(f"Controller Error: {e}")
                speak("An unexpected error occurred.")
                hud_state["state"], hud_state["intensity"] = "idle", 0.5


# -----------------------------------------------------------------------------
# --- 5. MAIN EXECUTION --- (Unchanged)
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    
    controller = JarvisController(mic_index=None) 
    controller.start()
    
    root = tk.Tk()
    gui = JarvisGUI(root)
    
    root.bind('q', lambda e: controller.running and root.quit())
    root.bind('<Escape>', lambda e: controller.running and root.quit())
    
    root.mainloop() 
    
    controller.running = False
    print("Application closed.")